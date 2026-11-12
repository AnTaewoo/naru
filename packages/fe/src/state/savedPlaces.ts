// ☆ 저장한 장소 (T7.14) — 이 기기 브라우저에만(localStorage, 계정 없음). 읽기·쓰기가 막혀도 앱은 그대로
import { useCallback, useEffect, useState } from "react";
import type { PlacePick } from "./RouteProvider";

export const SAVED_KEY = "naru.saved-places.v1";
/** 저장 개수 — 넘으면 오래된 것부터 뺀다 */
export const SAVED_MAX = 20;

function isPick(x: unknown): x is PlacePick {
  if (typeof x !== "object" || x === null) return false;
  const p = x as Record<string, unknown>;
  const point = p["point"];
  return (
    typeof p["id"] === "string" &&
    typeof p["name"] === "string" &&
    typeof p["address"] === "string" &&
    Array.isArray(point) &&
    point.length === 2 &&
    point.every((v) => typeof v === "number")
  );
}

export function readSaved(storage: Storage | null): PlacePick[] {
  try {
    const raw = storage?.getItem(SAVED_KEY);
    const list: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter(isPick) : [];
  } catch {
    return []; // 깨진 값·막힌 저장소
  }
}

export function writeSaved(storage: Storage | null, list: readonly PlacePick[]): void {
  try {
    storage?.setItem(SAVED_KEY, JSON.stringify(list));
  } catch {
    // 사생활 모드 등 — 저장 안 됨, 화면은 그대로
  }
}

/** 있으면 빼고, 없으면 맨 앞에 */
export function toggleSaved(list: readonly PlacePick[], place: PlacePick): PlacePick[] {
  if (list.some((p) => p.id === place.id)) return list.filter((p) => p.id !== place.id);
  return [place, ...list].slice(0, SAVED_MAX);
}

/** 이 브라우저 localStorage — 막혀 있으면 null (기기 토큰 T7.15 도 같이 쓴다) */
export function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** 저장한 장소 — 마운트 뒤에 읽는다(서버 렌더와 같게), 누르면 저장소에도 */
export function useSavedPlaces(): {
  saved: PlacePick[];
  toggle: (place: PlacePick) => void;
} {
  const [saved, setSaved] = useState<PlacePick[]>([]);
  useEffect(() => {
    setSaved(readSaved(browserStorage()));
  }, []);
  const toggle = useCallback((place: PlacePick) => {
    const next = toggleSaved(readSaved(browserStorage()), place);
    writeSaved(browserStorage(), next);
    setSaved(next);
  }, []);
  return { saved, toggle };
}
