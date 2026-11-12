// 순수 함수: 행진 키프레임(/closures/events/{id}/march, INTERFACE §3.2) → 그 시각의 예상 위치(두 키프레임
// 사이 보간) → MapLibre 소스·레이어 (ADR-015 G, T7.16). heatmap(표본이 겹칠수록 진하게), 예상 위치 원(크게 —
// 최소 250 m·화면 최소 26 px, 채움·테두리 + 중심 글로우; 태우 11/11 "슬라이더 시각의 군집이 크게"). 표시만 —
// 횡단보도 통제는 사건 전 구역(태우 11/12). 공간 연산은 원 폴리곤(표시용)뿐 — 값은 BE 키프레임 그대로
import type {
  ExpressionSpecification,
  GeoJSONSourceSpecification,
  LayerSpecification,
} from "maplibre-gl";
import type { MarchKeyframe, MarchResponse } from "../../types/contracts";
import { COLORS } from "../colors";

export const MARCH_HEAT_SOURCE_ID = "naru-march-heat";
export const MARCH_CIRCLE_SOURCE_ID = "naru-march-circle";
export const MARCH_LAYER_IDS = {
  heat: "naru-march-heat",
  circleGlow: "naru-march-circle-glow",
  circleFill: "naru-march-circle-fill",
  circleLine: "naru-march-circle-line",
} as const;

export type LngLat = [number, number];

/** 그 시각의 예상 위치 — 점은 가까운 키프레임 것, 중심·반경·P 는 두 키프레임 사이 선형 보간 */
export interface MarchFrame {
  points: LngLat[];
  center: LngLat;
  radiusM: number;
  /** 경로 위 횡단보도 id → 막혀 있을 확률 */
  p: Record<string, number>;
}

function pair(xs: readonly unknown[]): LngLat | null {
  const [a, b] = xs;
  return typeof a === "number" && typeof b === "number" ? [a, b] : null;
}

function flat(kf: MarchKeyframe): LngLat[] {
  const out: LngLat[] = [];
  for (const sample of kf.samples)
    for (const pt of sample) {
      const p = pair(pt);
      if (p) out.push(p);
    }
  return out;
}

function lerp(a: number, b: number, f: number): number {
  return a + (b - a) * f;
}

/** t(ms)의 프레임. 키프레임 범위 밖(통제 시간 밖)이면 null */
export function frameAt(body: MarchResponse, tMs: number): MarchFrame | null {
  const kfs = body.keyframes;
  const first = kfs[0];
  const last = kfs[kfs.length - 1];
  if (!first || !last) return null;
  const t0 = Date.parse(first.t);
  const t1 = Date.parse(last.t);
  if (tMs < t0 || tMs > t1) return null;
  // 간격이 일정(step_s)하니 인덱스로 바로
  const stepMs = body.step_s * 1000;
  const i = Math.min(kfs.length - 1, Math.floor((tMs - t0) / stepMs));
  const a = kfs[i];
  if (!a) return null;
  const b = kfs[i + 1] ?? a;
  const f = b === a ? 0 : Math.min(1, Math.max(0, (tMs - Date.parse(a.t)) / stepMs));
  const ca = pair(a.center);
  const cb = pair(b.center);
  if (!ca || !cb) return null;
  const p: Record<string, number> = {};
  for (const [id, pa] of Object.entries(a.crosswalks)) p[id] = lerp(pa, b.crosswalks[id] ?? pa, f);
  return {
    points: flat(f < 0.5 ? a : b),
    center: [lerp(ca[0], cb[0], f), lerp(ca[1], cb[1], f)],
    radiusM: lerp(a.radius_m, b.radius_m, f),
    p,
  };
}

const EMPTY = { type: "FeatureCollection" as const, features: [] };

interface PointCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Point"; coordinates: LngLat };
    properties: Record<string, unknown>;
  }[];
}

export function marchHeatPoints(frame: MarchFrame | null): PointCollection {
  if (!frame) return EMPTY;
  return {
    type: "FeatureCollection",
    features: frame.points.map((c) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: c },
      properties: {},
    })),
  };
}

const M_PER_DEG_LAT = 111_320;
/** 원 최소 반경(m) — 행렬 200 m + 여유. 표본 퍼짐이 이보다 작아도(출발 직후) 이만큼은 그린다 (태우 11/11 "크게") */
export const CIRCLE_MIN_M = 250;
/** 화면에서 원이 이보다 작게 보이지 않게(px) — 축소해도 군집이 보이게 */
export const CIRCLE_MIN_PX = 26;
/** 줌 0 에서 1 px 당 m (위도 37.55, 서울) — 미터 반경을 px 로 */
const M_PER_PX_Z0 = 156_543.03 * Math.cos((37.55 * Math.PI) / 180);

