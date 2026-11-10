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
import { SHEET_COLLAPSED_PX, stageHeight } from "../components/BottomSheet";
import { MAP_LOCALE_KO, MAP_OUTSIDE_KO } from "../i18n/ko";
import {
  eventBbox,
  inBbox,
  useClosureDispatch,
  useClosures,
  type Bbox4,
} from "../state/ClosureProvider";
import { POSITION_OPTIONS, useRoute, useRouteDispatch } from "../state/RouteProvider";
import type { ClosureEvent, FeatureCollection, RouteResponse, Status } from "../types/contracts";
import {
  AREA_MIN_ZOOM,
  CHIP_KINDS,
  chipStatuses,
  zoomBand,
  type ChipKind,
  type ZoomBand,
} from "./eventKinds";
import { ICON_IDS, ICON_PIXEL_RATIO, renderCount, renderIcon } from "./icons";
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
import {
  EVENT_AREA_SOURCE_ID,
  EVENT_LAYER_IDS,
  EVENT_POINT_SOURCE_ID,
  eventAreaSource,
  eventAreas,
  eventLayers,
  eventPointSource,
  eventPoints,
  eventsBounds,
  clickedIds,
  selectedFilter,
} from "./layers/eventLayer";
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
  /** 켜진 칩 (T7.4) — 사건 구역·클러스터와 횡단보도 점에 같이 건다. 없으면 전부 */
  visible?: readonly ChipKind[];
}

/** 누르면 사건을 여는 레이어 (T7.5) — 낱개 점(~12)·구역 없는 사건 점·구역 채움(12~) */
const EVENT_HIT_LAYERS: readonly string[] = [
  EVENT_LAYER_IDS.dot,
  EVENT_LAYER_IDS.dotNoArea,
  EVENT_LAYER_IDS.areaFill,
];
/** 클러스터 묶음 목록은 사건 응답 상한(300)까지 */
const MAX_LEAVES = 300;

/** 처음 화면 — 서울 쪽(줌 10). 사건 응답이 오면 그 사건들(없으면 coverage)에 맞춘다 (T7.4) */
const START_ZOOM = 10;

export function bboxOf(map: MapLibreMap): string {
  const b = map.getBounds();
  const f = (n: number) => n.toFixed(4);
  return `${f(b.getWest())},${f(b.getSouth())},${f(b.getEast())},${f(b.getNorth())}`;
}

/** 횡단보도 점(/closures)을 받는 줌 — 점은 15 부터 그리지만 한 단계 먼저 받아 둔다 (T7.4) */
export const POINTS_FETCH_ZOOM = 14;

