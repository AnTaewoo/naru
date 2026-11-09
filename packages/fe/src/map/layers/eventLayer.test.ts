// 지금 지도 사건 레이어 (T7.4) — 입력은 사건 v2 기록(scripts/record_live_events.py 가 실제 앱에서 받은 응답).
// 기대값은 기록을 열어 확인한 사건 id·centroid·area (data/MANIFEST.md 2026-11-09 재기록(T7.4))
import { describe, expect, it } from "vitest";
import { eventById, recordedLive } from "../../test/recorded";
import { COLORS } from "../colors";
import { CHIP_KINDS } from "../eventKinds";
import { countFromIconId, countLabel } from "../icons";
import { EVENT_LAYER_IDS, eventAreas, eventLayers, eventPoints } from "./eventLayer";

describe("eventPoints", () => {
  const { body, atMs } = recordedLive("closure_events_live_1107_1530");

  it("중심점 — 클러스터 색은 그 안의 가장 작은 sev(통제 중 0 · 1시간 안 1 · 예정 2 · 예정 구역 3 · 흐림 4)", () => {
    const pts = eventPoints(body.events, atMs, CHIP_KINDS);
    expect(pts.features).toHaveLength(13);
    const sev = new Map(pts.features.map((f) => [f.properties.id, f.properties.sev]));
    expect(sev.get("159e13bfe71a")).toBe(0); // 돌발 사직로 통제 중
    expect(sev.get("a1199bc3db1d")).toBe(1);
    expect(sev.get("3f036e3f24e0")).toBe(4); // 0.65
    const first = pts.features.find((f) => f.properties.id === "159e13bfe71a");
    expect(first?.geometry.coordinates).toEqual([126.970584, 37.576]); // 기록의 centroid 그대로
    expect(first?.properties.color).toBe(COLORS.stop);
    expect(first?.properties.noArea).toBe(false);
    const low = pts.features.find((f) => f.properties.id === "3f036e3f24e0");
    expect(low?.properties).toMatchObject({ low: true, color: COLORS.gray });
  });

  it("칩 = 필터 — 꺼진 종류는 중심점에서 빠진다(클러스터 개수도 소스에서 센다)", () => {
    expect(eventPoints(body.events, atMs, ["confirmed"]).features).toHaveLength(8);
    expect(eventPoints(body.events, atMs, ["scheduled"]).features).toHaveLength(5); // 0.65 포함
    expect(eventPoints(body.events, atMs, []).features).toHaveLength(0);
  });

  it("11/9 13:30 — 해제(하나증권 r01)는 그리지 않는다", () => {
    const live = recordedLive("closure_events_live_1109_1330");
    const ids = eventPoints(live.body.events, live.atMs, CHIP_KINDS).features.map(
      (f) => f.properties.id,
    );
    expect(ids).toHaveLength(4);
    expect(ids).not.toContain("1deaa20a0218");
  });
});

describe("eventAreas", () => {
  const { body, atMs } = recordedLive("closure_events_live_1107_1530");

  it("구역 — 기록의 Polygon 그대로, 1시간 안은 진한 주황, 0.7 미만은 회색", () => {
    const areas = eventAreas(body.events, atMs, CHIP_KINDS);
    expect(areas.features).toHaveLength(13);
    const area = areas.features.find((f) => f.properties.id === "2e930ec6deeb");
    expect(area?.geometry).toEqual(eventById(body.events, "2e930ec6deeb").area); // 시의회~숭례문R 22곳
    expect(area?.properties).toMatchObject({ kind: "soon", color: COLORS.soon, low: false });
    const low = areas.features.find((f) => f.properties.id === "3f036e3f24e0");
    expect(low?.properties).toMatchObject({ kind: "soon", color: COLORS.gray, low: true });
  });

  it("칩 = 필터 — 구역도 켜진 종류만, 해제는 없다", () => {
    expect(eventAreas(body.events, atMs, ["scheduled"]).features).toHaveLength(5);
    const live = recordedLive("closure_events_live_1109_1330");
    expect(eventAreas(live.body.events, live.atMs, CHIP_KINDS).features).toHaveLength(4);
  });
});

describe("eventLayers·개수 아이콘", () => {
  it("레이어 — 구역은 12 부터, 클러스터·점은 12 까지, 구역이 없는 사건은 12 부터 점으로", () => {
    const byId = new Map(eventLayers().map((l) => [l.id, l]));
    expect(byId.get(EVENT_LAYER_IDS.areaFill)?.minzoom).toBe(12);
    expect(byId.get(EVENT_LAYER_IDS.areaLine)?.minzoom).toBe(12);
    expect(byId.get(EVENT_LAYER_IDS.cluster)?.maxzoom).toBe(12);
    expect(byId.get(EVENT_LAYER_IDS.count)?.maxzoom).toBe(12);
    expect(byId.get(EVENT_LAYER_IDS.dot)?.maxzoom).toBe(12);
    expect(byId.get(EVENT_LAYER_IDS.dotNoArea)?.minzoom).toBe(12);
  });

  it("클러스터 개수 아이콘 id 는 naru-n-<개수>, 100 부터 99+ (사건 상한 300)", () => {
    expect(countFromIconId("naru-n-13")).toBe(13); // 11/7 15:30 사건 13 이 한 묶음일 때
    expect(countFromIconId("naru-x")).toBeNull();
    expect(countFromIconId("naru-n-0")).toBeNull();
    expect(countLabel(16)).toBe("16");
    expect(countLabel(300)).toBe("99+");
  });
});
