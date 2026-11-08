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
  /** 확인(빨강) "naru-x" ×, 예정(노랑) "naru-bang" ! — 시안 범례. 그 밖엔 표식 없음 */
  icon: string;
  /** 이 횡단보도에 걸린 후보 수 — 같은 횡단보도가 여러 구간에 걸릴 수 있다 */
  candidates: number;
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

/** 한 횡단보도의 상태가 여럿이면 앞쪽이 이긴다: 확인 > 예정 > 예정 구역 > 해제 */
export const STATUS_SEVERITY: Record<Status, number> = {
  confirmed: 0,
  scheduled: 1,
  zone_scheduled: 2,
  released: 3,
};

/** 같은 무게면 늦게 풀리는 쪽 — end 가 없으면(종료 미정) 가장 늦은 것으로 본다 */
function endKey(end: string | null): number {
  return end ? new Date(end).getTime() : Number.POSITIVE_INFINITY;
}

function wins(a: ClosurePointProps, b: ClosurePointProps): boolean {
  const d = STATUS_SEVERITY[a.status] - STATUS_SEVERITY[b.status];
  return d < 0 || (d === 0 && endKey(a.window_end) > endKey(b.window_end));
}

/**
 * 횡단보도(Point) 하나에 점 하나. /closures 는 (후보, 횡단보도)마다 Feature 라서 같은 횡단보도가 여러 번
 * 올 수 있다(코스 구간이 겹치는 교차로) — 가장 무거운 상태로 합친다. Polygon(예정 구역)은 zoneLayer 몫
 */
export function closurePoints(fc: FeatureCollection): ClosurePointCollection {
  const byCrosswalk = new Map<string, ClosurePointFeature>();
  for (const f of fc.features) {
    if (!isPoint(f)) continue;
    const [lng, lat] = f.geometry.coordinates;
    if (typeof lng !== "number" || typeof lat !== "number") continue;
    const p = f.properties;
    const id = p.crosswalk_id ?? `${lng},${lat}`;
    const props: ClosurePointProps = {
      crosswalk_id: p.crosswalk_id ?? "",
      status: p.status,
      color: STATUS_COLOR[p.status],
      reason: p.reason,
      window_end: (p.window["end"] as string | null | undefined) ?? null,
      confidence: p.confidence,
      approx: p.approx ?? false,
      icon: iconOf(p.status),
      candidates: 1,
    };
    const prev = byCrosswalk.get(id);
    if (prev && !wins(props, prev.properties)) {
      prev.properties.candidates += 1;
      continue;
    }
    props.candidates = (prev?.properties.candidates ?? 0) + 1;
    byCrosswalk.set(id, {
      type: "Feature",
      geometry: { type: "Point", coordinates: [lng, lat] },
      properties: props,
    });
  }
  return { type: "FeatureCollection", features: [...byCrosswalk.values()] };
}

/** 지도·칩·시트 부제의 개수 — 횡단보도는 곳 단위(합친 뒤), 예정 구역은 구역 단위 */
export function countByStatus(fc: FeatureCollection): Record<Status, number> {
  const out: Record<Status, number> = {
    scheduled: 0,
    confirmed: 0,
    released: 0,
    zone_scheduled: 0,
  };
  for (const f of closurePoints(fc).features) out[f.properties.status] += 1;
  for (const f of fc.features) if (f.geometry.type === "Polygon") out[f.properties.status] += 1;
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
