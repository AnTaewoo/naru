// recorded /route (2026-03-15 교보빌딩 → 대한문, INTERFACE v0.7): 07:45 는 광화문(세종문화회관) 지하보도
// 레그 coord_range [3, 8] (BE test_routers 와 같은 값), 04:30·13:30 은 지하보도 없음
import { describe, expect, it } from "vitest";
import { recordedClosures, recordedRoute } from "../../test/recorded";
import { COLORS } from "../colors";
import { ICON_IDS } from "../icons";
import {
  ROUTE_LAYER_IDS,
  avoidedLayers,
  avoidedPoints,
  baselineBounds,
  baselineLayers,
  baselineLine,
  crossingLayers,
  crossingSegments,
  entranceLayers,
  entranceMarkers,
  legCoordinates,
  legRange,
  routeBounds,
  routeLayers,
  routeLine,
  viewPaint,
  type LngLat,
} from "./routeLayer";

const ROUTES = ["route_0430", "route_0745", "route_1330", "route_1107_1500"] as const;

function lengthM(coords: LngLat[]): number {
  let total = 0;
  for (let k = 1; k < coords.length; k++) {
    const [lng1, lat1] = coords[k - 1] ?? [0, 0];
    const [lng2, lat2] = coords[k] ?? [0, 0];
    const p1 = (lat1 * Math.PI) / 180;
    const p2 = (lat2 * Math.PI) / 180;
    const h =
      Math.sin((p2 - p1) / 2) ** 2 +
      Math.cos(p1) * Math.cos(p2) * Math.sin(((lng2 - lng1) * Math.PI) / 180 / 2) ** 2;
    total += 2 * 6_371_008.8 * Math.asin(Math.sqrt(h));
  }
  return total;
}

describe("legs coord_range (ADR-009) — FE 에서 본 계약", () => {
  it("recorded 경로 셋 모두 레그가 좌표를 빈틈없이 나누고, 레그 선 길이 = 레그 거리 (1 m 안)", () => {
    for (const name of ROUTES) {
      const route = recordedRoute(name);
      const n = route.route.coordinates.length;
      let prevEnd = 0;
      for (const leg of route.legs) {
        const range = legRange(leg);
        expect(range).not.toBeNull();
        const [i, j] = range ?? [0, 0];
        expect(i).toBe(prevEnd);
        prevEnd = j;
        expect(Math.abs(lengthM(legCoordinates(route, leg)) - leg.distance_m)).toBeLessThanOrEqual(
          1,
        );
      }
      expect(prevEnd).toBe(n - 1);
      const sum = route.legs.reduce((s, leg) => s + leg.distance_m, 0);
      expect(Math.abs(sum - route.distance_m)).toBeLessThanOrEqual(1);
    }
  });
});

