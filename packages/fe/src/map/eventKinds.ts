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

/** 종류 바탕(배지·행 아이콘) — 목업 01_home·03_closure 의 연한 바탕 */
export const KIND_BG: Record<EventKind, string> = {
  confirmed: COLORS.stopBg,
  soon: COLORS.slowBg,
  scheduled: COLORS.slowBg,
  zone: COLORS.zoneBg,
  released: COLORS.grayBg,
};

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

export function listedEvents(
  events: readonly ClosureEvent[],
  atMs: number,
  withLow = false,
): ListedEvent[] {
  return events
    .map((event) => ({ event, kind: eventKind(event, atMs) }))
    .filter(({ event, kind }) => kind !== "released" && (withLow || !isLow(event)))
    .sort(
      (a, b) =>
        KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
        startMs(a.event) - startMs(b.event) ||
        a.event.reason.localeCompare(b.event.reason),
    );
}

/** 지금 서울 통제 묶음 (T7.5) — 통제 중 → 1시간 안 시작 → 오늘 → 내일 → 그 뒤. 날짜는 응답 at 의 KST 날짜 */
export type GroupKey = "now" | "soon" | "today" | "tomorrow" | "later";

export interface EventGroup {
  key: GroupKey;
  items: ListedEvent[];
}

const GROUP_ORDER: readonly GroupKey[] = ["now", "soon", "today", "tomorrow", "later"];
const KST_MS = 9 * 60 * 60_000;
const DAY_MS = 24 * 60 * 60_000;

function kstDay(ms: number): string {
  return new Date(ms + KST_MS).toISOString().slice(0, 10);
}

function groupOf({ event, kind }: ListedEvent, atMs: number): GroupKey {
  if (kind === "confirmed") return "now";
  if (kind === "soon") return "soon";
  if (!event.window.start) return "later";
  const day = kstDay(Date.parse(event.window.start));
  if (day <= kstDay(atMs)) return "today";
  return day === kstDay(atMs + DAY_MS) ? "tomorrow" : "later";
}

/** withLow — 지도에서 고른 묶음(클러스터·겹친 구역)은 흐리게 그린 0.7 미만도 보여 준다 */
export function liveGroups(
  events: readonly ClosureEvent[],
  atMs: number,
  withLow = false,
): EventGroup[] {
  const by = new Map<GroupKey, ListedEvent[]>();
  for (const row of listedEvents(events, atMs, withLow)) {
    const key = groupOf(row, atMs);
    by.set(key, [...(by.get(key) ?? []), row]);
  }
  return GROUP_ORDER.flatMap((key) => {
    const items = by.get(key);
    return items ? [{ key, items }] : [];
  });
}

/** [minLng, minLat, maxLng, maxLat] */
export type Bounds = [number, number, number, number];

function boundsOf(e: ClosureEvent): Bounds | null {
  const [w, s, east, n] = e.bbox;
  const ok = [w, s, east, n].every((x) => typeof x === "number");
  return ok ? [w as number, s as number, east as number, n as number] : null;
}

function overlaps(a: Bounds, b: Bounds): boolean {
  return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
}

/**
 * 구 칩 (T6.9 → T7.5 지금 서울 통제) — 목록 사건의 구. 지도 화면(view)과 bbox 가 겹치는 사건의 구 먼저(그런
 * 사건이 많은 순), 나머지는 가나다. 구 경계는 FE 에 없어서 사건 bbox 로 본다
 */
export function districtChips(events: readonly ClosureEvent[], view: Bounds | null): string[] {
  const inView = new Map<string, number>();
  const all = new Set<string>();
  for (const e of events) {
    const b = boundsOf(e);
    const seen = view !== null && b !== null && overlaps(b, view);
    for (const d of e.districts ?? []) {
      all.add(d);
      if (seen) inView.set(d, (inView.get(d) ?? 0) + 1);
    }
  }
  const ko = (a: string, b: string) => a.localeCompare(b, "ko");
  const count = (d: string) => inView.get(d) ?? 0;
  const first = [...inView.keys()].sort((a, b) => count(b) - count(a) || ko(a, b));
  return [...first, ...[...all].filter((d) => !inView.has(d)).sort(ko)];
}

/** 고른 구를 지나는 사건만 (null = 전체) */
export function byDistrict(
  events: readonly ClosureEvent[],
  district: string | null,
): ClosureEvent[] {
  if (district === null) return [...events];
  return events.filter((e) => (e.districts ?? []).includes(district));
}
