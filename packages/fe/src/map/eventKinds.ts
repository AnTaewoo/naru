// 지금 지도 사건의 종류·칩·줌 단계 (T7.4, ADR-014 A) — 지도·칩·시트가 같이 쓴다. 순수 함수
import type { ClosureEvent, Status } from "../types/contracts";
import { COLORS } from "./colors";

/** 줌 경계 (P7 계획 정할 것 9) — 12 아래 클러스터, 12~15 구역, 15 부터 횡단보도 */
export const AREA_MIN_ZOOM = 12;
export const CROSSWALK_MIN_ZOOM = 15;

export type ZoomBand = "cluster" | "area" | "crosswalk";

export function zoomBand(zoom: number): ZoomBand {
  if (zoom < AREA_MIN_ZOOM) return "cluster";
  return zoom < CROSSWALK_MIN_ZOOM ? "area" : "crosswalk";
}

/** 지도의 사건 종류 — status(응답 at 기준 가장 심한)와 시작까지 남은 시간 */
export type EventKind = "confirmed" | "soon" | "scheduled" | "zone" | "released";
/** 칩 = 필터. 예정 = 1시간 안 + 그 뒤(오늘·내일) */
export type ChipKind = "confirmed" | "scheduled" | "zone";
export const CHIP_KINDS: readonly ChipKind[] = ["confirmed", "scheduled", "zone"];

/** "1시간 안에 시작" — 시작이 at + 60분 안. 이미 시작했는데 근거가 없어 예정인 사건도 여기(진한 주황) */
export const SOON_MS = 60 * 60_000;
/** 이보다 낮으면 흐린 회색 점선 — 지도에만, 칩 수에는 안 센다 (라우터 review_confidence 와 같다) */
export const LOW_CONFIDENCE = 0.7;

export function eventKind(e: ClosureEvent, atMs: number): EventKind {
  switch (e.status) {
    case "confirmed":
      return "confirmed";
    case "zone_scheduled":
      return "zone";
    case "released":
      return "released";
    case "scheduled": {
      const start = e.window.start ? Date.parse(e.window.start) : Number.POSITIVE_INFINITY;
      return start - atMs <= SOON_MS ? "soon" : "scheduled";
    }
  }
}

export function chipOf(kind: EventKind): ChipKind | null {
  if (kind === "soon" || kind === "scheduled") return "scheduled";
  if (kind === "released") return null;
  return kind;
}

export function isLow(e: ClosureEvent): boolean {
  return e.confidence < LOW_CONFIDENCE;
}

/** 칩 수 — 해제·확신도 0.7 미만은 안 센다 */
export function chipCounts(
  events: readonly ClosureEvent[],
  atMs: number,
): Record<ChipKind, number> {
  const out: Record<ChipKind, number> = { confirmed: 0, scheduled: 0, zone: 0 };
  for (const e of events) {
    const chip = chipOf(eventKind(e, atMs));
    if (chip && !isLow(e)) out[chip] += 1;
  }
  return out;
}

/** 칩 → 횡단보도 점(/closures) 의 상태 필터 */
const CHIP_STATUS: Record<ChipKind, Status> = {
  confirmed: "confirmed",
  scheduled: "scheduled",
  zone: "zone_scheduled",
};

export function chipStatuses(visible: readonly ChipKind[]): Status[] {
  return visible.map((k) => CHIP_STATUS[k]);
}

export const KIND_COLOR: Record<EventKind, string> = {
  confirmed: COLORS.stop,
  soon: COLORS.soon,
  scheduled: COLORS.slow,
  zone: COLORS.zone,
  released: COLORS.gray,
};

/** 목록·시간표의 사건 (T7.4) — 칩과 같은 기준(해제·확신도 0.7 미만 빼고), 통제 중 → 1시간 안 → 예정 →
 * 예정 구역, 같으면 시작 이른 순 */
export interface ListedEvent {
  event: ClosureEvent;
  kind: EventKind;
}

const KIND_ORDER: Record<EventKind, number> = {
  confirmed: 0,
  soon: 1,
  scheduled: 2,
  zone: 3,
  released: 4,
};

function startMs(e: ClosureEvent): number {
  return e.window.start ? Date.parse(e.window.start) : Number.POSITIVE_INFINITY;
}

export function listedEvents(events: readonly ClosureEvent[], atMs: number): ListedEvent[] {
  return events
    .map((event) => ({ event, kind: eventKind(event, atMs) }))
    .filter(({ event, kind }) => kind !== "released" && !isLow(event))
    .sort(
      (a, b) =>
        KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
        startMs(a.event) - startMs(b.event) ||
        a.event.reason.localeCompare(b.event.reason),
    );
}
