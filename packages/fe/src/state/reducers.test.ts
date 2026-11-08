// reducer 단독 (순수 함수) — Time·Closure
import { describe, expect, it } from "vitest";
import { hhmm, reasonKo, untilKo, windowKo } from "../i18n/ko";
import { recordedClosures } from "../test/recorded";
import {
  DEFAULT_BBOX,
  EMPTY_CLOSURES,
  closureReducer,
  initialClosureState,
} from "./ClosureProvider";
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
