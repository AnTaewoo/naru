// 순수 함수: 지금 지도 사건(/closures/events v0.14) → 클러스터용 중심점·통제 구역 + MapLibre 레이어 스펙
// (T7.4, ADR-014 A). 줌 12 아래 사건 중심점 클러스터, 12 부터 구역(BE 가 접수 때 만든 area), 15 부터 횡단보도
// 점(closureLayer). 공간 연산은 하지 않는다 — 구역·중심은 BE 값 그대로 (CLAUDE.md §3-5)
import type {
  CircleLayerSpecification,
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSourceSpecification,
  LayerSpecification,
} from "maplibre-gl";
import type { ClosureEvent } from "../../types/contracts";
import { COLORS } from "../colors";
import {
  AREA_MIN_ZOOM,
  CHIP_KINDS,
  KIND_COLOR,
  chipOf,
  eventKind,
  isLow,
  type ChipKind,
  type EventKind,
} from "../eventKinds";
import { COUNT_ICON_PREFIX } from "../icons";

export const EVENT_POINT_SOURCE_ID = "naru-events-points";
export const EVENT_AREA_SOURCE_ID = "naru-events-areas";

/** 클러스터 색은 그 안에서 가장 작은 sev — 통제 중 0 · 1시간 안 1 · 예정 2 · 예정 구역 3 · 흐림 4 */
const SEV: Record<EventKind, number> = {
  confirmed: 0,
  soon: 1,
  scheduled: 2,
  zone: 3,
  released: 5,
};
export const LOW_SEV = 4;

interface Shown {
  event: ClosureEvent;
  kind: EventKind;
  low: boolean;
  color: string;
}

/** 칩이 켜진 종류만, 해제는 그리지 않는다 */
function shown(
  events: readonly ClosureEvent[],
  atMs: number,
  visible: readonly ChipKind[],
): Shown[] {
  const on = new Set(visible);
  const out: Shown[] = [];
  for (const event of events) {
    const kind = eventKind(event, atMs);
    const chip = chipOf(kind);
    if (chip === null || !on.has(chip)) continue;
    const low = isLow(event);
    out.push({ event, kind, low, color: low ? COLORS.gray : KIND_COLOR[kind] });
  }
  return out;
}

export interface EventPointProps {
  id: string;
  kind: EventKind;
  low: boolean;
  sev: number;
  color: string;
  /** 구역이 없는 사건(T7.2 전에 받은 배치) — 12 부터도 점으로 그린다 */
  noArea: boolean;
}

export interface EventPointFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: EventPointProps;
}

export interface EventPointCollection {
  type: "FeatureCollection";
  features: EventPointFeature[];
}

function pair(xs: readonly unknown[]): [number, number] | null {
  const [a, b] = xs;
  return typeof a === "number" && typeof b === "number" ? [a, b] : null;
}

/** 중심점 — centroid 가 없으면 bbox 가운데 */
function anchorOf(e: ClosureEvent): [number, number] | null {
  const c = e.centroid ? pair(e.centroid) : null;
  if (c) return c;
  const sw = pair(e.bbox.slice(0, 2));
  const ne = pair(e.bbox.slice(2, 4));
  return sw && ne ? [(sw[0] + ne[0]) / 2, (sw[1] + ne[1]) / 2] : null;
}