describe("routeLayer — 지하보도 구간·입구", () => {
  it("07:45 — 남색 터널 1개 = coordinates[3..8], 입구 = coordinates[3] (앞 계단 레그의 끝)", () => {
    const route = recordedRoute("route_0745");
    const segs = crossingSegments(route);
    expect(segs.features).toHaveLength(1);
    const seg = segs.features[0];
    expect(seg?.properties.kind).toBe("underpass");
    expect(seg?.properties.name).toBe("광화문(세종문화회관) 지하보도");
    expect(seg?.geometry.coordinates).toEqual(route.route.coordinates.slice(3, 9));
    expect(Math.abs(lengthM(seg?.geometry.coordinates ?? []) - 156.2)).toBeLessThan(1);
    const entrances = entranceMarkers(route);
    expect(entrances.features).toHaveLength(1);
    expect(entrances.features[0]?.geometry.coordinates).toEqual(route.route.coordinates[3]);
    const k = seg?.properties.leg_index ?? -1;
    const before = route.legs[k - 1];
    expect(before?.kind).toBe("stairs");
    expect(before && legRange(before)?.[1]).toBe(3);
  });

  it("지하보도가 없는 경로·경로 없음 → 비어 있다", () => {
    expect(crossingSegments(recordedRoute("route_1330")).features).toEqual([]);
    expect(entranceMarkers(recordedRoute("route_0430")).features).toEqual([]);
    expect(crossingSegments(null).features).toEqual([]);
    expect(entranceMarkers(null).features).toEqual([]);
  });

  it("레이어 스펙 — 남색 선 + 옅은 파랑 점선, 입구는 파란 계단 아이콘", () => {
    const [tunnel, dash] = crossingLayers();
    expect(tunnel?.id).toBe(ROUTE_LAYER_IDS.tunnel);
    if (tunnel?.type !== "line" || dash?.type !== "line") throw new Error("line 레이어");
    expect(tunnel.paint?.["line-color"]).toBe(COLORS.tunnel);
    expect(dash.paint?.["line-color"]).toBe(COLORS.tunnelDash);
    expect(dash.paint?.["line-dasharray"]).toEqual([3, 1.5]);
    const [entrance] = entranceLayers();
    if (entrance?.type !== "symbol") throw new Error("symbol 레이어");
    expect(entrance.layout?.["icon-image"]).toBe(ICON_IDS.entrance);
  });
});

// 같은 기록: 07:45·11/7 15:00 은 원래 길과 경로가 다르고, 04:30·13:30 은 둘이 같다 (기록을 열어 좌표 배열 비교)
describe("routeLayer — 경로 실선·원래 길 점선", () => {
  it("07:45 — 실선 = route.coordinates 28점, 점선 = baseline 31점", () => {
    const route = recordedRoute("route_0745");
    const line = routeLine(route);
    expect(line.features).toHaveLength(1);
    expect(line.features[0]?.geometry.coordinates).toEqual(route.route.coordinates);
    expect(line.features[0]?.geometry.coordinates).toHaveLength(28);
    expect(line.features[0]?.properties.role).toBe("route");
    const base = baselineLine(route);
    expect(base.features).toHaveLength(1);
    expect(base.features[0]?.geometry.coordinates).toEqual(route.baseline.route.coordinates);
    expect(base.features[0]?.geometry.coordinates).toHaveLength(31);
    expect(base.features[0]?.properties.role).toBe("baseline");
  });

  it("13:30 — 원래 길이 경로와 같으면 점선을 그리지 않는다. 경로 없음 → 둘 다 비었다", () => {
    const route = recordedRoute("route_1330");
    expect(routeLine(route).features).toHaveLength(1);
    expect(baselineLine(route).features).toEqual([]);
    // 04:30 은 창 밖이라 원래 길 그대로(ADR-011 A), 11/7 15:00 은 예정 집회를 피해 원래 길과 다르다
    expect(baselineLine(recordedRoute("route_0430")).features).toEqual([]);
    expect(baselineLine(recordedRoute("route_1107_1500")).features).toHaveLength(1);
    expect(routeLine(null).features).toEqual([]);
    expect(baselineLine(null).features).toEqual([]);
  });

  it("routeBounds — 경로와 원래 길 좌표를 모두 담는 [[서, 남], [동, 북]]", () => {
    const route = recordedRoute("route_0745");
    const b = routeBounds(route);
    expect(b).not.toBeNull();
    const [[w, sth], [e, n]] = b ?? [
      [0, 0],
      [0, 0],
    ];
    for (const c of [...route.route.coordinates, ...route.baseline.route.coordinates]) {
      const [lng, lat] = c as number[];
      expect(lng).toBeGreaterThanOrEqual(w);
      expect(lng).toBeLessThanOrEqual(e);
      expect(lat).toBeGreaterThanOrEqual(sth);
      expect(lat).toBeLessThanOrEqual(n);
    }
    expect(routeBounds(null)).toBeNull();
  });

  it("레이어 스펙 — 흰 테두리 위 파란 실선, 원래 길은 회색 점선(둥근 끝)", () => {
    const [casing, line] = routeLayers();
    if (casing?.type !== "line" || line?.type !== "line") throw new Error("line 레이어");
    expect(casing.id).toBe(ROUTE_LAYER_IDS.casing);
    expect(casing.paint?.["line-color"]).toBe("#ffffff");
    expect(line.id).toBe(ROUTE_LAYER_IDS.line);
    expect(line.paint?.["line-color"]).toBe(COLORS.blue);
    const [dots] = baselineLayers();
    if (dots?.type !== "line") throw new Error("line 레이어");
    expect(dots.id).toBe(ROUTE_LAYER_IDS.baseline);
    expect(dots.paint?.["line-color"]).toBe(COLORS.baseline);
    expect(dots.layout?.["line-cap"]).toBe("round");
    expect(dots.paint?.["line-dasharray"]).toBeDefined();
  });
});