/** 지금 화면 — bbox 와 횡단보도 점이 필요한지(줌 14 이상이거나 길찾기) */
function viewOf(map: MapLibreMap, routeActive: boolean): { bbox: string; points: boolean } {
  return { bbox: bboxOf(map), points: routeActive || map.getZoom() >= POINTS_FETCH_ZOOM };
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

/** 칩 필터 → 상태 in 필터. 칩을 다 끄면 아무것도 안 그린다 (T7.4) */
export function statusFilter(visible: readonly Status[] | undefined): FilterSpecification | null {
  return visible ? ["in", ["get", "status"], ["literal", [...visible]]] : null;
}

function applyClosures(map: MapLibreMap, fc: FeatureCollection) {
  const points = map.getSource(CLOSURE_SOURCE_ID);
  if (points instanceof GeoJSONSource) void points.setData(closurePoints(fc));
  const zones = map.getSource(ZONE_SOURCE_ID);
  if (zones instanceof GeoJSONSource) void zones.setData(zonePolygons(fc));
}

/** 지금 지도 사건 (T7.4) — 칩이 꺼진 종류는 소스에서 뺀다(클러스터 개수가 소스에서 세어진다) */
function applyEvents(
  map: MapLibreMap,
  events: readonly ClosureEvent[],
  atMs: number,
  visible: readonly ChipKind[],
) {
  const points = map.getSource(EVENT_POINT_SOURCE_ID);
  if (points instanceof GeoJSONSource) void points.setData(eventPoints(events, atMs, visible));
  const areas = map.getSource(EVENT_AREA_SOURCE_ID);
  if (areas instanceof GeoJSONSource) void areas.setData(eventAreas(events, atMs, visible));
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

/** 첫 화면 맞춤 여백 (T7.4) — 위는 지도 컨트롤 윗변(검색·칩 아래), 아래는 절반 시트 */
function framePadding(map: MapLibreMap) {
  const container = map.getContainer();
  const h = container.clientHeight;
  const ctrl = container.querySelector(".maplibregl-ctrl-top-right");
  const ctrlTop = ctrl
    ? ctrl.getBoundingClientRect().top - container.getBoundingClientRect().top
    : 0;
  const top = Math.round(Math.max(ctrlTop, 0));
  const bottom = Math.max(0, Math.min(stageHeight("half", h) + 8, h - top - 80));
  return { top, bottom, left: 24, right: 24 };
}

function fitRoute(map: MapLibreMap, route: RouteResponse | null, fitted: RefObject<string | null>) {
  const key = routeOdKey(route);
  const bounds = routeBounds(route);
  if (!key || !bounds || key === fitted.current) return;
  fitted.current = key;
  map.fitBounds(bounds, { padding: fitPadding(map), maxZoom: 17 });
}

/** 검색으로 고른 곳으로 갈 때 줌 (T7.14, 네이버지도·카카오맵 장소처럼) */
const FOCUS_ZOOM = 17;

/** 검색한 장소 핀 (T7.14) — 출발·도착 핀과 같은 말풍선, 글은 장소 이름 */
function placePinElement(name: string): HTMLElement {
  const el = document.createElement("div");
  el.className = `${styles.pin} ${styles.pinPlace}`;
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", `${name} 위치`);
  const label = document.createElement("span");
  label.className = styles.pinLabel ?? "";
  label.textContent = name;
  const dot = document.createElement("span");
  dot.className = styles.pinDot ?? "";
  el.append(label, dot);
  return el;
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

function applyFilter(map: MapLibreMap, visible: readonly ChipKind[] | undefined) {
  const filter = statusFilter(visible ? chipStatuses(visible) : undefined);
  for (const id of Object.values(CLOSURE_LAYER_IDS)) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
}

export function MapView({ visible }: MapViewProps) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const loaded = useRef(false);
  const { closures, bbox, coverage, events, eventsAt, selected, frame, catalog } = useClosures();
  const dispatch = useClosureDispatch();
  const { route, from, to, active, view, place, focus } = useRoute();
  // 원래 길 카드를 골랐나 (T5.11) — 피한 통제가 없으면 원래 길도 없다
  const original = view === "original" && (route?.avoided.length ?? 0) > 0;
  const originalRef = useRef(original);
  const routeDispatch = useRouteDispatch();
  const activeRef = useRef(active);
  const selectedRef = useRef(selected);
  const fromPin = useRef<Marker | null>(null);
  const placePin = useRef<Marker | null>(null);
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
  // 지금 지도 사건 (T7.4) — 종류는 응답 at 기준
  const atMs = eventsAt ? Date.parse(eventsAt) : 0;
  const eventsRef = useRef({ events: events ?? [], atMs });
  // 카메라를 사람·경로·맞춤이 이미 정했나 — 아니면 coverage(서울 전체)가 오면 한 번 맞춘다
  const framed = useRef(false);
  // 줌 3단계 (T7.4) — e2e 가 data-band 로 본다
  const [band, setBand] = useState<ZoomBand>(zoomBand(START_ZOOM));

  useEffect(() => {
    if (!container.current) return;
    setWorkerUrl(WORKER_URL);
    // 주소에 카메라가 있으면 그 화면 — 지도가 만들어지며 #map= 을 바로 쓰니 그 전에 본다
    if (/[#&]map=/.test(window.location.hash)) framed.current = true;
    const map = new MapLibreMap({
      container: container.current,
      style: baseStyle(process.env.NEXT_PUBLIC_VWORLD_KEY),
      center: centerOf(initialBbox.current),
      zoom: START_ZOOM,
      attributionControl: false,
      locale: MAP_LOCALE_KO,
      // 카메라를 주소 #map=줌/위도/경도 로 — 링크로 그 화면, e2e 는 줌 단계를 바로 연다 (T7.4)
      hash: "map",
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    // 내 위치 찾기 (T5.7) — 한 번 찾아 파란 점을 찍고 옮긴다. 보행망 밖이면 안내
    const geolocate = new GeolocateControl({
      positionOptions: POSITION_OPTIONS,
      fitBoundsOptions: { maxZoom: 16 },
    });
    geolocate.on("geolocate", (e) => {
      framed.current = true;
      const cov = coverageRef.current;
      const outside = cov !== null && !inBbox([e.coords.longitude, e.coords.latitude], cov);
      setNotice(outside ? MAP_OUTSIDE_KO : null);
    });
    map.addControl(geolocate, "top-right");
    // 출처 표기는 타일 출처 한 줄만, 늘 펼쳐 두고 위쪽에 — 아래 모서리는 하단 시트가 덮는다. OSM 타일은
    // 숨기거나 ⓘ로 접을 수 없다(OSMF 타일 정책 §2). 고지 링크는 시트 맨 아래 줄·푸터 (T5.12)
    map.addControl(new AttributionControl({ compact: false }), "top-right");
    map.on("load", () => {
      for (const id of Object.values(ICON_IDS)) {
        const image = renderIcon(id);
        if (image && !map.hasImage(id)) map.addImage(id, image, { pixelRatio: ICON_PIXEL_RATIO });
      }
      const layers = eventLayers();
      const below = new Set<string>([
        EVENT_LAYER_IDS.areaFill,
        EVENT_LAYER_IDS.areaLine,
        EVENT_LAYER_IDS.selected,
      ]);
      map.addSource(EVENT_AREA_SOURCE_ID, eventAreaSource(eventAreas([], 0, CHIP_KINDS)));
      map.addSource(EVENT_POINT_SOURCE_ID, eventPointSource(eventPoints([], 0, CHIP_KINDS)));
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
      // 아래부터: 사건 구역 → 예정 구역 → 원래 길 점선 → 경로 실선 → 터널 → (원래 길 보기의 원) →
      // 통제 점 → 사건 클러스터·점 → 입구 마커
      for (const layer of layers.filter((l) => below.has(l.id))) map.addLayer(layer);
      for (const layer of zoneLayers()) map.addLayer(layer);
      for (const layer of baselineLayers()) map.addLayer(layer);
      for (const layer of routeLayers()) map.addLayer(layer);
      for (const layer of crossingLayers()) map.addLayer(layer);
      for (const layer of avoidedLayers()) map.addLayer(layer);
      for (const layer of closureLayers()) map.addLayer(layer);
      for (const layer of layers.filter((l) => !below.has(l.id))) map.addLayer(layer);
      for (const layer of entranceLayers()) map.addLayer(layer);
      loaded.current = true;
      setReady(true);
      setBand(zoomBand(map.getZoom()));
      applyClosures(map, closuresRef.current);
      const now = eventsRef.current;
      applyEvents(map, now.events, now.atMs, visibleRef.current ?? CHIP_KINDS);
      applyFilter(map, visibleRef.current);
      map.setFilter(EVENT_LAYER_IDS.selected, selectedFilter(selectedRef.current));
      applyRoute(map, routeRef.current);
      applyView(map, routeRef.current, originalRef.current, closuresRef.current);
      fitRoute(map, routeRef.current, fitted);
      dispatch({ type: "setView", ...viewOf(map, activeRef.current) });
    });
    map.on("moveend", () => dispatch({ type: "setView", ...viewOf(map, activeRef.current) }));
    map.on("movestart", (e) => {
      if (e.originalEvent) framed.current = true; // 사람이 움직였다
    });
    map.on("zoom", () => setBand(zoomBand(map.getZoom())));
    // 클러스터 개수 아이콘은 지도가 찾을 때 그린다 (글리프 서버 없음, maplibre 6 resolver)
    map.setMissingStyleImageResolver((id) => {
      const image = renderCount(id);
      if (image && !map.hasImage(id)) map.addImage(id, image, { pixelRatio: ICON_PIXEL_RATIO });
    });
    // 사건을 누르면 (T7.5) — 하나면 카드, 여럿(클러스터·겹친 구역)이면 그 묶음 목록. 클러스터는 풀리는 줌으로도.
    // 길찾기 중엔 지도 고르기(출발·도착)가 먼저라 사건을 열지 않는다
    map.on("click", EVENT_LAYER_IDS.cluster, (e) => {
      const f = e.features?.[0];
      const id: unknown = f?.properties.cluster_id;
      const source = map.getSource(EVENT_POINT_SOURCE_ID);
      if (!f || typeof id !== "number" || !(source instanceof GeoJSONSource)) return;
      const center = e.lngLat;
      void source.getClusterExpansionZoom(id).then((zoom) => map.easeTo({ center, zoom }));
      void source.getClusterLeaves(id, MAX_LEAVES, 0).then((leaves) => {
        const ids = clickedIds(leaves);
        if (!activeRef.current && ids.length) dispatch({ type: "pick", ids });
      });
    });
    map.on("click", (e) => {
      if (activeRef.current) return;
      routeDispatch({ type: "place", place: null }); // 지도를 누르면 검색한 장소 핀·카드는 닫는다 (T7.14)
      const layers = EVENT_HIT_LAYERS.filter((id) => map.getLayer(id));
      const ids = clickedIds(map.queryRenderedFeatures(e.point, { layers }));
      if (ids.length) dispatch({ type: "pick", ids });
    });
    for (const layer of [EVENT_LAYER_IDS.cluster, ...EVENT_HIT_LAYERS]) {
      map.on("mouseenter", layer, () => {
        if (!activeRef.current) map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", layer, () => {
        if (!activeRef.current) map.getCanvas().style.cursor = "";
      });
    }
    // 길찾기가 켜져 있을 때만 reducer 가 받는다 — 출발, 다음 도착
    map.on("click", (e) => routeDispatch({ type: "pick", point: [e.lngLat.lng, e.lngLat.lat] }));
    mapRef.current = map;
    return () => {
      loaded.current = false;
      for (const pin of [fromPin, toPin, placePin]) {
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

  // 검색으로 고른 곳(장소·칸, T7.14) — 부드럽게 그리로(줌 17), 위 검색창·아래 시트에 가리지 않게
  const flown = useRef<number | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus || flown.current === focus.seq) return;
    flown.current = focus.seq;
    const run = () => {
      framed.current = true;
      map.flyTo({ center: focus.point, zoom: FOCUS_ZOOM, padding: framePadding(map) });
    };
    if (loaded.current) run();
    else map.once("load", run);
  }, [focus]);

  // 검색한 장소 핀 — 이름 말풍선 (T7.14). 다른 검색·지도 누르기·카드 닫기로 사라진다
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    placePin.current?.remove();
    placePin.current = place
      ? new Marker({ element: placePinElement(place.name), anchor: "bottom", offset: [0, 5] })
          .setLngLat(place.point)
          .addTo(map)
      : null;
  }, [place]);

  // 사건·칩이 바뀌면 사건 소스만 갱신 (T7.4)
  useEffect(() => {
    eventsRef.current = { events: events ?? [], atMs };
    const map = mapRef.current;
    if (map && loaded.current) applyEvents(map, events ?? [], atMs, visible ?? CHIP_KINDS);
  }, [events, atMs, visible]);

  // 처음 화면 — 사람·경로·주소(#map=)가 카메라를 정하기 전에 사건이 오면 한 번: 그 시각 서울 사건이 다
  // 보이게(줌 13 까지), 사건이 없으면 서울 전체(coverage). 절반 시트 위에 (T7.4)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || events === null || framed.current) return;
    const box: Bbox4 | null = eventsBounds(events, atMs) ?? coverage;
    if (!box) return;
    const run = () => {
      if (framed.current || fitted.current !== null) return;
      framed.current = true;
      map.fitBounds(
        [
          [box[0], box[1]],
          [box[2], box[3]],
        ],
        { padding: framePadding(map), maxZoom: 13, animate: false },
      );
    };
    if (loaded.current) run();
    else map.once("load", run);
  }, [events, atMs, coverage]);

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

  // 예시로 보기 (T7.11) — 그 통제 구역으로, 절반 시트 위에. 누를 때마다(순번). 줌은 구역이 그려지는 12 이상 —
  // 9.5 km 국회대로 행진은 다 담으면 11.6 이라 클러스터만 보인다
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !frame) return;
    const [w, s, e, n] = frame.bbox;
    const run = () => {
      framed.current = true;
      const bounds: [[number, number], [number, number]] = [
        [w, s],
        [e, n],
      ];
      const cam = map.cameraForBounds(bounds, { padding: framePadding(map), maxZoom: 16 });
      if (!cam) return;
      map.easeTo({ ...cam, zoom: Math.max(cam.zoom ?? AREA_MIN_ZOOM, AREA_MIN_ZOOM) });
    };
    if (loaded.current) run();
    else map.once("load", run);
  }, [frame]);

  // 고른 사건 윤곽 (T7.5)
  useEffect(() => {
    selectedRef.current = selected;
    const map = mapRef.current;
    if (map && loaded.current && map.getLayer(EVENT_LAYER_IDS.selected)) {
      map.setFilter(EVENT_LAYER_IDS.selected, selectedFilter(selected));
    }
  }, [selected]);

  // 사건 카드를 열면(T7.5) 그 사건 범위로 — 절반 시트 위에. 고른 사건이 바뀔 때 한 번(60초 갱신엔 안 움직인다).
  // 시트 목록(T7.12)의 다가오는·지난 사건은 지도 응답에 아직 없을 수 있다 — 넓은 창 목록에서도 찾는다
  const fittedEvent = useRef<string | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    const find = (xs: readonly ClosureEvent[] | null) => xs?.find((e) => e.id === selected);
    const event = selected ? (find(events) ?? find(catalog)) : undefined;
    if (!selected) fittedEvent.current = null;
    if (!map || !event || fittedEvent.current === event.id) return;
    const box = eventBbox(event); // 해제된 사건(?event= 옛 링크)도 맞춘다
    if (!box) return;
    fittedEvent.current = event.id;
    const run = () => {
      framed.current = true;
      map.fitBounds(
        [
          [box[0], box[1]],
          [box[2], box[3]],
        ],
        { padding: framePadding(map), maxZoom: 16 },
      );
    };
    if (loaded.current) run();
    else map.once("load", run);
  }, [selected, events, catalog]);

  // 길찾기를 켜고 끄면 횡단보도 점이 필요한지도 바뀐다 (원래 길 원·통제 근거가 점을 쓴다)
  useEffect(() => {
    activeRef.current = active;
    const map = mapRef.current;
    if (map && loaded.current) dispatch({ type: "setView", ...viewOf(map, active) });
  }, [active, dispatch]);

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
      <div
        ref={container}
        className={styles.map}
        role="region"
        aria-label="지도"
        data-band={band}
      />
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
