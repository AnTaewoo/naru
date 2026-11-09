// reducer 단독 (순수 함수) — Time·Closure·Route, 라벨
import { describe, expect, it } from "vitest";
import {
  LEG_KO,
  dateKo,
  dayKo,
  distanceKo,
  hhmm,
  josaRo,
  reasonKo,
  sheetTitleKo,
  untilKo,
  windowKo,
} from "../i18n/ko";
import { parseGeocodeSearch, placeLngLat } from "../api/naruApiClient";
import type { LngLat } from "../map/layers/routeLayer";
import type { ClosureEventsResponse, ErrorBody } from "../types/contracts";
import { recorded, recordedClosures, recordedEvents, recordedRoute } from "../test/recorded";
import {
  DEFAULT_BBOX,
  EMPTY_CLOSURES,
  asBbox4,
  catalogParams,
  closureReducer,
  eventFromLocation,
  inBbox,
  initialClosureState,
} from "./ClosureProvider";
import {
  initialRouteState,
  latLngParam,
  odFromLocation,
  parseLatLng,
  routeReducer,
} from "./RouteProvider";
import {
  dayBoundsKst,
  initialTimeState,
  isNowAt,
  kstIso,
  liveFromLocation,
  minutesFromDayStart,
  pendingTimeState,
  tFromLocation,
  timeReducer,
} from "./TimeProvider";

describe("timeReducer", () => {
  const t0 = "2026-03-15T07:45:00+09:00"; // recorded /route·/closures 의 통제 중 시각
  it("하루 범위는 KST 자정~자정, 분 단위 위치", () => {
    const s = initialTimeState(t0);
    expect(s.t).toBe(t0);
    expect(s.dayStart).toBe("2026-03-15T00:00:00+09:00");
    expect(s.dayEnd).toBe("2026-03-16T00:00:00+09:00");
    expect(minutesFromDayStart(s)).toBe(7 * 60 + 45);
    expect(dayBoundsKst("2026-03-14T23:30:00+09:00").dayStart).toBe("2026-03-14T00:00:00+09:00");
    expect(kstIso(Date.UTC(2026, 2, 14, 22, 45))).toBe(t0); // UTC 22:45 = KST 07:45 다음 날
  });
  it("setMinutes·step 은 날 안에서 움직이고 넘치면 자른다", () => {
    const s = initialTimeState(t0);
    expect(timeReducer(s, { type: "setMinutes", minutesFromDayStart: 13 * 60 + 30 }).t).toBe(
      "2026-03-15T13:30:00+09:00",
    );
    expect(timeReducer(s, { type: "step", deltaMin: 10 }).t).toBe("2026-03-15T07:55:00+09:00");
    expect(timeReducer(s, { type: "step", deltaMin: -8 * 60 }).t).toBe("2026-03-15T00:00:00+09:00");
    expect(timeReducer(s, { type: "setMinutes", minutesFromDayStart: 9999 }).t).toBe(
      "2026-03-16T00:00:00+09:00",
    );
    const other = timeReducer(s, { type: "set", t: "2026-11-07T15:30:00+09:00" });
    expect(other.dayStart).toBe("2026-11-07T00:00:00+09:00");
  });
  it("하이드레이션 자리값 — ready false, 슬라이더 조작 무시, set 으로 ready", () => {
    const pending = pendingTimeState();
    expect(pending.ready).toBe(false);
    expect(pendingTimeState()).toEqual(pending); // 서버·클라이언트가 같은 값 (Date.now 미사용)
    expect(timeReducer(pending, { type: "step", deltaMin: 10 })).toBe(pending);
    const set = timeReducer(pending, { type: "set", t: t0 });
    expect(set.ready).toBe(true);
    expect(set.t).toBe(t0);
    expect(initialTimeState(t0).ready).toBe(true);
  });
  it("?t= 가 있으면 그 시각, 아니면 now", () => {
    expect(tFromLocation("?t=2026-03-15T07:45:00%2B09:00")).toBe(t0);
    expect(tFromLocation("?t=2026-03-15T07:45:00+09:00")).toBe(t0);
    expect(tFromLocation("?t=garbage", () => Date.UTC(2026, 2, 14, 22, 45))).toBe(t0);
    expect(tFromLocation("", () => Date.UTC(2026, 2, 14, 22, 45))).toBe(t0);
  });
});

