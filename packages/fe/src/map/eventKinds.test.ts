// 지금 지도 사건의 종류·칩·줌 단계 (T7.4) — 입력은 사건 v2 기록(scripts/record_live_events.py 가 실제 앱에서
// 받은 응답). 기대값은 기록을 열어 확인한 사건 id·status·시작·확신도 (data/MANIFEST.md 2026-11-09 재기록(T7.4))
import { describe, expect, it } from "vitest";
import { eventById, recordedLive } from "../test/recorded";
import { CHIP_KINDS, chipCounts, chipStatuses, eventKind, zoomBand } from "./eventKinds";

describe("eventKind·chipCounts", () => {
  it("11/7 15:30 — 통제 중 8, 예정 5 는 다 1시간 안(16:00 시작 하나 + 이미 시작했는데 근거 없는 넷)", () => {
    const { body, atMs } = recordedLive("closure_events_live_1107_1530");
    const kinds = new Map(body.events.map((e) => [e.id, eventKind(e, atMs)]));
    expect([...kinds.values()].filter((k) => k === "confirmed")).toHaveLength(8);
    expect(kinds.get("a1199bc3db1d")).toBe("soon"); // 경찰청 r06 16:00 — 30분 뒤
    expect(kinds.get("be5f89a4ebf3")).toBe("soon"); // r01 12:00 시작, 공지뿐이라 예정
    expect([...kinds.values()].filter((k) => k === "soon")).toHaveLength(5);
    // r05 내자R~사직공원 0.65 — 지도에는 흐리게, 칩 수에는 안 센다
    expect(eventById(body.events, "3f036e3f24e0").confidence).toBe(0.65);
    expect(chipCounts(body.events, atMs)).toEqual({ confirmed: 8, scheduled: 4, zone: 0 });
  });

  it("3/15 07:45 마라톤 — 예정 7 중 08:45 까지 시작하는 둘(4·5구간)만 1시간 안", () => {
    const { body, atMs } = recordedLive("closure_events_live_0315_0745");
    const soon = body.events.filter((e) => eventKind(e, atMs) === "soon").map((e) => e.id);
    expect(soon.sort()).toEqual(["7b8097f506bf", "cffcce1130c0"]); // 08:29·08:17
    // 6구간 08:46 은 61분 뒤 — 오늘 예정
    expect(eventKind(eventById(body.events, "22938eac16b6"), atMs)).toBe("scheduled");
    expect(chipCounts(body.events, atMs)).toEqual({ confirmed: 9, scheduled: 7, zone: 0 });
  });

  it("11/9 13:30 — 해제(하나증권 r01 13:00 끝)는 세지 않는다", () => {
    const { body, atMs } = recordedLive("closure_events_live_1109_1330");
    expect(eventKind(eventById(body.events, "1deaa20a0218"), atMs)).toBe("released");
    expect(chipCounts(body.events, atMs)).toEqual({ confirmed: 2, scheduled: 2, zone: 0 });
  });
});

describe("칩·줌 단계", () => {
  it("칩은 /closures 상태로 — 예정 구역은 zone_scheduled", () => {
    expect(chipStatuses(CHIP_KINDS)).toEqual(["confirmed", "scheduled", "zone_scheduled"]);
    expect(chipStatuses([])).toEqual([]);
  });

  it("줌 3단계 — 12 아래 클러스터, 12~15 구역, 15 부터 횡단보도", () => {
    expect([10, 11.99, 12, 14.99, 15, 17].map(zoomBand)).toEqual([
      "cluster",
      "cluster",
      "area",
      "area",
      "crosswalk",
      "crosswalk",
    ]);
  });
});
