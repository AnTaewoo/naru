// 순수 함수: /route 응답(RouteResponse) → 경로 파란 실선 · 원래 길(baseline) 회색 점선 · 지하보도·육교 구간
// (남색 터널)과 그 입구 마커. 시안 02 범례. 터널은 레그의 coord_range [i, j] 로 route.coordinates 를 자른다 (ADR-009)
import type { LayerSpecification } from "maplibre-gl";
import type { Leg, LegKind, LineString, RouteResponse } from "../../types/contracts";
import { COLORS } from "../colors";
import { ICON_IDS } from "../icons";

export const ROUTE_LINE_SOURCE_ID = "naru-route-line";
export const ROUTE_BASELINE_SOURCE_ID = "naru-route-baseline";
export const ROUTE_CROSSING_SOURCE_ID = "naru-route-crossings";
export const ROUTE_ENTRANCE_SOURCE_ID = "naru-route-entrances";
export const ROUTE_LAYER_IDS = {
  baseline: "naru-route-baseline",
  casing: "naru-route-casing",
  line: "naru-route-line",
  tunnel: "naru-route-tunnel",
  tunnelDash: "naru-route-tunnel-dash",
  entrance: "naru-route-entrance",
} as const;

/** 길을 건너는 구조물 레그 — 그 범위를 남색 터널로, 시작점에 입구 마커 */
export const CROSSING_KINDS: readonly LegKind[] = ["underpass", "overpass"];

export type LngLat = [number, number];

export interface CrossingFeature {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: LngLat[] };
  properties: { kind: LegKind; name: string; leg_index: number; distance_m: number };
}

export interface LineFeature {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: LngLat[] };
  properties: { role: "route" | "baseline"; duration_s: number; distance_m: number };
}

export interface EntranceFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: LngLat };
  properties: { kind: LegKind; name: string; leg_index: number };
}

export interface Collection<F> {
  type: "FeatureCollection";
  features: F[];
}

function toLngLat(c: unknown): LngLat | null {
  if (!Array.isArray(c)) return null;
  const [lng, lat] = c as unknown[];
  return typeof lng === "number" && typeof lat === "number" ? [lng, lat] : null;
}

/** LineString 좌표 — 생성 타입이 [unknown, unknown] 이라 숫자만 남긴다 */
export function lineCoordinates(line: LineString): LngLat[] {
  const out: LngLat[] = [];
  for (const c of line.coordinates) {
    const p = toLngLat(c);
    if (p) out.push(p);
  }
  return out;
}

function lineFeature(
  role: LineFeature["properties"]["role"],
  coordinates: LngLat[],
  durationS: number,
  distanceM: number,
): LineFeature {
  return {
    type: "Feature",
    geometry: { type: "LineString", coordinates },
    properties: { role, duration_s: durationS, distance_m: distanceM },
  };
}

/** 지금 갈 수 있는 가장 빠른 길 — 파란 실선 */
export function routeLine(route: RouteResponse | null): Collection<LineFeature> {
  const coords = route ? lineCoordinates(route.route) : [];
  if (!route || coords.length < 2) return { type: "FeatureCollection", features: [] };
  return {
    type: "FeatureCollection",
    features: [lineFeature("route", coords, route.duration_s, route.distance_m)],
  };
}

function sameLine(a: LngLat[], b: LngLat[]): boolean {
  return a.length === b.length && a.every((p, k) => p[0] === b[k]?.[0] && p[1] === b[k]?.[1]);
}

/** 원래 최단 경로(통제를 끈 경로) — 회색 점선. 지금 경로와 같으면 그리지 않는다 */
export function baselineLine(route: RouteResponse | null): Collection<LineFeature> {
  if (!route) return { type: "FeatureCollection", features: [] };
  const coords = lineCoordinates(route.baseline.route);
  if (coords.length < 2 || sameLine(coords, lineCoordinates(route.route))) {
    return { type: "FeatureCollection", features: [] };
  }
  const b = route.baseline;
  return {
    type: "FeatureCollection",
    features: [lineFeature("baseline", coords, b.duration_s, b.distance_m)],
  };
}

/**
 * 경로의 첫·끝 좌표 = 출발·도착 (ADR-009 접근 구간 포함). 새 출발·도착의 첫 경로를 알아본다 —
 * 지도 맞춤(MapView)·시트 접기(RouteCard)가 같은 키를 쓴다 (T5.6)
 */
export function routeOdKey(route: RouteResponse | null): string | null {
  const coords = route ? lineCoordinates(route.route) : [];
  return coords.length ? JSON.stringify([coords[0], coords[coords.length - 1]]) : null;
}