describe("지금 모드 (T7.4)", () => {
  // 사건 v2 기록 closure_events_live_1107_1530 의 at
  const at = Date.parse("2026-11-07T15:30:00+09:00");
  it("?t= 없이 열었거나 '지금으로'면 live — 5분마다 지금으로, 그 사이엔 같은 t(같은 at → 304)", () => {
    expect(liveFromLocation("")).toBe(true);
    expect(liveFromLocation("?t=garbage")).toBe(true); // tFromLocation 도 지금으로 간다
    expect(liveFromLocation("?t=2026-03-15T07:45:00%2B09:00")).toBe(false);
    const live = timeReducer(pendingTimeState(), { type: "set", t: kstIso(at), live: true });
    expect(live.live).toBe(true);
    expect(timeReducer(live, { type: "tick", nowMs: at + 4 * 60_000 + 59_000 })).toBe(live);
    const next = timeReducer(live, { type: "tick", nowMs: at + 5 * 60_000 });
    expect(next.t).toBe("2026-11-07T15:35:00+09:00");
    expect(next.live).toBe(true);
  });
  it("슬라이더를 만지거나 시각을 정해 옮기면 멈춘다 — 그 뒤 tick 은 무시", () => {
    const live = timeReducer(pendingTimeState(), { type: "set", t: kstIso(at), live: true });
    const stepped = timeReducer(live, { type: "step", deltaMin: 10 });
    expect(stepped.live).toBe(false);
    expect(timeReducer(stepped, { type: "tick", nowMs: at + 60 * 60_000 })).toBe(stepped);
    const slid = timeReducer(live, { type: "setMinutes", minutesFromDayStart: 16 * 60 });
    expect(slid.live).toBe(false);
    expect(timeReducer(live, { type: "set", t: "2026-03-15T07:45:00+09:00" }).live).toBe(false);
    expect(initialTimeState("2026-03-15T07:45:00+09:00").live).toBe(false);
    expect(pendingTimeState().live).toBe(false);
  });
});

describe("달력 (T7.11)", () => {
  it("날짜를 바꾸면 그날 같은 시각 — live 끔, 날 범위도 그날", () => {
    // 11/9 12:00 = 국회대로 행진 예시 시각, 3/15 = 서울마라톤 (사건 v2 기록의 날짜)
    const live = timeReducer(pendingTimeState(), {
      type: "set",
      t: "2026-11-09T12:00:00+09:00",
      live: true,
    });
    const day = timeReducer(live, { type: "setDay", day: "2026-03-15" });
    expect(day.t).toBe("2026-03-15T12:00:00+09:00");
    expect(day.dayStart).toBe("2026-03-15T00:00:00+09:00");
    expect(day.live).toBe(false);
  });
  it("슬라이더 끝(24:00)에서 바꿔도 그날에 머문다(23:59), 읽을 수 없는 날짜·시각 전엔 그대로", () => {
    const day = timeReducer(pendingTimeState(), { type: "set", t: "2026-03-15T07:45:00+09:00" });
    const end = timeReducer(day, { type: "setMinutes", minutesFromDayStart: 24 * 60 });
    expect(timeReducer(end, { type: "setDay", day: "2026-11-07" }).t).toBe(
      "2026-11-07T23:59:00+09:00",
    );
    expect(timeReducer(day, { type: "setDay", day: "" })).toBe(day);
    const pending = pendingTimeState();
    expect(timeReducer(pending, { type: "setDay", day: "2026-03-15" })).toBe(pending);
  });
});

describe("closureReducer", () => {
  const fc = recordedClosures("closures_0745");
  it("request → receive → setView", () => {
    let s = initialClosureState();
    expect(s.status).toBe("idle");
    expect(s.bbox).toBe(DEFAULT_BBOX);
    expect(s.closures).toBe(EMPTY_CLOSURES);
    s = closureReducer(s, { type: "request", at: "2026-03-15T07:45:00+09:00", bbox: s.bbox });
    expect(s.status).toBe("loading");
    s = closureReducer(s, {
      type: "receive",
      at: "2026-03-15T07:45:00+09:00",
      bbox: s.bbox,
      closures: fc,
    });
    expect(s.status).toBe("ready");
    expect(s.closures.features).toHaveLength(79);
    expect(s.at).toBe("2026-03-15T07:45:00+09:00");
    const same = closureReducer(s, { type: "setView", bbox: s.bbox, points: s.points });
    expect(same).toBe(s); // 같은 화면이면 참조 유지 → 재요청 없음
    expect(s.points).toBe(false); // 처음은 서울 전체 — 횡단보도 점은 줌 14 이상·길찾기에서만 (T7.4)
    const moved = closureReducer(s, {
      type: "setView",
      bbox: "126.9,37.5,127.0,37.6",
      points: true,
    });
    expect(moved.bbox).toBe("126.9,37.5,127.0,37.6");
    expect(moved.points).toBe(true);
    expect(moved.closures).toBe(fc); // 이전 결과는 유지(깜빡임 없음)
    const failed = closureReducer(moved, { type: "fail", error: "x" });
    expect(failed.status).toBe("error");
    expect(failed.closures).toBe(fc);
  });
});

