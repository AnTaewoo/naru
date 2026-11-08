// 순수 함수: contracts FeatureCollection(/closures) → MapLibre source 데이터 + 레이어 스펙 (CONVENTIONS §5.6)
import type { GeoJSONSourceSpecification, LayerSpecification } from "maplibre-gl";
import type { Feature, FeatureCollection, Status } from "../../types/contracts";
import { STATUS_COLOR } from "../colors";
import { ICON_IDS, ICON_PIXEL_RATIO } from "../icons";

export const CLOSURE_SOURCE_ID = "naru-closures";
export const CLOSURE_LAYER_IDS = {
  dot: "naru-closures-dot",
  mark: "naru-closures-mark",
} as const;

export interface ClosurePointProps {
  crosswalk_id: string;
  status: Status;
  color: string;
  reason: string;
  window_end: string | null;
  confidence: number;
  approx: boolean;
  /** 확인(빨강) "naru-x" ×, 예정(노랑) "naru-bang" ! — 목업 범례. 그 밖엔 표식 없음 */
  icon: string;
}

export interface ClosurePointFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: ClosurePointProps;
}

export interface ClosurePointCollection {
  type: "FeatureCollection";
  features: ClosurePointFeature[];
}

export function iconOf(status: Status): string {
  if (status === "confirmed") return ICON_IDS.x;
  if (status === "scheduled") return ICON_IDS.bang;
  return "";
}

function isPoint(f: Feature): f is Feature & { geometry: { type: "Point" } } {
  return f.geometry.type === "Point";
}

/** 횡단보도(Point) Feature 만 — Polygon(예정 구역)은 zoneLayer 가 맡는다 */
export function closurePoints(fc: FeatureCollection): ClosurePointCollection {
  const features: ClosurePointFeature[] = [];
  for (const f of fc.features) {
    if (!isPoint(f)) continue;
    const [lng, lat] = f.geometry.coordinates;
    if (typeof lng !== "number" || typeof lat !== "number") continue;
    const p = f.properties;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lng, lat] },
      properties: {
        crosswalk_id: p.crosswalk_id ?? "",
        status: p.status,
        color: STATUS_COLOR[p.status],
        reason: p.reason,
        window_end: (p.window["end"] as string | null | undefined) ?? null,
        confidence: p.confidence,
        approx: p.approx ?? false,
        icon: iconOf(p.status),
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export function countByStatus(fc: FeatureCollection): Record<Status, number> {
  const out: Record<Status, number> = {
    scheduled: 0,
    confirmed: 0,
    released: 0,
    zone_scheduled: 0,
  };
  for (const f of fc.features) out[f.properties.status] += 1;
  return out;
}

export function closureSource(fc: FeatureCollection): GeoJSONSourceSpecification {
  return { type: "geojson", data: closurePoints(fc) };
}

/** 레이어 2장: 흰 테두리 상태색 점 → 그 위 표식 아이콘(× / !). 아이콘은 icons.ts 가 addImage */
export function closureLayers(sourceId: string = CLOSURE_SOURCE_ID): LayerSpecification[] {
  return [
    {
      id: CLOSURE_LAYER_IDS.dot,
      type: "circle",
      source: sourceId,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 5, 17, 11],
        "circle-color": ["get", "color"],
        "circle-opacity": ["case", ["==", ["get", "status"], "released"], 0.45, 0.95],
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 13, 1.5, 17, 2.5],
      },
    },
    {
      id: CLOSURE_LAYER_IDS.mark,
      type: "symbol",
      source: sourceId,
      layout: {
        "icon-image": ["get", "icon"],
        // 아이콘 한 변 24 px(×2 로 그림) → 점 지름에 맞춘다
        "icon-size": ["interpolate", ["linear"], ["zoom"], 13, 0.42, 17, 0.9],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    },
  ];
}

export const CLOSURE_ICON_PIXEL_RATIO = ICON_PIXEL_RATIO;
