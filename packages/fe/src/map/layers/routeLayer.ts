// 순수 함수: /route 응답(RouteResponse) → 지하보도·육교 구간(남색 터널)과 그 입구 마커 (ADR-009)
// 레그의 coord_range [i, j] 로 route.coordinates 를 잘라 쓴다. 경로선·baseline 은 T5.2 에서 이 파일에 더한다
import type { LayerSpecification } from "maplibre-gl";
import type { Leg, LegKind, RouteResponse } from "../../types/contracts";
import { COLORS } from "../colors";
import { ICON_IDS } from "../icons";

export const ROUTE_CROSSING_SOURCE_ID = "naru-route-crossings";
export const ROUTE_ENTRANCE_SOURCE_ID = "naru-route-entrances";
export const ROUTE_LAYER_IDS = {
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
