// 알림 상태 — Provider 없이 모듈 스토어 + useSyncExternalStore (ADR-014 D, T7.10). 순수 부분(판정·라벨)은
// 여기, 브라우저·네트워크는 usePush. 여러 컴포넌트(시트 칸·사건 카드·지도)가 같은 상태를 본다
import type { WatchArea } from "../types/contracts";
import type { PushState } from "./support";

export const ENDPOINT_KEY = "naru.push.v1"; // { endpoint } — 이 브라우저 구독의 손잡이
export const LABEL_KEY = "naru.watch-labels.v1"; // { [관심 지역 id]: 사건 이름 } — 화면용, 이 기기에만
export const WATCH_RADIUS_M = 500; // ☆ 이 근처 알림 받기 기본 반경 (ADR-014 C)

export interface PushStore {
  support: PushState;
  /** 이 브라우저가 서버에 구독돼 있나 — endpoint 는 localStorage 에도 */
  endpoint: string | null;
  areas: WatchArea[];
  labels: Record<string, string>;
  busy: boolean;
  /** PUSH_KO 열쇠 — 마지막 실패 */
  error: "failed" | "limit" | null;
}

export const initialStore: PushStore = {
  support: "unknown",
  endpoint: null,
  areas: [],
  labels: {},
  busy: false,
  error: null,
};

let current: PushStore = initialStore;
const listeners = new Set<() => void>();

export function readStore(): PushStore {
  return current;
}

export function setStore(patch: Partial<PushStore>): void {
  current = { ...current, ...patch };
  for (const l of listeners) l();
}

export function subscribeStore(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** 테스트·초기화용 */
export function resetStore(next: Partial<PushStore> = {}): void {
  current = { ...initialStore, ...next };
  for (const l of listeners) l();
}

/** 저장 관심 지역 중 이 점(사건 중심)과 같은 곳 — 서버가 소수 7자리로 돌려준다 */
export function watchedArea(
  areas: readonly WatchArea[],
  point: readonly [number, number],
): WatchArea | null {
  const [lng, lat] = point;
  return (
    areas.find(
      (a) => a.kind === "saved" && Math.abs(a.lng - lng) < 1e-6 && Math.abs(a.lat - lat) < 1e-6,
    ) ?? null
  );
}

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readEndpoint(store: Storage | null = storage()): string | null {
  try {
    const raw = store?.getItem(ENDPOINT_KEY);
    const v: unknown = raw ? JSON.parse(raw) : null;
    const ep = typeof v === "object" && v !== null ? (v as { endpoint?: unknown }).endpoint : null;
    return typeof ep === "string" && ep.startsWith("https://") ? ep : null;
  } catch {
    return null;
  }
}

export function writeEndpoint(endpoint: string | null, store: Storage | null = storage()): void {
  try {
    if (endpoint) store?.setItem(ENDPOINT_KEY, JSON.stringify({ endpoint }));
    else store?.removeItem(ENDPOINT_KEY);
  } catch {
    // 막힌 저장소 — 이 화면 동안만
  }
}

export function readLabels(store: Storage | null = storage()): Record<string, string> {
  try {
    const raw = store?.getItem(LABEL_KEY);
    const v: unknown = raw ? JSON.parse(raw) : {};
    if (typeof v !== "object" || v === null) return {};
    const out: Record<string, string> = {};
    for (const [k, val] of Object.entries(v)) if (typeof val === "string") out[k] = val;
    return out;
  } catch {
    return {};
  }
}

export function writeLabels(
  labels: Record<string, string>,
  store: Storage | null = storage(),
): void {
  try {
    store?.setItem(LABEL_KEY, JSON.stringify(labels));
  } catch {
    // 막힌 저장소
  }
}
