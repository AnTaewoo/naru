"use client";

import {
  GeoJSONSource,
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type FilterSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { useClosureDispatch, useClosures } from "../state/ClosureProvider";
import type { FeatureCollection, Status } from "../types/contracts";
import { ICON_IDS, ICON_PIXEL_RATIO, renderIcon } from "./icons";
import {
  CLOSURE_LAYER_IDS,
  CLOSURE_SOURCE_ID,
  closureLayers,
  closurePoints,
} from "./layers/closureLayer";
import { ZONE_SOURCE_ID, zoneLayers, zonePolygons } from "./layers/zoneLayer";
import styles from "./MapView.module.css";
import { baseStyle } from "./tiles";

// maplibre Map 하나를 useRef 로 보유. 레이어는 React 로 다시 그리지 않고 setData 로 갱신 (CONVENTIONS §5.6)

/**
 * maplibre v6 는 워커 주소를 import.meta.url 로 찾는데, 번들 안에서는 file:// 이라 빈 값이 된다.
 * webpack 이 이 줄을 보고 워커 파일을 .next/static/media 에 해시 이름으로 내보낸다.
 */
const WORKER_URL = new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href;

export interface MapViewProps {
  /** 지도에 보일 상태. 비면 전부 */
  visible?: readonly Status[];
}

export function bboxOf(map: MapLibreMap): string {
  const b = map.getBounds();
  const f = (n: number) => n.toFixed(4);
  return `${f(b.getWest())},${f(b.getSouth())},${f(b.getEast())},${f(b.getNorth())}`;
}

export function centerOf(bbox: string): [number, number] {
  const [w, s, e, n] = bbox.split(",").map(Number);
  if (
    w === undefined ||
    s === undefined ||
    e === undefined ||
    n === undefined ||
    [w, s, e, n].some(Number.isNaN)
  ) {
    return [126.9779, 37.5709];
  }
  return [(w + e) / 2, (s + n) / 2];
}

export function statusFilter(visible: readonly Status[] | undefined): FilterSpecification | null {
  return visible && visible.length ? ["in", ["get", "status"], ["literal", [...visible]]] : null;
}

function applyClosures(map: MapLibreMap, fc: FeatureCollection) {
  const points = map.getSource(CLOSURE_SOURCE_ID);
  if (points instanceof GeoJSONSource) void points.setData(closurePoints(fc));
  const zones = map.getSource(ZONE_SOURCE_ID);
  if (zones instanceof GeoJSONSource) void zones.setData(zonePolygons(fc));
}

function applyFilter(map: MapLibreMap, visible: readonly Status[] | undefined) {
  const filter = statusFilter(visible);
  for (const id of Object.values(CLOSURE_LAYER_IDS)) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
}

export function MapView({ visible }: MapViewProps) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const loaded = useRef(false);
  const { closures, bbox } = useClosures();
  const dispatch = useClosureDispatch();
  // load 이전에 바뀐 값은 ref 에 두었다가 load 때 한 번에 반영한다
  const closuresRef = useRef(closures);
  const visibleRef = useRef(visible);
  const initialBbox = useRef(bbox);

  useEffect(() => {
    if (!container.current) return;
    setWorkerUrl(WORKER_URL);
    const map = new MapLibreMap({
      container: container.current,
      style: baseStyle(process.env.NEXT_PUBLIC_VWORLD_KEY),
      center: centerOf(initialBbox.current),
      zoom: 15,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      for (const id of Object.values(ICON_IDS)) {
        const image = renderIcon(id);
        if (image && !map.hasImage(id)) map.addImage(id, image, { pixelRatio: ICON_PIXEL_RATIO });
      }
      map.addSource(ZONE_SOURCE_ID, {
        type: "geojson",
        data: zonePolygons({ type: "FeatureCollection", features: [] }),
      });
      map.addSource(CLOSURE_SOURCE_ID, {
        type: "geojson",
        data: closurePoints({ type: "FeatureCollection", features: [] }),
      });
      for (const layer of zoneLayers()) map.addLayer(layer);
      for (const layer of closureLayers()) map.addLayer(layer);
      loaded.current = true;
      applyClosures(map, closuresRef.current);
      applyFilter(map, visibleRef.current);
    });
    map.on("moveend", () => dispatch({ type: "setBbox", bbox: bboxOf(map) }));
    mapRef.current = map;
    return () => {
      loaded.current = false;
      map.remove(); // StrictMode 이중 마운트에서 map 이 둘 생기지 않게
      mapRef.current = null;
    };
  }, [dispatch]);

  // closures 가 바뀌면 소스 데이터만 갱신
  useEffect(() => {
    closuresRef.current = closures;
    const map = mapRef.current;
    if (map && loaded.current) applyClosures(map, closures);
  }, [closures]);

  // 칩 필터 → 레이어 filter
  useEffect(() => {
    visibleRef.current = visible;
    const map = mapRef.current;
    if (map && loaded.current) applyFilter(map, visible);
  }, [visible]);

  return <div ref={container} className={styles.map} role="region" aria-label="지도" />;
}

export default MapView;