export function eventPoints(
  events: readonly ClosureEvent[],
  atMs: number,
  visible: readonly ChipKind[],
): EventPointCollection {
  const features: EventPointFeature[] = [];
  for (const { event, kind, low, color } of shown(events, atMs, visible)) {
    const at = anchorOf(event);
    if (!at) continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: at },
      properties: {
        id: event.id,
        kind,
        low,
        sev: low ? LOW_SEV : SEV[kind],
        color,
        noArea: !event.area,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

type AreaGeometry =
  | { type: "Polygon"; coordinates: number[][][] }
  | { type: "MultiPolygon"; coordinates: number[][][][] };

export interface EventAreaFeature {
  type: "Feature";
  geometry: AreaGeometry;
  properties: { id: string; kind: EventKind; low: boolean; color: string };
}

export interface EventAreaCollection {
  type: "FeatureCollection";
  features: EventAreaFeature[];
}

function areaOf(e: ClosureEvent): AreaGeometry | null {
  const a = e.area;
  if (!a) return null;
  // 생성 타입은 type 이 선택·좌표가 unknown 튜플 — 응답은 GeoJSON 그대로 (INTERFACE §3.1 v0.14)
  return a.type === "MultiPolygon"
    ? { type: "MultiPolygon", coordinates: a.coordinates as unknown as number[][][][] }
    : { type: "Polygon", coordinates: a.coordinates as unknown as number[][][] };
}

export function eventAreas(
  events: readonly ClosureEvent[],
  atMs: number,
  visible: readonly ChipKind[],
): EventAreaCollection {
  const features: EventAreaFeature[] = [];
  for (const { event, kind, low, color } of shown(events, atMs, visible)) {
    const geometry = areaOf(event);
    if (geometry)
      features.push({ type: "Feature", geometry, properties: { id: event.id, kind, low, color } });
  }
  return { type: "FeatureCollection", features };
}

/** 첫 화면 범위 (T7.4) — 그리는 사건(해제 빼고)의 bbox 합집합. 없으면 null */
export function eventsBounds(
  events: readonly ClosureEvent[],
  atMs: number,
): [number, number, number, number] | null {
  let out: [number, number, number, number] | null = null;
  for (const { event } of shown(events, atMs, CHIP_KINDS)) {
    const sw = pair(event.bbox.slice(0, 2));
    const ne = pair(event.bbox.slice(2, 4));
    if (!sw || !ne) continue;
    out = out
      ? [
          Math.min(out[0], sw[0]),
          Math.min(out[1], sw[1]),
          Math.max(out[2], ne[0]),
          Math.max(out[3], ne[1]),
        ]
      : [sw[0], sw[1], ne[0], ne[1]];
  }
  return out;
}

/** 중심점 소스 — 11 까지 묶고(12 부터는 낱개), 묶음의 sev 는 그 안의 가장 작은 값 */
export function eventPointSource(fc: EventPointCollection): GeoJSONSourceSpecification {
  return {
    type: "geojson",
    data: fc,
    cluster: true,
    clusterMaxZoom: AREA_MIN_ZOOM - 1,
    clusterRadius: 44,
    clusterProperties: { sev: ["min", ["get", "sev"]] },
  };
}

export function eventAreaSource(fc: EventAreaCollection): GeoJSONSourceSpecification {
  return { type: "geojson", data: fc };
}

export const EVENT_LAYER_IDS = {
  areaFill: "naru-events-area-fill",
  areaLine: "naru-events-area-line",
  cluster: "naru-events-cluster",
  count: "naru-events-count",
  dot: "naru-events-dot",
  dotNoArea: "naru-events-dot-noarea",
  selected: "naru-events-selected",
} as const;

/** 고른 사건 윤곽 필터 (T7.5) — null 이면 아무것도 */
export function selectedFilter(id: string | null): FilterSpecification {
  return ["==", ["get", "id"], id ?? ""];
}

/** 누른 곳의 렌더 피처 → 사건 id (순서대로, 같은 사건은 하나로 — MultiPolygon 조각·타일 경계) (T7.5) */
export function clickedIds(
  features: readonly { properties: Record<string, unknown> | null }[],
): string[] {
  const out: string[] = [];
  for (const f of features) {
    const id = f.properties?.["id"];
    if (typeof id === "string" && !out.includes(id)) out.push(id);
  }
  return out;
}

const SEV_COLOR: ExpressionSpecification = [
  "step",
  ["get", "sev"],
  COLORS.stop,
  1,
  COLORS.soon,
  2,
  COLORS.slow,
  3,
  COLORS.zone,
  LOW_SEV,
  COLORS.gray,
];
const IS_SOON: ExpressionSpecification = ["==", ["get", "kind"], "soon"];
const LOW: ExpressionSpecification = ["get", "low"];
const IS_ZONE: ExpressionSpecification = ["==", ["get", "kind"], "zone"];

/** 구역 채움 — 흐림·예정 구역은 옅게, 나머지는 줌이 커질수록 옅게(횡단보도 점이 위에 온다) */
function fillAt(opacity: number): ExpressionSpecification {
  return ["case", LOW, 0.06, IS_ZONE, 0.1, opacity];
}

/** 레이어 7장 — 구역 채움·윤곽(12~), 고른 사건 윤곽, 클러스터 원·개수(~12), 낱개 점(~12), 구역 없는 사건 점(12~) */
export function eventLayers(
  pointSource: string = EVENT_POINT_SOURCE_ID,
  areaSource: string = EVENT_AREA_SOURCE_ID,
): LayerSpecification[] {
  return [
    {
      id: EVENT_LAYER_IDS.areaFill,
      type: "fill",
      source: areaSource,
      minzoom: AREA_MIN_ZOOM,
      paint: {
        "fill-color": ["get", "color"],
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 12, fillAt(0.3), 16, fillAt(0.12)],
      },
    },
    {
      id: EVENT_LAYER_IDS.areaLine,
      type: "line",
      source: areaSource,
      minzoom: AREA_MIN_ZOOM,
      paint: {
        "line-color": ["get", "color"],
        "line-width": ["case", IS_SOON, 3, 2],
        "line-opacity": ["case", LOW, 0.7, 1],
        "line-dasharray": ["case", ["any", LOW, IS_ZONE], ["literal", [2, 2]], ["literal", [1, 0]]],
      },
    },
    {
      // 고른 사건 (T7.5) — 줌 제한 없이: 긴 행진은 카드를 열면 12 아래로 맞춰진다
      id: EVENT_LAYER_IDS.selected,
      type: "line",
      source: areaSource,
      filter: selectedFilter(null),
      paint: { "line-color": ["get", "color"], "line-width": 5, "line-opacity": 0.9 },
    },
    {
      id: EVENT_LAYER_IDS.cluster,
      type: "circle",
      source: pointSource,
      maxzoom: AREA_MIN_ZOOM,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": SEV_COLOR,
        "circle-radius": ["step", ["get", "point_count"], 14, 5, 17, 20, 21],
        "circle-opacity": ["case", [">=", ["get", "sev"], LOW_SEV], 0.6, 0.95],
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    },
    {
      id: EVENT_LAYER_IDS.count,
      type: "symbol",
      source: pointSource,
      maxzoom: AREA_MIN_ZOOM,
      filter: ["has", "point_count"],
      layout: {
        "icon-image": ["concat", COUNT_ICON_PREFIX, ["to-string", ["get", "point_count"]]],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    },
    {
      id: EVENT_LAYER_IDS.dot,
      type: "circle",
      source: pointSource,
      maxzoom: AREA_MIN_ZOOM,
      filter: ["!", ["has", "point_count"]],
      paint: dotPaint(7),
    },
    {
      id: EVENT_LAYER_IDS.dotNoArea,
      type: "circle",
      source: pointSource,
      minzoom: AREA_MIN_ZOOM,
      filter: ["==", ["get", "noArea"], true],
      paint: dotPaint(9),
    },
  ];
}

function dotPaint(radius: number): CircleLayerSpecification["paint"] {
  return {
    "circle-color": ["get", "color"],
    "circle-radius": radius,
    "circle-opacity": ["case", LOW, 0.6, 0.95],
    "circle-stroke-color": "#ffffff",
    "circle-stroke-width": ["case", IS_SOON, 3, 2],
  };
}