export interface CircleCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Polygon"; coordinates: LngLat[][] } | { type: "Point"; coordinates: LngLat };
    properties: { radius_m: number };
  }[];
}
const EMPTY_CIRCLE: CircleCollection = { type: "FeatureCollection", features: [] };

/** 예상 위치 원 — 폴리곤(64 꼭짓점, 반경 max(퍼짐, 250 m)) + 중심 점(글로우 레이어용, radius_m). 프레임이 없으면 비움 */
export function marchCircle(frame: MarchFrame | null): CircleCollection {
  if (!frame) return EMPTY_CIRCLE;
  const radiusM = Math.max(frame.radiusM, CIRCLE_MIN_M);
  const [lng, lat] = frame.center;
  const dLat = radiusM / M_PER_DEG_LAT;
  const dLng = radiusM / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  const ring: LngLat[] = [];
  for (let k = 0; k <= 64; k += 1) {
    const a = (k / 64) * 2 * Math.PI;
    ring.push([lng + dLng * Math.cos(a), lat + dLat * Math.sin(a)]);
  }
  const properties = { radius_m: radiusM };
  return {
    type: "FeatureCollection",
    features: [
      { type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties },
      { type: "Feature", geometry: { type: "Point", coordinates: frame.center }, properties },
    ],
  };
}

/** 줌 z 에서 radius_m 을 px 로 — 최소 CIRCLE_MIN_PX. 줌 식은 interpolate 의 입력으로만 쓸 수 있어 단계마다 max */
function glowRadius(z: number): ExpressionSpecification {
  return ["max", CIRCLE_MIN_PX, ["*", ["get", "radius_m"], 2 ** z / M_PER_PX_Z0]];
}

export function marchSource(
  data: PointCollection | ReturnType<typeof marchCircle>,
): GeoJSONSourceSpecification {
  return { type: "geojson", data };
}

const HEAT_RAMP: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["heatmap-density"],
  0,
  "rgba(239, 108, 0, 0)",
  0.2,
  "rgba(245, 213, 138, 0.55)",
  0.4,
  "rgba(245, 163, 0, 0.7)",
  0.6,
  "rgba(240, 127, 31, 0.8)",
  0.8,
  "rgba(239, 108, 0, 0.9)",
  1,
  "rgba(229, 50, 45, 0.95)",
];

/** 레이어 4장 — heatmap, 예상 위치 원(글로우·채움·테두리) (고른 행진 사건에만 데이터가 있다). 횡단보도 P 점은
 * 태우 11/12 뺐다 — 행진도 횡단보도 통제는 사건 전 구역, 군집은 표시만 */
export function marchLayers(): LayerSpecification[] {
  return [
    {
      id: MARCH_LAYER_IDS.heat,
      type: "heatmap",
      source: MARCH_HEAT_SOURCE_ID,
      paint: {
        "heatmap-weight": 1,
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 11, 0.9, 16, 1.8],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 11, 14, 16, 40],
        "heatmap-color": HEAT_RAMP,
        "heatmap-opacity": 0.85,
      },
    },
    {
      // 축소해도 보이는 군집 — 미터 반경을 px 로, 최소 26 px, 가장자리는 흐리게
      id: MARCH_LAYER_IDS.circleGlow,
      type: "circle",
      source: MARCH_CIRCLE_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-color": COLORS.soon,
        "circle-opacity": 0.28,
        "circle-blur": 0.5,
        "circle-radius": [
          "interpolate",
          ["exponential", 2],
          ["zoom"],
          9,
          glowRadius(9),
          12,
          glowRadius(12),
          14,
          glowRadius(14),
          16,
          glowRadius(16),
          18,
          glowRadius(18),
        ],
      },
    },
    {
      id: MARCH_LAYER_IDS.circleFill,
      type: "fill",
      source: MARCH_CIRCLE_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": COLORS.soon, "fill-opacity": 0.22 },
    },
    {
      id: MARCH_LAYER_IDS.circleLine,
      type: "line",
      source: MARCH_CIRCLE_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "line-color": COLORS.soon, "line-width": 3, "line-opacity": 0.9 },
    },
  ];
}