describe("reasonKo", () => {
  it("reason 앞머리의 type 코드값만 한국어로 — 나머지·자유 문장은 그대로", () => {
    // recorded /closures 0745 의 reason (BE ClosureEngine._reason: "<type> <구간> <구간명>")
    expect(reasonKo("marathon 1구간 세종대로 사거리~숭례문 오거리")).toBe(
      "마라톤 1구간 세종대로 사거리~숭례문 오거리",
    );
    // 공지 후보는 공지 원문이 reason — 바꾸지 않는다 (T4.4 e2e 의 실제 reason)
    const notice =
      "12:00~16:00 동화면세점 앞 → 종로1R → 동화면세점 앞 <세종대로 등> 50,000명 종로, 남대문";
    expect(reasonKo(notice)).toBe(notice);
    expect(reasonKo("marathonx 1구간")).toBe("marathonx 1구간");
  });
});

describe("ko 라벨·시각", () => {
  it("hhmm·windowKo·untilKo", () => {
    expect(hhmm("2026-03-15T07:45:00+09:00")).toBe("07:45");
    expect(hhmm("2026-03-14T22:45:00+00:00")).toBe("07:45"); // UTC 도 KST 로
    expect(hhmm(null)).toBe("—");
    expect(windowKo("2026-03-15T07:20:00+09:00", "2026-03-15T08:08:00+09:00")).toBe("07:20–08:08");
    expect(windowKo("2026-03-15T07:20:00+09:00", null)).toBe("07:20–종료 미정");
    expect(untilKo("2026-03-15T08:08:00+09:00", "2026-03-15T07:45:00+09:00")).toBe("23분 뒤 해제");
    expect(untilKo("2026-03-15T10:00:00+09:00", "2026-03-15T07:45:00+09:00")).toBe(
      "2시간 15분 뒤 해제",
    );
    expect(untilKo("2026-03-15T08:08:00+09:00", "2026-03-15T09:00:00+09:00")).toBe("해제됨");
  });
});

// recorded naru_api/route_0745.json 의 query — 교보빌딩 앞 → 대한문, "lat,lng" (record_naru_api.py 가 보낸 값)
const T745 = "2026-03-15T07:45:00+09:00";
const T1330 = "2026-03-15T13:30:00+09:00";
const q745 = recorded("route_0745").query ?? {};
const r0745 = recordedRoute("route_0745");

