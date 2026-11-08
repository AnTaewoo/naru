// recorded /route (2026-03-15 교보빌딩 → 대한문, INTERFACE v0.7): 07:45 는 광화문(세종문화회관) 지하보도
// 레그 coord_range [3, 8] (BE test_routers 와 같은 값), 04:30·13:30 은 지하보도 없음
import { describe, expect, it } from "vitest";
import { recordedRoute } from "../../test/recorded";
import { COLORS } from "../colors";
import { ICON_IDS } from "../icons";
import {
  ROUTE_LAYER_IDS,
  crossingLayers,
  crossingSegments,
  entranceLayers,
  entranceMarkers,
  legCoordinates,
  legRange,
  type LngLat,
} from "./routeLayer";

const ROUTES = ["route_0430", "route_0745", "route_1330"] as const;

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
