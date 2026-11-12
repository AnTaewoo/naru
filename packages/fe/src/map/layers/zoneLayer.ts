// 순수 함수: /closures 의 Polygon Feature(예정 구역, zone_scheduled) → MapLibre source/레이어 (보라 빗금)
// 지금 BE 는 Polygon 을 내지 않는다(ZoneMatcher v1 전). 레이어는 준비만 — 데이터가 생기면 그대로 그린다
import type { GeoJSONSourceSpecification, LayerSpecification } from "maplibre-gl";
import type { Feature, FeatureCollection } from "../../types/contracts";
import { COLORS } from "../colors";
import { ICON_IDS } from "../icons";

export const ZONE_SOURCE_ID = "naru-zones";
export const ZONE_LAYER_IDS = { fill: "naru-zones-fill", line: "naru-zones-line" } as const;

export interface ZoneFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: [number, number][][] };
  properties: { zone_name: string; reason: string; confidence: number };
}

function isPolygon(f: Feature): f is Feature & { geometry: { type: "Polygon" } } {
  return f.geometry.type === "Polygon";
}

export function zonePolygons(fc: FeatureCollection): {
  type: "FeatureCollection";
  features: ZoneFeature[];
} {
  const features: ZoneFeature[] = [];
  for (const f of fc.features) {
    if (!isPolygon(f)) continue;
    const rings = f.geometry.coordinates as unknown as [number, number][][];
    features.push({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: rings },
      properties: {
        zone_name: f.properties.zone_name ?? "",
        reason: f.properties.reason,
        confidence: f.properties.confidence,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export function zoneSource(fc: FeatureCollection): GeoJSONSourceSpecification {
  return { type: "geojson", data: zonePolygons(fc) };
}

export function zoneLayers(sourceId: string = ZONE_SOURCE_ID): LayerSpecification[] {
  return [
    {
      id: ZONE_LAYER_IDS.fill,
      type: "fill",
      source: sourceId,
      paint: { "fill-pattern": ICON_IDS.hatch, "fill-opacity": 0.9 },
    },
    {
      id: ZONE_LAYER_IDS.line,
      type: "line",
      source: sourceId,
      paint: { "line-color": COLORS.zone, "line-width": 1.5, "line-dasharray": [2, 2] },
    },
  ];
}