describe("routeReducer", () => {
  const od = odFromLocation(`?t=${T745}&from=${q745["from"] ?? ""}&to=${q745["to"] ?? ""}`);
  const from: LngLat = od.from ?? [0, 0];
  const to: LngLat = od.to ?? [0, 0];
  // 세 번째로 누를 점 — 경로 가운데 좌표 (route_0745 route.coordinates[13])
  const [midLng, midLat] = (r0745.route.coordinates[13] ?? []) as number[];
  const third: LngLat = [midLng ?? 0, midLat ?? 0];

  it("?from=&to= 는 lat,lng → [lng, lat], 되돌리면 같은 문자열. 순서가 틀리거나 숫자가 아니면 null", () => {
    expect(od.from).not.toBeNull();
    expect(od.to).not.toBeNull();
    expect(latLngParam(from)).toBe(q745["from"]);
    expect(latLngParam(to)).toBe(q745["to"]);
    expect(from[0]).toBeGreaterThan(from[1]); // 경도(126…)가 앞
    expect(parseLatLng(`${from[0]},${from[1]}`)).toBeNull(); // lng,lat 로 주면 위도가 범위 밖
    expect(parseLatLng("출발")).toBeNull();
    expect(odFromLocation(`?t=${T745}`)).toEqual({ from: null, to: null });
  });

  it("길찾기를 켜야 지도 고르기가 먹는다 — 출발 → 도착 → 세 번째는 무시, 바꾸기·다시 고르기·닫기", () => {
    const s0 = initialRouteState();
    expect(s0.active).toBe(false);
    expect(routeReducer(s0, { type: "pick", point: from })).toBe(s0);
    const s1 = routeReducer(s0, { type: "open" });
    const s2 = routeReducer(s1, { type: "pick", point: from });
    expect(s2.from).toEqual(from);
    expect(s2.to).toBeNull();
    const s3 = routeReducer(s2, { type: "pick", point: to });
    expect(s3.to).toEqual(to);
    expect(routeReducer(s3, { type: "pick", point: third })).toBe(s3);
    const swapped = routeReducer(s3, { type: "swap" });
    expect(swapped.from).toEqual(to);
    expect(swapped.to).toEqual(from);
    const unset = routeReducer(s3, { type: "unset", which: "to" });
    expect(unset.to).toBeNull();
    expect(routeReducer(unset, { type: "pick", point: third }).to).toEqual(third);
    expect(routeReducer(s3, { type: "close" })).toEqual(initialRouteState());
  });

  it("request → receive → (t 이동) request 중엔 이전 경로 유지 → fail 은 경로를 지운다. 출발·도착이 바뀌어도 지운다", () => {
    const base = routeReducer(initialRouteState(), { type: "setOd", from, to });
    expect(base.active).toBe(true);
    const loading = routeReducer(base, { type: "request", at: T745 });
    expect(loading.status).toBe("loading");
    const ready = routeReducer(loading, { type: "receive", at: T745, route: r0745 });
    expect(ready.status).toBe("ready");
    expect(ready.route).toBe(r0745);
    expect(ready.at).toBe(T745);
    const again = routeReducer(ready, { type: "request", at: T1330 });
    expect(again.status).toBe("loading");
    expect(again.route).toBe(r0745); // 깜빡임 없음
    // 실제 Flask 오류 응답 (recorded naru_api/error_invalid_query.json)
    const err = recorded("error_invalid_query").body as ErrorBody;
    const failed = routeReducer(again, {
      type: "fail",
      error: err.error.message,
      code: err.error.code,
    });
    expect(failed.status).toBe("error");
    expect(failed.route).toBeNull();
    expect(failed.errorCode).toBe("invalid_query");
    const moved = routeReducer(ready, { type: "setOd", from: to, to: from });
    expect(moved.route).toBeNull();
    expect(moved.status).toBe("idle");
    expect(routeReducer(ready, { type: "setOd", from, to })).toBe(ready); // 같은 점이면 그대로
  });
});

describe("길찾기 라벨", () => {
  it("distanceKo — 1 km 아래는 m 반올림, 넘으면 km 소수 한 자리", () => {
    expect(distanceKo(r0745.distance_m)).toBe("840m"); // 839.6
    expect(distanceKo(r0745.baseline.distance_m)).toBe("808m"); // 808.3
    // route_1107_1500 (11/7 15:00 세종대로 우회) 1,122.5 m
    expect(distanceKo(recordedRoute("route_1107_1500").distance_m)).toBe("1.1km");
  });

  it("josaRo — 받침 없거나 ㄹ 받침이면 '로', 그 밖은 '으로', 한글로 안 끝나면 '(으)로'", () => {
    const name = r0745.legs.find((l) => l.kind === "underpass")?.name ?? "";
    expect(name).toBe("광화문(세종문화회관) 지하보도");
    expect(josaRo(name)).toBe("로");
    expect(josaRo(LEG_KO.overpass)).toBe("로"); // 육교
    expect(josaRo(LEG_KO.stairs)).toBe("으로"); // 계단
    expect(josaRo(LEG_KO.station)).toBe("로"); // 역 통과
    expect(josaRo(name.slice(0, name.indexOf(" ")))).toBe("(으)로"); // 괄호로 끝남
  });
});

// recorded naru_api/closure_events.json — 11/7 집회 2(15:00·12:00 시작) + 3/15 마라톤 5, 시작 늦은 순
const events = recordedEvents().events;
// 같은 파일의 coverage (INTERFACE v0.10) — 보행망 노드 bbox (T5.7 재기록, MANIFEST)
const coverage = asBbox4(recordedEvents().coverage);

