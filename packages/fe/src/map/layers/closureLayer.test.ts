// recorded /closures (2026-03-15 광화문 bbox: 04:30 예정 5 · 07:45 확인 55+예정 24 · 13:30 없음)
import { describe, expect, it } from "vitest";
import { recordedClosures } from "../../test/recorded";
import { COLORS } from "../colors";
import { ICON_IDS } from "../icons";
import { statusFilter } from "../MapView";
import {
  CLOSURE_LAYER_IDS,
  closureLayers,
  closurePoints,
  closureSource,
  countByStatus,
} from "./closureLayer";
import { ZONE_LAYER_IDS, zoneLayers, zonePolygons } from "./zoneLayer";

describe("closureLayer", () => {
  it("07:45 — feature 79, 확인 55 빨강 ×, 예정 24 노랑 !", () => {
    const fc = recordedClosures("closures_0745");
    const pts = closurePoints(fc);
    expect(pts.features).toHaveLength(79);
    const by = countByStatus(fc);
    expect(by.confirmed).toBe(55);
    expect(by.scheduled).toBe(24);
    const confirmed = pts.features.filter((f) => f.properties.status === "confirmed");
    expect(confirmed).toHaveLength(55);
    expect(new Set(confirmed.map((f) => f.properties.color))).toEqual(new Set([COLORS.stop]));
    expect(new Set(confirmed.map((f) => f.properties.icon))).toEqual(new Set([ICON_IDS.x]));
    const scheduled = pts.features.filter((f) => f.properties.status === "scheduled");
    expect(new Set(scheduled.map((f) => f.properties.color))).toEqual(new Set([COLORS.slow]));
    expect(new Set(scheduled.map((f) => f.properties.icon))).toEqual(new Set([ICON_IDS.bang]));
    for (const f of pts.features) {
      const [lng, lat] = f.geometry.coordinates;
      expect(lng).toBeGreaterThan(126.965);
      expect(lng).toBeLessThan(126.99);
      expect(lat).toBeGreaterThan(37.555);
      expect(lat).toBeLessThan(37.58);
      expect(f.properties.crosswalk_id.startsWith("06-")).toBe(true);
      expect(f.properties.reason.startsWith("marathon ")).toBe(true);
    }
  });

  it("04:30 — 예정 5 (출발지 구간 05:00~, 60분 지평) · 13:30 — 없음", () => {
    const early = closurePoints(recordedClosures("closures_0430"));
    expect(early.features).toHaveLength(5);
    expect(early.features.every((f) => f.properties.status === "scheduled")).toBe(true);
    expect(closurePoints(recordedClosures("closures_1330")).features).toEqual([]);
  });

  it("source/layer 스펙 — geojson 소스 하나, 점(상태색 data-driven) + 아이콘 표식 2장", () => {
    const src = closureSource(recordedClosures("closures_0745"));
    expect(src.type).toBe("geojson");
    const [dot, mark, ...rest] = closureLayers();
    expect(rest).toEqual([]);
    expect(dot?.id).toBe(CLOSURE_LAYER_IDS.dot);
    expect(mark?.id).toBe(CLOSURE_LAYER_IDS.mark);
    if (dot?.type !== "circle") throw new Error("dot 은 circle 레이어");
    expect(dot.paint?.["circle-color"]).toEqual(["get", "color"]);
    if (mark?.type !== "symbol") throw new Error("mark 는 symbol 레이어");
    expect(mark.layout?.["icon-image"]).toEqual(["get", "icon"]);
    expect(mark.layout?.["text-field"]).toBeUndefined(); // 글리프 서버 없이
  });

  it("칩 필터 → 상태 in 필터, 비면 null(전부)", () => {
    expect(statusFilter(["confirmed", "scheduled"])).toEqual([
      "in",
      ["get", "status"],
      ["literal", ["confirmed", "scheduled"]],
    ]);
    expect(statusFilter([])).toBeNull();
    expect(statusFilter(undefined)).toBeNull();
  });

  it("zoneLayer — 기록에 Polygon 이 없으면 비고, 레이어 스펙은 보라 빗금 + 점선", () => {
    expect(zonePolygons(recordedClosures("closures_0745")).features).toEqual([]);
    const [fill, line] = zoneLayers();
    expect(fill?.id).toBe(ZONE_LAYER_IDS.fill);
    if (fill?.type !== "fill") throw new Error("fill 레이어");
    expect(fill.paint?.["fill-pattern"]).toBe(ICON_IDS.hatch);
    if (line?.type !== "line") throw new Error("line 레이어");
    expect(line.paint?.["line-color"]).toBe(COLORS.zone);
  });
});
