// recorded /closures (2026-03-15 광화문 bbox). 07:45 는 후보×횡단보도 79건이 횡단보도 64곳 — 12곳이 두 구간에 걸린다
// (2026-11-08 recorded 를 열어 확인). 곳 단위로 확인 45 · 예정 19. 04:30 예정 5곳, 13:30 없음
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
  it("07:45 — 횡단보도 64곳(후보×횡단보도 79건), 확인 45 빨강 ×, 예정 19 노랑 !", () => {
    const fc = recordedClosures("closures_0745");
    expect(fc.features).toHaveLength(79);
    const pts = closurePoints(fc);
    expect(pts.features).toHaveLength(64);
    expect(new Set(pts.features.map((f) => f.properties.crosswalk_id)).size).toBe(64);
    expect(pts.features.reduce((n, f) => n + f.properties.candidates, 0)).toBe(79);
    expect(pts.features.filter((f) => f.properties.candidates > 1)).toHaveLength(12);
    const by = countByStatus(fc);
    expect(by.confirmed).toBe(45);
    expect(by.scheduled).toBe(19);
    const confirmed = pts.features.filter((f) => f.properties.status === "confirmed");
    expect(confirmed).toHaveLength(45);
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

  it("겹친 횡단보도 — 가장 무거운 상태, 같은 무게면 늦게 풀리는 쪽", () => {
    const fc = recordedClosures("closures_0745");
    const raw = new Map<string, { status: string; end: string | null }[]>();
    for (const f of fc.features) {
      const p = f.properties;
      const list = raw.get(p.crosswalk_id ?? "") ?? [];
      list.push({ status: p.status, end: (p.window["end"] as string | null) ?? null });
      raw.set(p.crosswalk_id ?? "", list);
    }
    for (const f of closurePoints(fc).features) {
      const all = raw.get(f.properties.crosswalk_id) ?? [];
      expect(all).toHaveLength(f.properties.candidates);
      if (all.some((x) => x.status === "confirmed")) {
        expect(f.properties.status).toBe("confirmed");
        const ends = all.filter((x) => x.status === "confirmed").map((x) => x.end ?? "");
        expect(f.properties.window_end).toBe([...ends].sort().at(-1));
      }
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

  it("칩 필터 → 상태 in 필터 — 칩을 다 끄면 아무것도 안 그린다(T7.4), 칩이 없으면 null(전부)", () => {
    expect(statusFilter(["confirmed", "scheduled"])).toEqual([
      "in",
      ["get", "status"],
      ["literal", ["confirmed", "scheduled"]],
    ]);
    expect(statusFilter([])).toEqual(["in", ["get", "status"], ["literal", []]]);
    expect(statusFilter(undefined)).toBeNull();
  });

  it("횡단보도 점은 줌 15 부터, 해제·확신도 0.7 미만은 흐리게 (T7.4 줌 3단계)", () => {
    const [dot, mark] = closureLayers();
    expect(dot?.minzoom).toBe(15);
    expect(mark?.minzoom).toBe(15);
    if (dot?.type !== "circle") throw new Error("circle 레이어");
    expect(dot.paint?.["circle-opacity"]).toEqual([
      "case",
      ["==", ["get", "status"], "released"],
      0.45,
      ["<", ["get", "confidence"], 0.7],
      0.45,
      0.95,
    ]);
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