describe("closureReducer — 지금 지도 사건·지도 맞춤 (T5.4·T7.4)", () => {
  // 사건 v2 기록 (scripts/record_live_events.py) — 11/7 15:30 사건 13, 응답 ETag 같이
  const rec = recorded("closure_events_live_1107_1530");
  const body = rec.body as ClosureEventsResponse;
  it("receiveEvents 로 사건·기준 시각·ETag·잘림, 실패해도 받아 둔 사건은 그대로", () => {
    const s0 = initialClosureState();
    expect(s0.events).toBeNull();
    expect(s0.eventsEtag).toBeNull();
    expect(s0.coverage).toBeNull();
    const s1 = closureReducer(s0, {
      type: "receiveEvents",
      events: body.events,
      at: body.at,
      etag: rec.etag ?? null,
      truncated: body.truncated ?? false,
      coverage: asBbox4(body.coverage),
      dataAsOf: body.data_as_of,
    });
    expect(s1.events).toBe(body.events);
    expect(s1.eventsAt).toBe("2026-11-07T15:30:00+09:00");
    expect(s1.eventsEtag).toBe(rec.etag);
    expect(s1.truncated).toBe(false);
    expect(s1.dataAsOf).toBe(body.data_as_of);
    expect(s1.coverage).toEqual(body.coverage);
    // 실제 Flask 오류 문구 (recorded naru_api/error_not_found.json)
    const err = recorded("error_not_found").body as ErrorBody;
    const failed = closureReducer(s1, { type: "failEvents", error: err.error.message });
    expect(failed.events).toBe(body.events); // 실패해도 받아 둔 사건은 그대로
    expect(failed.eventsError).toBe(err.error.message);
  });

  it("사건 카드 (T7.5) — select 로 열고 null 로 닫는다. pick 은 묶음 목록(하나면 바로 카드), unpick 은 전체로", () => {
    const s0 = initialClosureState();
    expect([s0.selected, s0.picked]).toEqual([null, null]);
    // 11/7 15:30 광화문 묶음 일부 — 돌발 사직로(통제 중)·경찰청 r04(1시간 안)
    const opened = closureReducer(s0, { type: "select", id: "159e13bfe71a" });
    expect(opened.selected).toBe("159e13bfe71a");
    expect(closureReducer(opened, { type: "select", id: null }).selected).toBeNull();
    const two = closureReducer(s0, { type: "pick", ids: ["159e13bfe71a", "2e930ec6deeb"] });
    expect([two.picked, two.selected]).toEqual([["159e13bfe71a", "2e930ec6deeb"], null]);
    const card = closureReducer(two, { type: "select", id: "2e930ec6deeb" });
    expect(card.picked).toEqual(["159e13bfe71a", "2e930ec6deeb"]); // 카드를 닫으면 묶음으로 돌아간다
    expect(closureReducer(card, { type: "unpick" })).toMatchObject({ picked: null });
    const one = closureReducer(s0, { type: "pick", ids: ["2e930ec6deeb"] });
    expect([one.picked, one.selected]).toEqual([null, "2e930ec6deeb"]);
    expect(closureReducer(s0, { type: "pick", ids: [] })).toBe(s0);
  });

  it("frame (T7.11 예시로 보기) — 지도 맞춤 요청은 누를 때마다 순번, 카드·묶음은 닫는다", () => {
    const opened = closureReducer(initialClosureState(), { type: "select", id: "2e930ec6deeb" });
    // 11/7 r04 의 bbox (closure_events_live_1107_1530.json)
    const bbox: [number, number, number, number] = [
      126.975691, 37.5605144, 126.9875484, 37.5749426,
    ];
    const f1 = closureReducer(opened, { type: "frame", bbox });
    expect(f1.frame).toEqual({ bbox, seq: 1 });
    expect([f1.selected, f1.picked]).toEqual([null, null]);
    expect(closureReducer(f1, { type: "frame", bbox }).frame?.seq).toBe(2);
  });

  it("시트 목록 (T7.12) — 넓은 창 질의는 기준 시각 앞뒤 365일, receiveCatalog 로 사건·기준 시각·ETag", () => {
    // 넓은 창 기록 closure_events_catalog_1107_1530 의 질의와 같다
    const wide = recorded("closure_events_catalog_1107_1530");
    expect(catalogParams("2026-11-07T15:30:00+09:00")).toEqual(wide.query);
    const body = wide.body as ClosureEventsResponse;
    const s = closureReducer(initialClosureState(), {
      type: "receiveCatalog",
      events: body.events,
      at: body.at,
      etag: wide.etag ?? null,
    });
    expect(s.catalog).toBe(body.events);
    expect(s.catalogAt).toBe("2026-11-07T15:30:00+09:00");
    expect(s.catalogEtag).toBe(wide.etag);
    expect(initialClosureState().catalog).toBeNull();
  });

  it("?event= — 사건 id(12자 소문자 16진)만 받는다", () => {
    expect(eventFromLocation("?event=2e930ec6deeb&t=2026-11-07T15:00:00%2B09:00")).toBe(
      "2e930ec6deeb",
    );
    expect(eventFromLocation("?event=<script>")).toBeNull();
    expect(eventFromLocation("")).toBeNull();
  });
});

