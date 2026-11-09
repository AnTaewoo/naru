// 지금 지도 사건의 종류·칩·줌 단계 (T7.4) — 입력은 사건 v2 기록(scripts/record_live_events.py 가 실제 앱에서
// 받은 응답). 기대값은 기록을 열어 확인한 사건 id·status·시작·확신도 (data/MANIFEST.md 2026-11-09 재기록(T7.4))
import { describe, expect, it } from "vitest";
import { eventById, recordedLive } from "../test/recorded";
import { hhmm } from "../i18n/ko";
import {
  CHIP_KINDS,
  byDistrict,
  chipCounts,
  chipStatuses,
  districtChips,
  eventKind,
  listedEvents,
  sheetSections,
  zoomBand,
} from "./eventKinds";

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

describe("listedEvents — 시트 목록·시간표", () => {
  it("3/15 07:45 — 통제 중 9(시작 순) → 1시간 안 2 → 예정 5, 같은 05:00 은 이유 순", () => {
    const { body, atMs } = recordedLive("closure_events_live_0315_0745");
    const rows = listedEvents(body.events, atMs);
    expect(rows.map((r) => r.kind)).toEqual([
      ...Array<string>(9).fill("confirmed"),
      "soon",
      "soon",
      ...Array<string>(5).fill("scheduled"),
    ]);
    // 기록: 15구간·출발지 05:00, 11·14구간 07:10, 1구간 07:20 … 4구간 08:17(1시간 안) … 10구간 09:12
    expect(rows[0]?.event.id).toBe("5f206eb9e97c"); // marathon 15구간 < marathon 출발지
    expect(rows[1]?.event.id).toBe("3d608690c438");
    expect(rows[9]?.event.id).toBe("cffcce1130c0");
    expect(rows.at(-1)?.event.id).toBe("e1d0e06932a8");
  });

  it("11/7 15:30 — r05 0.65 는 목록에 없다(13 → 12), 11/9 13:30 해제 하나증권도 없다(5 → 4)", () => {
    const a = recordedLive("closure_events_live_1107_1530");
    const ids = listedEvents(a.body.events, a.atMs).map((r) => r.event.id);
    expect(ids).toHaveLength(12);
    expect(ids).not.toContain("3f036e3f24e0");
    const b = recordedLive("closure_events_live_1109_1330");
    expect(listedEvents(b.body.events, b.atMs).map((r) => r.event.id)).not.toContain(
      "1deaa20a0218",
    );
    // 지도에서 고른 묶음은 흐린 사건도 (withLow) — 해제는 여전히 없다
    expect(listedEvents(a.body.events, a.atMs, true).map((r) => r.event.id)).toContain(
      "3f036e3f24e0",
    );
  });
});

describe("시트 묶음(지도 사건만일 때)·구 칩 (T7.5 → T7.12)", () => {
  it("3/15 07:45 — 지금 11(통제 중 9 + 1시간 안 2) · 다가오는 3/15 다섯 · 지난 없음", () => {
    // 기록 16건: confirmed 9 · scheduled 7(08:17·08:29 는 08:45 안, 08:46~09:12 다섯은 그 뒤), 모두 3/15
    const { body, atMs } = recordedLive("closure_events_live_0315_0745");
    const { now, upcoming, past } = sheetSections(body.events, atMs);
    expect(now).toHaveLength(11);
    expect(upcoming.map((g) => [g.day, g.items.length])).toEqual([["2026-03-15", 5]]);
    expect(past).toEqual([]);
  });

  it("11/8 20:00 — 다음 날 11/9 통제 다섯(하나증권 10:30 · 국회대로 11:00 둘 · 강남대로 14:00 둘)은 11/9 한 묶음", () => {
    const { body, atMs } = recordedLive("closure_events_live_1108_2000");
    const { now, upcoming } = sheetSections(body.events, atMs);
    expect(now).toEqual([]);
    expect(upcoming.map((g) => g.day)).toEqual(["2026-11-09"]);
    const [day] = upcoming;
    expect(day?.items.map((r) => hhmm(r.event.window.start))).toEqual([
      "10:30",
      "11:00",
      "11:00",
      "14:00",
      "14:00",
    ]);
    expect(day?.items[0]?.event.id).toBe("1deaa20a0218");
  });

  it("11/7 15:30 구 칩 — 광화문 화면과 겹치는 사건의 구(종로구·중구 각 5) 먼저, 나머지 가나다", () => {
    const { body, atMs } = recordedLive("closure_events_live_1107_1530");
    const listed = listedEvents(body.events, atMs).map((r) => r.event); // r05 0.65 빼고 12
    const view: [number, number, number, number] = [126.965, 37.555, 126.99, 37.58]; // DEFAULT_BBOX
    expect(districtChips(listed, view)).toEqual(["종로구", "중구", "강남구", "서초구", "영등포구"]);
    expect(districtChips(listed, null)).toEqual(["강남구", "서초구", "영등포구", "종로구", "중구"]);
    // 영등포구 = 돌발 여의대로 08:03(통제 중) · 경찰청 r06 의사당역 16:00(1시간 안) — 목록 순서 그대로
    expect(byDistrict(listed, "영등포구").map((e) => e.id)).toEqual([
      "86f1c51ec2de",
      "a1199bc3db1d",
    ]);
    expect(byDistrict(listed, null)).toHaveLength(12);
  });
});

// T7.12 시트 세 묶음 — 넓은 창 기록(at 앞뒤 365일, scripts/record_live_events.py)을 열어 확인한 사건 id·창
describe("sheetSections — 지금·다가오는 통제·지난 통제 (T7.12)", () => {
  it("11/7 15:30 — 지금 12(통제 중 8·1시간 안 4, 0.65 뺌) · 다가오는 11/9 다섯 · 지난 3/15 마라톤 16(늦게 끝난 것부터)", () => {
    const { body, atMs } = recordedLive("closure_events_catalog_1107_1530");
    const { now, upcoming, past } = sheetSections(body.events, atMs);
    expect(now.map((r) => r.kind)).toEqual([
      ...Array<string>(8).fill("confirmed"),
      ...Array<string>(4).fill("soon"),
    ]);
    expect(upcoming.map((d) => [d.day, d.items.length])).toEqual([["2026-11-09", 5]]);
    expect(upcoming[0]?.items[0]?.event.id).toBe("1deaa20a0218"); // 하나증권 10:30
    expect(past).toHaveLength(16);
    expect(past[0]?.event.id).toBe("5f206eb9e97c"); // 15구간 ~14:30
    expect(past.at(-1)?.event.window.end).toBe("2026-03-15T08:08:00+09:00"); // 1구간
  });

  it("11/8 12:00 — 그 시각 걸린 통제 없음, 다가오는 11/9 다섯, 지난 28(11/7 19:00 끝 r06 부터)", () => {
    const { body, atMs } = recordedLive("closure_events_catalog_1108_1200");
    const { now, upcoming, past } = sheetSections(body.events, atMs);
    expect(now).toEqual([]);
    expect(upcoming.map((d) => [d.day, d.items.length])).toEqual([["2026-11-09", 5]]);
    expect(past).toHaveLength(28);
    expect(past[0]?.event.id).toBe("a1199bc3db1d"); // 경찰청 r06 16:00~19:00
    expect(past.map((r) => r.event.id)).toContain("2e930ec6deeb"); // r04
    // 지도에서 고른 묶음엔 흐린 사건도 — 0.65 r05 가 지난 쪽에
    expect(sheetSections(body.events, atMs, true).past).toHaveLength(29);
  });
});