/** 경로와 원래 길을 모두 담는 [[서, 남], [동, 북]] — 지도를 맞출 때 */
export function routeBounds(route: RouteResponse | null): [LngLat, LngLat] | null {
  if (!route) return null;
  const all = [...lineCoordinates(route.route), ...lineCoordinates(route.baseline.route)];
  if (all.length === 0) return null;
  const lngs = all.map((p) => p[0]);
  const lats = all.map((p) => p[1]);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}

/** 레그의 [i, j] (ADR-009). 생성 타입이 unknown 이라 여기서 숫자를 확인한다 */
export function legRange(leg: Leg): [number, number] | null {
  const [i, j] = leg.coord_range;
  return typeof i === "number" && typeof j === "number" && i <= j ? [i, j] : null;
}

/** route.coordinates[i..j] — 그 레그의 선 */
export function legCoordinates(route: RouteResponse, leg: Leg): LngLat[] {
  const range = legRange(leg);
  if (!range) return [];
  const out: LngLat[] = [];
  for (const c of route.route.coordinates.slice(range[0], range[1] + 1)) {
    const p = toLngLat(c);
    if (p) out.push(p);
  }
  return out;
}

function isCrossing(leg: Leg): boolean {
  return CROSSING_KINDS.includes(leg.kind);
}

export function crossingSegments(route: RouteResponse | null): Collection<CrossingFeature> {
  const features: CrossingFeature[] = [];
  route?.legs.forEach((leg, k) => {
    if (!isCrossing(leg)) return;
    const coordinates = legCoordinates(route, leg);
    if (coordinates.length < 2) return;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates },
      properties: {
        kind: leg.kind,
        name: leg.name ?? "",
        leg_index: k,
        distance_m: leg.distance_m,
      },
    });
  });
  return { type: "FeatureCollection", features };
}

/** 입구 = 지하보도·육교 레그의 시작점 coordinates[i] (앞 계단·엘리베이터 레그의 끝과 같은 점) */
export function entranceMarkers(route: RouteResponse | null): Collection<EntranceFeature> {
  const features: EntranceFeature[] = [];
  route?.legs.forEach((leg, k) => {
    if (!isCrossing(leg)) return;
    const first = legCoordinates(route, leg)[0];
    if (!first) return;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: first },
      properties: { kind: leg.kind, name: leg.name ?? "", leg_index: k },
    });
  });
  return { type: "FeatureCollection", features };
}

/** 남색 터널: 굵은 남색 선 + 그 위 옅은 파랑 점선 (시안 02) */
export function crossingLayers(sourceId: string = ROUTE_CROSSING_SOURCE_ID): LayerSpecification[] {
  return [
    {
      id: ROUTE_LAYER_IDS.tunnel,
      type: "line",
      source: sourceId,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": COLORS.tunnel,
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 4, 17, 9],
      },
    },
    {
      id: ROUTE_LAYER_IDS.tunnelDash,
      type: "line",
      source: sourceId,
      layout: { "line-join": "round" },
      paint: {
        "line-color": COLORS.tunnelDash,
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1.5, 17, 3],
        "line-dasharray": [3, 1.5],
      },
    },
  ];
}

/** 입구 마커: 파란 계단 아이콘 (icons.ts) */
export function entranceLayers(sourceId: string = ROUTE_ENTRANCE_SOURCE_ID): LayerSpecification[] {
  return [
    {
      id: ROUTE_LAYER_IDS.entrance,
      type: "symbol",
      source: sourceId,
      layout: {
        "icon-image": ICON_IDS.entrance,
        "icon-size": ["interpolate", ["linear"], ["zoom"], 13, 0.6, 17, 1],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    },
  ];
}

/** 경로: 흰 테두리 위 파란 실선 (시안 02) */
export function routeLayers(sourceId: string = ROUTE_LINE_SOURCE_ID): LayerSpecification[] {
  return [
    {
      id: ROUTE_LAYER_IDS.casing,
      type: "line",
      source: sourceId,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#ffffff",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 6, 17, 13],
      },
    },
    {
      id: ROUTE_LAYER_IDS.line,
      type: "line",
      source: sourceId,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": COLORS.blue,
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 3.5, 17, 8],
      },
    },
  ];
}

/** 원래 길: 회색 점선 — 길이 0 대시 + 둥근 끝으로 점을 찍는다 */
export function baselineLayers(sourceId: string = ROUTE_BASELINE_SOURCE_ID): LayerSpecification[] {
  return [
    {
      id: ROUTE_LAYER_IDS.baseline,
      type: "line",
      source: sourceId,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": COLORS.baseline,
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 3, 17, 5],
        "line-dasharray": [0, 2],
      },
    },
  ];
}