describe("날짜 라벨 (T5.4)", () => {
  it("dateKo·dayKo — KST 날짜와 요일", () => {
    expect(dayKo(events[0]?.window.start)).toBe("11월 7일 (토)"); // 2026-11-07 15:00 집회
    expect(dateKo(T745)).toBe("3월 15일");
    expect(dayKo(T745)).toBe("3월 15일 (일)"); // 서울마라톤 일요일 (MANIFEST course)
    expect(dayKo(null)).toBe("시간 미정");
  });

  it("sheetTitleKo — 기준 시각이 지금과 같은 날(KST)이면 '오늘 통제', 아니면 그 날짜", () => {
    const rallyMs = Date.parse(events[0]?.window.start ?? "");
    expect(sheetTitleKo(T745, Date.parse(T1330))).toBe("오늘 통제"); // 같은 3/15
    expect(sheetTitleKo(T745, rallyMs)).toBe("3월 15일 통제"); // 지금이 11/7 이면
  });
});

describe("내 위치 (T5.7)", () => {
  // 출발·도착 = recorded route_0745 질의(카카오 광화문교보빌딩·덕수궁 대한문), 가운데 점 = 그 경로 좌표[13]
  const od = odFromLocation(`?from=${q745["from"] ?? ""}&to=${q745["to"] ?? ""}`);
  const kyobo: LngLat = od.from ?? [0, 0];
  const daehanmun: LngLat = od.to ?? [0, 0];
  const [midLng, midLat] = (r0745.route.coordinates[13] ?? []) as number[];
  const mid: LngLat = [midLng ?? 0, midLat ?? 0];
  // 범위 밖 — 태우가 실서버에 보낸 잠실 요청 (recorded naru_api/error_out_of_coverage.json 의 from)
  const jamsil = parseLatLng(recorded("error_out_of_coverage").query?.["from"]) ?? [0, 0];

  it("coverage — 기록된 보행망 bbox, 교보빌딩·대한문은 안, 잠실은 밖. 숫자 4개가 아니면 null", () => {
    expect(coverage).toEqual([
      126.94810841609588, 37.54264971358972, 127.02668353217784, 37.63148349215145,
    ]);
    if (!coverage) throw new Error("기록에 coverage 가 없다 — make record-naru-api");
    expect(inBbox(kyobo, coverage)).toBe(true);
    expect(inBbox(daehanmun, coverage)).toBe(true);
    expect(jamsil).toEqual([127.098, 37.5133]);
    expect(inBbox(jamsil, coverage)).toBe(false);
    expect(asBbox4([1, 2, 3])).toBeNull();
    expect(asBbox4([1, 2, "3", 4])).toBeNull();
  });

  it("길찾기를 켜면 출발은 내 위치부터 — 받으면 출발이 내 위치, 찾는 중 지도를 누르면 그 점, 늦은 위치는 버린다", () => {
    const opened = routeReducer(initialRouteState(), { type: "open" });
    expect(opened.locate).toEqual({ which: "from", status: "locating" });
    const got = routeReducer(opened, { type: "located", point: kyobo, coverage });
    expect(got.from).toEqual(kyobo);
    expect(got.mine).toEqual(kyobo);
    expect(got.locate).toBeNull();
    const picked = routeReducer(opened, { type: "pick", point: mid });
    expect(picked.from).toEqual(mid);
    expect(picked.locate).toBeNull();
    expect(routeReducer(picked, { type: "located", point: kyobo, coverage })).toBe(picked);
    // URL(?from=) 로 출발이 정해져 들어오면 찾지 않는다
    const fromUrl = routeReducer(initialRouteState(), { type: "setOd", from: kyobo, to: null });
    expect(fromUrl.locate).toBeNull();
    expect(routeReducer(fromUrl, { type: "open" }).locate).toBeNull();
    expect(routeReducer(got, { type: "close" })).toEqual(initialRouteState());
  });

  it("거부·실패·범위 밖이면 칸은 비우고 안내 — 지도로 채우면 안내가 사라진다. coverage 를 못 받았으면 막지 않는다", () => {
    const opened = routeReducer(initialRouteState(), { type: "open" });
    const denied = routeReducer(opened, { type: "locateFail", reason: "denied" });
    expect(denied.locate).toEqual({ which: "from", status: "denied" });
    expect(denied.from).toBeNull();
    const failed = routeReducer(opened, { type: "locateFail", reason: "unavailable" });
    expect(failed.locate).toEqual({ which: "from", status: "unavailable" });
    const outside = routeReducer(opened, { type: "located", point: jamsil, coverage });
    expect(outside.locate).toEqual({ which: "from", status: "outside" });
    expect(outside.from).toBeNull();
    expect(outside.mine).toBeNull();
    const picked = routeReducer(outside, { type: "pick", point: kyobo });
    expect(picked.from).toEqual(kyobo);
    expect(picked.locate).toBeNull();
    // 찾는 중이 아니면 결과를 버린다
    expect(routeReducer(denied, { type: "located", point: kyobo, coverage })).toBe(denied);
    expect(routeReducer(picked, { type: "locateFail", reason: "denied" })).toBe(picked);
    // 범위를 아직 모르면 그대로 넣는다 — BE /route 가 out_of_coverage 로 답한다
    const unknown = routeReducer(opened, { type: "located", point: jamsil, coverage: null });
    expect(unknown.from).toEqual(jamsil);
  });

  it("칸 옆 내 위치 버튼 — 그 칸만 바꾼다. 다른 칸을 지도로 채워도 찾기는 계속, 길찾기가 꺼져 있으면 무시", () => {
    const s0 = initialRouteState();
    expect(routeReducer(s0, { type: "locate", which: "from" })).toBe(s0);
    const both = routeReducer(s0, { type: "setOd", from: mid, to: daehanmun });
    const toMine = routeReducer(both, { type: "locate", which: "to" });
    expect(toMine.locate).toEqual({ which: "to", status: "locating" });
    expect(toMine.to).toEqual(daehanmun); // 받기 전엔 그대로
    const done = routeReducer(toMine, { type: "located", point: kyobo, coverage });
    expect(done.to).toEqual(kyobo);
    expect(done.from).toEqual(mid);
    const empty = routeReducer(s0, { type: "setOd", from: null, to: null });
    const waiting = routeReducer(empty, { type: "locate", which: "to" });
    const pickedFrom = routeReducer(waiting, { type: "pick", point: mid });
    expect(pickedFrom.from).toEqual(mid);
    expect(pickedFrom.locate).toEqual({ which: "to", status: "locating" });
    const swapped = routeReducer(done, { type: "swap" });
    expect(swapped.from).toEqual(kyobo);
    expect(swapped.mine).toEqual(kyobo); // 바꿔도 내 위치는 기억한다 (칸 이름 "내 위치")
  });
});

