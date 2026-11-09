// "예시로 보기" (T7.11) — 예시마다 그 시각에 걸린 통제가 있고, 지도를 맞출 bbox 가 그 사건을 담는다.
// 사건 v2 기록(scripts/record_live_events.py)을 열어 확인한 사건 id·창·bbox
import { describe, expect, it } from "vitest";
import { eventById, recordedLive } from "../test/recorded";
import type { ClosureEvent } from "../types/contracts";
import { EXAMPLES } from "./examples";

function covers(box: readonly number[], e: ClosureEvent): boolean {
  const [w, s, east, n] = e.bbox as number[];
  return (
    (box[0] ?? 0) <= (w ?? 0) &&
    (box[1] ?? 0) <= (s ?? 0) &&
    (box[2] ?? 0) >= (east ?? 0) &&
    (box[3] ?? 0) >= (n ?? 0)
  );
}

function during(t: string, e: ClosureEvent): boolean {
  const at = Date.parse(t);
  const start = Date.parse(e.window.start ?? "");
  const end = Date.parse(e.window.end ?? "");
  return start <= at && at <= end;
}

describe("예시로 보기", () => {
  it("셋 — 서울마라톤 3/15 07:45 · 광화문 집회·행진 11/7 15:00 · 국회대로 행진 11/9 12:00", () => {
    expect(EXAMPLES.map((x) => [x.key, x.t])).toEqual([
      ["marathon", "2026-03-15T07:45:00+09:00"],
      ["rally", "2026-11-07T15:00:00+09:00"],
      ["march", "2026-11-09T12:00:00+09:00"],
    ]);
  });

  it("그 시각에 걸린 통제를 bbox 가 담는다 — 1구간·출발지, 경찰청 r04, TOPIS 통제지도 1109233", () => {
    const [marathon, rally, march] = EXAMPLES;
    const m = recordedLive("closure_events_live_0315_0745").body.events;
    for (const id of ["adaea2f4cc02", "3d608690c438"]) {
      expect(covers(marathon?.bbox ?? [], eventById(m, id))).toBe(true);
      expect(during(marathon?.t ?? "", eventById(m, id))).toBe(true);
    }
    const r04 = eventById(
      recordedLive("closure_events_live_1107_1530").body.events,
      "2e930ec6deeb",
    );
    expect(covers(rally?.bbox ?? [], r04)).toBe(true);
    expect(during(rally?.t ?? "", r04)).toBe(true);
    const map = eventById(
      recordedLive("closure_events_live_1109_1330").body.events,
      "ccaa9980c6ac",
    );
    expect(covers(march?.bbox ?? [], map)).toBe(true);
    expect(during(march?.t ?? "", map)).toBe(true);
  });
});
