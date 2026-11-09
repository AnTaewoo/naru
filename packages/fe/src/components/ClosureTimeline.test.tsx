// 미니 시간표 막대 (순수) — 사건 v2 기록(scripts/record_live_events.py). ClosureSheet.test 에서 옮김 (T7.5)
import { describe, expect, it } from "vitest";
import { COLORS } from "../map/colors";
import { recordedLive } from "../test/recorded";
import { timelineBars } from "./ClosureTimeline";

const live0745 = recordedLive("closure_events_live_0315_0745");

describe("timelineBars (순수)", () => {
  it("3/15 07:45 — 시트 목록과 같은 사건 16, 1구간 07:20~08:08 막대·통제 중 빨강", () => {
    const bars = timelineBars(live0745.body.events, live0745.atMs, "2026-03-15T00:00:00+09:00");
    expect(bars).toHaveLength(16);
    const seg1 = bars.find((b) => b.key === "adaea2f4cc02"); // 기록: marathon 1구간 07:20–08:08
    expect(seg1?.title).toBe("마라톤 1구간 세종대로 사거리~숭례문 오거리");
    expect(seg1?.color).toBe(COLORS.stop);
    expect(seg1?.leftPct).toBeCloseTo(((7 * 60 + 20) / (24 * 60)) * 100, 3);
    expect(seg1?.widthPct).toBeCloseTo((48 / (24 * 60)) * 100, 3);
    // 다른 날이면 막대 없음 — 3/15 사건을 3/16 축에
    expect(timelineBars(live0745.body.events, live0745.atMs, "2026-03-16T00:00:00+09:00")).toEqual(
      [],
    );
  });
});