describe("주소·검색 (T5.8)", () => {
  // recorded naru_api/geocode_search_*.json (카카오 기록 재생): '교보빌딩' 1위 광화문교보빌딩,
  // '덕수궁' 3위 덕수궁 대한문 — route_0745 의 출발·도착과 같은 좌표
  const kyobo = parseGeocodeSearch(recorded("geocode_search_kyobo").body).places[0];
  const daehanmun = parseGeocodeSearch(recorded("geocode_search_deoksugung").body).places[2];
  const kyoboAt = kyobo ? placeLngLat(kyobo) : null;
  const daehanmunAt = daehanmun ? placeLngLat(daehanmun) : null;
  if (!kyobo || !daehanmun || !kyoboAt || !daehanmunAt) throw new Error("기록 장소가 없다");
  const q = odFromLocation(`?from=${q745["from"] ?? ""}&to=${q745["to"] ?? ""}`);

  it("검색 1위·3위는 route_0745 출발·도착점 — 장소 좌표가 질의 좌표와 같다", () => {
    expect([kyobo.name, daehanmun.name]).toEqual(["광화문교보빌딩", "덕수궁 대한문"]);
    expect(kyoboAt).toEqual(q.from);
    expect(daehanmunAt).toEqual(q.to);
  });

  it("홈 검색에서 도착을 고르면 길찾기가 켜지고 출발은 내 위치부터 — 출발을 고르면 찾지 않는다", () => {
    const s0 = initialRouteState();
    expect([s0.names, s0.editing]).toEqual([{ from: null, to: null }, null]);
    const toPlace = routeReducer(s0, {
      type: "choose",
      which: "to",
      point: daehanmunAt,
      name: daehanmun.name,
    });
    expect(toPlace.active).toBe(true);
    expect(toPlace.to).toEqual(daehanmunAt);
    expect(toPlace.names.to).toEqual({ point: daehanmunAt, text: "덕수궁 대한문" });
    expect(toPlace.locate).toEqual({ which: "from", status: "locating" });
    const fromPlace = routeReducer(s0, {
      type: "choose",
      which: "from",
      point: kyoboAt,
      name: kyobo.name,
    });
    expect([fromPlace.active, fromPlace.from, fromPlace.locate]).toEqual([true, kyoboAt, null]);
  });

  it("칸을 누르면 입력 중 — 지도를 누르면 그 칸에(둘 다 차 있어도), 검색으로 고르면 장소 이름", () => {
    const both = routeReducer(initialRouteState(), { type: "setOd", from: q.from, to: q.to });
    expect(routeReducer(initialRouteState(), { type: "edit", which: "to" }).editing).toBeNull();
    const editing = routeReducer(both, { type: "edit", which: "from" });
    expect(editing.editing).toBe("from");
    const tapped = routeReducer(editing, { type: "pick", point: daehanmunAt });
    expect([tapped.from, tapped.to, tapped.editing]).toEqual([daehanmunAt, q.to, null]);
    expect(routeReducer(both, { type: "pick", point: daehanmunAt })).toBe(both); // 입력 중이 아니면 무시
    const chosen = routeReducer(routeReducer(both, { type: "edit", which: "to" }), {
      type: "choose",
      which: "to",
      point: kyoboAt,
      name: kyobo.name,
    });
    expect([chosen.to, chosen.names.to?.text, chosen.editing]).toEqual([
      kyoboAt,
      "광화문교보빌딩",
      null,
    ]);
    expect(routeReducer(editing, { type: "edit", which: null }).editing).toBeNull();
    // 입력 중에 '내 위치' 를 누르면 입력은 끝난다
    expect(routeReducer(editing, { type: "locate", which: "from" }).editing).toBeNull();
  });

  it("주소(named)는 그 점일 때만 받는다, 바꾸기는 이름도 바꾼다", () => {
    const both = routeReducer(initialRouteState(), { type: "setOd", from: q.from, to: q.to });
    // recorded naru_api/geocode_reverse_kyobo.json 의 label
    const named = routeReducer(both, {
      type: "named",
      which: "from",
      point: kyoboAt,
      text: "종로구 종로 1",
    });
    expect(named.names.from).toEqual({ point: kyoboAt, text: "종로구 종로 1" });
    expect(
      routeReducer(both, { type: "named", which: "from", point: daehanmunAt, text: "x" }),
    ).toBe(both); // 그새 칸이 바뀌었으면 버린다
    const swapped = routeReducer(named, { type: "swap" });
    expect(swapped.names.to).toEqual({ point: kyoboAt, text: "종로구 종로 1" });
    expect(swapped.names.from).toBeNull();
  });
});