describe("원래 길 보기 (T5.11)", () => {
  // recorded route_0745 avoided 2곳(confirmed) ↔ 같은 시각 closures_0745 의 점 (파일을 열어 확인)
  const r0745 = recordedRoute("route_0745");
  const fc0745 = recordedClosures("closures_0745");

  it("피한 횡단보도는 같은 시각 /closures 점에서 찾는다 — 못 찾으면 그리지 않는다", () => {
    const pts = avoidedPoints(r0745, fc0745);
    expect(pts.features.map((f) => [f.properties.crosswalk_id, f.properties.status])).toEqual([
      ["06-0000023206", "confirmed"],
      ["06-0000036391", "confirmed"],
    ]);
    expect(pts.features.map((f) => f.geometry.coordinates)).toEqual([
      [126.9771308, 37.5700504],
      [126.9769067, 37.5701284],
    ]);
    expect(avoidedPoints(recordedRoute("route_1330"), fc0745).features).toEqual([]);
    expect(avoidedPoints(r0745, { type: "FeatureCollection", features: [] }).features).toEqual([]);
    expect(avoidedPoints(null, fc0745).features).toEqual([]);
  });

  it("원래 길 범위는 원래 길 좌표만 — 경로와 원래 길을 다 담는 범위 안", () => {
    const b = baselineBounds(r0745);
    const all = routeBounds(r0745);
    if (!b || !all) throw new Error("범위 없음");
    expect(b[0][0]).toBeGreaterThanOrEqual(all[0][0]);
    expect(b[0][1]).toBeGreaterThanOrEqual(all[0][1]);
    expect(b[1][0]).toBeLessThanOrEqual(all[1][0]);
    expect(b[1][1]).toBeLessThanOrEqual(all[1][1]);
    expect(baselineBounds(null)).toBeNull();
  });

  it("원래 길을 고르면 원래 길 실선·굵게, 가장 빠른 길은 흐리게 — 둘러싼 원은 통제 중 빨강·공지상 주황", () => {
    const on = new Map(viewPaint(true).map(([id, prop, v]) => [`${id}|${prop}`, v]));
    const off = new Map(viewPaint(false).map(([id, prop, v]) => [`${id}|${prop}`, v]));
    expect(on.get(`${ROUTE_LAYER_IDS.line}|line-opacity`)).toBeLessThan(1);
    expect(off.get(`${ROUTE_LAYER_IDS.line}|line-opacity`)).toBe(1);
    expect(on.get(`${ROUTE_LAYER_IDS.baseline}|line-dasharray`)).toBeUndefined(); // 실선
    expect(off.get(`${ROUTE_LAYER_IDS.baseline}|line-dasharray`)).toEqual([0, 2]); // 점선
    const [halo] = avoidedLayers();
    expect(halo?.type).toBe("circle");
    expect(JSON.stringify(halo)).toContain(COLORS.stop);
    expect(JSON.stringify(halo)).toContain(COLORS.slow);
  });
});
