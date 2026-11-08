"use client";

import {
  AttributionControl,
  GeoJSONSource,
  GeolocateControl,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
  type FilterSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState, type RefObject } from "react";
import { SHEET_COLLAPSED_PX } from "../components/BottomSheet";
import { MAP_LOCALE_KO, MAP_OUTSIDE_KO } from "../i18n/ko";
import { inBbox, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { POSITION_OPTIONS, useRoute, useRouteDispatch } from "../state/RouteProvider";
import type { FeatureCollection, RouteResponse, Status } from "../types/contracts";
import { ICON_IDS, ICON_PIXEL_RATIO, renderIcon } from "./icons";
import {
  CLOSURE_LAYER_IDS,
  CLOSURE_SOURCE_ID,
  closureLayers,
  closurePoints,
} from "./layers/closureLayer";
import {
  ROUTE_AVOIDED_SOURCE_ID,
  ROUTE_BASELINE_SOURCE_ID,
  ROUTE_CROSSING_SOURCE_ID,
  ROUTE_ENTRANCE_SOURCE_ID,
  ROUTE_LINE_SOURCE_ID,
  avoidedLayers,
  avoidedPoints,
  baselineBounds,
  baselineLayers,
  baselineLine,
  crossingLayers,
  crossingSegments,
  entranceLayers,
  entranceMarkers,
  routeBounds,
  routeLayers,
  routeLine,
  routeOdKey,
  viewPaint,
  type LngLat,
} from "./layers/routeLayer";
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

function applyRoute(map: MapLibreMap, route: RouteResponse | null) {
  const line = map.getSource(ROUTE_LINE_SOURCE_ID);
  if (line instanceof GeoJSONSource) void line.setData(routeLine(route));
  const baseline = map.getSource(ROUTE_BASELINE_SOURCE_ID);
  if (baseline instanceof GeoJSONSource) void baseline.setData(baselineLine(route));
  const crossings = map.getSource(ROUTE_CROSSING_SOURCE_ID);
  if (crossings instanceof GeoJSONSource) void crossings.setData(crossingSegments(route));
  const entrances = map.getSource(ROUTE_ENTRANCE_SOURCE_ID);
  if (entrances instanceof GeoJSONSource) void entrances.setData(entranceMarkers(route));
}

/** 고른 길 (T5.11) — 원래 길이면 원래 길 실선·가장 빠른 길 흐리게·지나는 통제 횡단보도에 원 */
function applyView(
  map: MapLibreMap,
  route: RouteResponse | null,
  original: boolean,
  closures: FeatureCollection,
) {
  const avoided = map.getSource(ROUTE_AVOIDED_SOURCE_ID);
  const none: FeatureCollection = { type: "FeatureCollection", features: [] };
  if (avoided instanceof GeoJSONSource) {
    void avoided.setData(avoidedPoints(original ? route : null, original ? closures : none));
  }
  for (const [id, prop, value] of viewPaint(original)) {
    if (map.getLayer(id)) map.setPaintProperty(id, prop, value);
  }
}

/**
 * 위는 떠 있는 UI 와 그 아래 지도 컨트롤(확대·출처) + 핀 말풍선(약 50px). 아래는 접힌 시트(96px) —
 * 경로를 찾거나 통제를 고르면 시트가 접히고 나서 맞춘다 (T5.6)
 */
function fitPadding(map: MapLibreMap) {
  const container = map.getContainer();
  const h = container.clientHeight;
  const ctrl = container.querySelector(".maplibregl-ctrl-top-right");
  const ctrlBottom = ctrl
    ? ctrl.getBoundingClientRect().bottom - container.getBoundingClientRect().top
    : 0;
  const top = Math.round(Math.max(ctrlBottom, 0) + 50);
  const bottom = Math.max(0, Math.min(SHEET_COLLAPSED_PX + 24, h - top - 80));
  return { top, bottom, left: 40, right: 40 };
}

function fitRoute(map: MapLibreMap, route: RouteResponse | null, fitted: RefObject<string | null>) {
  const key = routeOdKey(route);
  const bounds = routeBounds(route);
  if (!key || !bounds || key === fitted.current) return;
  fitted.current = key;
  map.fitBounds(bounds, { padding: fitPadding(map), maxZoom: 17 });
}

/** 출발·도착 핀 — 글리프 서버 없이 DOM 마커로 (시안 02 말풍선) */
function pinElement(kind: "from" | "to"): HTMLElement {
  const el = document.createElement("div");
  el.className = `${styles.pin} ${kind === "from" ? styles.pinFrom : styles.pinTo}`;
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", kind === "from" ? "출발 지점" : "도착 지점");
  const label = document.createElement("span");
  label.className = styles.pinLabel ?? "";
  label.textContent = kind === "from" ? "출발" : "도착";
  const dot = document.createElement("span");
  dot.className = styles.pinDot ?? "";
  el.append(label, dot);
  return el;
}

function syncPin(
  map: MapLibreMap,
  pin: RefObject<Marker | null>,
  kind: "from" | "to",
  p: LngLat | null,
) {
  if (!p) {
    pin.current?.remove();
    pin.current = null;
  } else if (pin.current) {
    pin.current.setLngLat(p);
  } else {
    // 점(지름 10px)의 가운데가 좌표에 오도록 아래로 5px
    pin.current = new Marker({ element: pinElement(kind), anchor: "bottom", offset: [0, 5] })
      .setLngLat(p)
      .addTo(map);
  }
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
  const { closures, bbox, focus, coverage } = useClosures();
  const dispatch = useClosureDispatch();
  const { route, from, to, active, view } = useRoute();
  // 원래 길 카드를 골랐나 (T5.11) — 피한 통제가 없으면 원래 길도 없다
  const original = view === "original" && (route?.avoided.length ?? 0) > 0;
  const originalRef = useRef(original);
  const routeDispatch = useRouteDispatch();
  const fromPin = useRef<Marker | null>(null);
  const toPin = useRef<Marker | null>(null);
  const fitted = useRef<string | null>(null);
  // 지도 load 전에는 회색 대신 로딩 표시 (T5.6)
  const [ready, setReady] = useState(false);
  // 지도 '내 위치 찾기' 가 보행망 밖이면 잠깐 안내 (T5.7)
  const [notice, setNotice] = useState<string | null>(null);
  const coverageRef = useRef(coverage);
  // load 이전에 바뀐 값은 ref 에 두었다가 load 때 한 번에 반영한다
  const closuresRef = useRef(closures);
  const visibleRef = useRef(visible);
  const routeRef = useRef(route);
  const initialBbox = useRef(bbox);

  useEffect(() => {
    if (!container.current) return;
    setWorkerUrl(WORKER_URL);
    const map = new MapLibreMap({
      container: container.current,
      style: baseStyle(process.env.NEXT_PUBLIC_VWORLD_KEY),
      center: centerOf(initialBbox.current),
      zoom: 15,
      attributionControl: false,
      locale: MAP_LOCALE_KO,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    // 내 위치 찾기 (T5.7) — 한 번 찾아 파란 점을 찍고 옮긴다. 보행망 밖이면 안내
    const geolocate = new GeolocateControl({
      positionOptions: POSITION_OPTIONS,
      fitBoundsOptions: { maxZoom: 16 },
    });
    geolocate.on("geolocate", (e) => {
      const cov = coverageRef.current;
      const outside = cov !== null && !inBbox([e.coords.longitude, e.coords.latitude], cov);
      setNotice(outside ? MAP_OUTSIDE_KO : null);
    });
    map.addControl(geolocate, "top-right");
    // 출처 표기는 늘 펼쳐 두고 위쪽에 — 아래 모서리는 하단 시트가 덮는다. 고지 전문은 /licenses
    map.addControl(
      new AttributionControl({
        compact: false,
        customAttribution: '<a href="/licenses">오픈소스 고지</a>',
      }),
      "top-right",
    );
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
      map.addSource(ROUTE_BASELINE_SOURCE_ID, { type: "geojson", data: baselineLine(null) });
      map.addSource(ROUTE_LINE_SOURCE_ID, { type: "geojson", data: routeLine(null) });
      map.addSource(ROUTE_CROSSING_SOURCE_ID, { type: "geojson", data: crossingSegments(null) });
      map.addSource(ROUTE_ENTRANCE_SOURCE_ID, { type: "geojson", data: entranceMarkers(null) });
      map.addSource(ROUTE_AVOIDED_SOURCE_ID, {
        type: "geojson",
        data: avoidedPoints(null, { type: "FeatureCollection", features: [] }),
      });
      // 아래부터: 예정 구역 → 원래 길 점선 → 경로 실선 → 터널 → (원래 길 보기의 원) → 통제 점 → 입구 마커
      for (const layer of zoneLayers()) map.addLayer(layer);
      for (const layer of baselineLayers()) map.addLayer(layer);
      for (const layer of routeLayers()) map.addLayer(layer);
      for (const layer of crossingLayers()) map.addLayer(layer);
      for (const layer of avoidedLayers()) map.addLayer(layer);
      for (const layer of closureLayers()) map.addLayer(layer);
      for (const layer of entranceLayers()) map.addLayer(layer);
      loaded.current = true;
      setReady(true);
      applyClosures(map, closuresRef.current);
      applyFilter(map, visibleRef.current);
      applyRoute(map, routeRef.current);
      applyView(map, routeRef.current, originalRef.current, closuresRef.current);
      fitRoute(map, routeRef.current, fitted);
    });
    map.on("moveend", () => dispatch({ type: "setBbox", bbox: bboxOf(map) }));
    // 길찾기가 켜져 있을 때만 reducer 가 받는다 — 출발, 다음 도착
    map.on("click", (e) => routeDispatch({ type: "pick", point: [e.lngLat.lng, e.lngLat.lat] }));
    mapRef.current = map;
    return () => {
      loaded.current = false;
      for (const pin of [fromPin, toPin]) {
        pin.current?.remove();
        pin.current = null;
      }
      map.remove(); // StrictMode 이중 마운트에서 map 이 둘 생기지 않게
      mapRef.current = null;
    };
  }, [dispatch, routeDispatch]);

  useEffect(() => {
    coverageRef.current = coverage;
  }, [coverage]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(timer);
  }, [notice]);

  // 새로 정해진 출발·도착이 화면 밖이면 그 점으로 — 내 위치(T5.7)·검색으로 고른 곳(T5.8).
  // 둘이 함께 바뀌면(바꾸기·주소창) 경로 맞춤이 한다
  const lastOd = useRef<{ from: LngLat | null; to: LngLat | null }>({ from: null, to: null });
  useEffect(() => {
    const prev = lastOd.current;
    lastOd.current = { from, to };
    const map = mapRef.current;
    const moved = [from !== prev.from ? from : null, to !== prev.to ? to : null].filter(
      (p): p is LngLat => p !== null,
    );
    const [p] = moved;
    if (!map || moved.length !== 1 || !p) return;
    const run = () => {
      const pad = fitPadding(map);
      const { x, y } = map.project(p);
      const box = map.getContainer();
      const inView =
        x >= pad.left &&
        x <= box.clientWidth - pad.right &&
        y >= pad.top &&
        y <= box.clientHeight - pad.bottom;
      if (inView) return;
      const zoom = Math.max(map.getZoom(), 15);
      map.easeTo({ center: p, zoom, offset: [0, (pad.top - pad.bottom) / 2] });
    };
    if (loaded.current) run();
    else map.once("load", run);
  }, [from, to]);

  // closures 가 바뀌면 소스 데이터만 갱신
  useEffect(() => {
    closuresRef.current = closures;
    const map = mapRef.current;
    if (map && loaded.current) applyClosures(map, closures);
  }, [closures]);

  // 경로가 바뀌면 경로 소스만 갱신. 새 출발·도착의 첫 경로면 지도를 맞춘다
  useEffect(() => {
    routeRef.current = route;
    const map = mapRef.current;
    if (!map || !loaded.current) return;
    applyRoute(map, route);
    fitRoute(map, route, fitted);
  }, [route]);

  // 고른 길 (T5.11) — 경로·통제가 바뀌어도 다시 그린다
  useEffect(() => {
    originalRef.current = original;
    const map = mapRef.current;
    if (map && loaded.current) applyView(map, route, original, closures);
  }, [route, original, closures]);

  // 카드를 눌러 고른 길이 바뀌면 그 길에 맞춘다 — 원래 길이면 원래 길만, 아니면 둘 다
  const lastOriginal = useRef(original);
  useEffect(() => {
    const changed = lastOriginal.current !== original;
    lastOriginal.current = original;
    const map = mapRef.current;
    const bounds = original ? baselineBounds(route) : routeBounds(route);
    if (!changed || !map || !loaded.current || !bounds) return;
    map.fitBounds(bounds, { padding: fitPadding(map), maxZoom: 17 });
  }, [original, route]);

  // 통제 불러오기(T5.4) — 고른 통제의 범위로 지도를 맞춘다. 순번이 바뀔 때마다
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    const [w, s, e, n] = focus.bbox;
    const run = () => {
      map.fitBounds(
        [
          [w, s],
          [e, n],
        ],
        { padding: fitPadding(map), maxZoom: 16 },
      );
    };
    if (loaded.current) run();
    else map.once("load", run);
  }, [focus]);

  // 출발·도착 핀, 고르는 중엔 십자 커서
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    syncPin(map, fromPin, "from", from);
    syncPin(map, toPin, "to", to);
    map.getCanvas().style.cursor = active && (!from || !to) ? "crosshair" : "";
  }, [active, from, to]);

  // 칩 필터 → 레이어 filter
  useEffect(() => {
    visibleRef.current = visible;
    const map = mapRef.current;
    if (map && loaded.current) applyFilter(map, visible);
  }, [visible]);

  return (
    <div className={styles.wrap}>
      <div ref={container} className={styles.map} role="region" aria-label="지도" />
      {!ready && (
        <div className={styles.loading} role="status" aria-label="지도 불러오는 중">
          <span className={styles.spinner} aria-hidden />
          지도 불러오는 중…
        </div>
      )}
      {notice && (
        <div className={styles.notice} role="status">
          {notice}
        </div>
      )}
    </div>
  );
}

export default MapView;
