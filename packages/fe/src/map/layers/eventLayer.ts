// 순수 함수: 지금 지도 사건(/closures/events v0.14) → 클러스터용 중심점·통제 구역 + MapLibre 레이어 스펙
// (T7.4, ADR-014 A). 줌 12 아래 사건 중심점 클러스터, 12 부터 구역(BE 가 접수 때 만든 area), 15 부터 횡단보도
// 점(closureLayer). 공간 연산은 하지 않는다 — 구역·중심은 BE 값 그대로 (CLAUDE.md §3-5)
import type { ClosureEvent } from "../../types/contracts";
import { COLORS } from "../colors";
import { KIND_COLOR, chipOf, eventKind, isLow, type ChipKind, type EventKind } from "../eventKinds";

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