describe("원래 길 보기 (T5.11)", () => {
  // recorded route_0745: 통제 중 2곳을 피함(원래 길 카드 있음), route_1330: 피한 곳 없음
  const od = odFromLocation(`?from=${q745["from"] ?? ""}&to=${q745["to"] ?? ""}`);
  const both = routeReducer(initialRouteState(), { type: "setOd", from: od.from, to: od.to });
  const ready = routeReducer(both, { type: "receive", at: T745, route: r0745 });

  it("카드를 누르면 원래 길·가장 빠른 길을 오간다 — 처음은 가장 빠른 길", () => {
    expect(ready.view).toBe("fastest");
    const original = routeReducer(ready, { type: "view", view: "original" });
    expect(original.view).toBe("original");
    expect(routeReducer(original, { type: "view", view: "fastest" }).view).toBe("fastest");
  });

  it("새 출발·도착이거나 피한 통제가 없는 경로가 오면 가장 빠른 길로 돌아간다", () => {
    const original = routeReducer(ready, { type: "view", view: "original" });
    expect(routeReducer(original, { type: "receive", at: T745, route: r0745 }).view).toBe(
      "original",
    );
    const r1330 = recordedRoute("route_1330");
    expect(r1330.avoided).toHaveLength(0);
    expect(routeReducer(original, { type: "receive", at: T1330, route: r1330 }).view).toBe(
      "fastest",
    );
    expect(routeReducer(original, { type: "swap" }).view).toBe("fastest");
    expect(routeReducer(original, { type: "close" }).view).toBe("fastest");
  });
});

describe("'지금' 배지 (T5.9)", () => {
  it("기준 시각이 실제 지금(±5분)일 때만 — 5분 넘게 떨어지면 아니다", () => {
    const t0 = Date.parse(T745); // recorded route_0745 출발 시각
    expect(isNowAt(T745, t0 + 4 * 60_000)).toBe(true);
    expect(isNowAt(T745, t0 - 4 * 60_000)).toBe(true);
    expect(isNowAt(T745, t0 + 6 * 60_000)).toBe(false);
    expect(isNowAt(T1330, t0)).toBe(false);
  });
});
