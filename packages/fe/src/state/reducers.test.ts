// reducer 단독 (순수 함수) — Time·Closure·Route, 라벨
import { describe, expect, it } from "vitest";
import { LEG_KO, distanceKo, hhmm, josaRo, reasonKo, untilKo, whenKo, windowKo } from "../i18n/ko";
import type { LngLat } from "../map/layers/routeLayer";
import type { ErrorBody } from "../types/contracts";
import { recorded, recordedClosures, recordedRoute } from "../test/recorded";
import {
  DEFAULT_BBOX,
  EMPTY_CLOSURES,
  closureReducer,
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
  kstIso,
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

describe("closureReducer", () => {
  const fc = recordedClosures("closures_0745");
  it("request → receive → setBbox", () => {
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
    const same = closureReducer(s, { type: "setBbox", bbox: s.bbox });
    expect(same).toBe(s); // 같은 bbox 면 참조 유지 → 재요청 없음
    const moved = closureReducer(s, { type: "setBbox", bbox: "126.9,37.5,127.0,37.6" });
    expect(moved.bbox).toBe("126.9,37.5,127.0,37.6");
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
const r0430 = recordedRoute("route_0430");

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
    // 두 기록 경로를 이어 걸은 거리 839.6 + 846.3 = 1685.9 m
    expect(distanceKo(r0745.distance_m + r0430.distance_m)).toBe("1.7km");
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

  it("whenKo — 기준 시각과 같은 날이면 HH:MM, 다른 날이면 M/D HH:MM", () => {
    // route_0745 avoided[0].evidence: 시각표 게시 2026-03-12T16:07, 해제 2026-03-15T08:08
    const ev = r0745.avoided[0]?.evidence ?? [];
    expect(whenKo(ev[0]?.at, T745)).toBe("3/12 16:07");
    expect(whenKo(ev[1]?.at, T745)).toBe("08:08");
    expect(whenKo(null, T745)).toBe("—");
  });
});
