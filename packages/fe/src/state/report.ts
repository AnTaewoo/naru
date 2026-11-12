// 통제 제보 (T7.15, INTERFACE §8) — 지금 위치 → 가장 가까운 횡단보도 → "막혔어요 / 열렸어요". 기록만 —
// 길찾기·확신도에 안 쓴다. 위치 좌표는 횡단보도를 찾을 때까지만 들고 있다가 버린다(서버도 저장 안 함).
// 상태는 RouteProvider 가 들고(Provider 4개 그대로), 위치·요청은 그 Provider 의 useEffect 에서
import { NaruApiError, crosswalkLngLat } from "../api/naruApiClient";
import type { LngLat } from "../map/layers/routeLayer";
import type { NearestCrosswalkResponse, ReportRequest } from "../types/contracts";

export type ReportPhase = "locating" | "finding" | "ready" | "sending" | "sent" | "error";
export type ReportFailure =
  "denied" | "unavailable" | "inaccurate" | "none" | "too_many" | "failed";
export type ReportValue = ReportRequest["state"];

/** 위치 정확도 상한(m) — 계약 accuracy_m 0~1000 (INTERFACE §8.2) */
export const ACCURACY_MAX_M = 1000;
export const DEVICE_KEY = "naru.device.v1";
const DEVICE_RE = /^[A-Za-z0-9-]{16,64}$/;

export interface ReportCrosswalk {
  id: string;
  /** 교차로명 */
  name: string;
  district: string;
  point: LngLat;
  distanceM: number;
}

export interface ReportState {
  phase: ReportPhase;
  /** 현장 검증(?mode=field) — 출처 field */
  field: boolean;
  /** 지금 위치 — 횡단보도를 찾는 동안만 */
  point: LngLat | null;
  /** 위치 정확도(m, 반올림) */
  accuracyM: number | null;
  crosswalk: ReportCrosswalk | null;
  /** 보내는·보낸 값 */
  sent: ReportValue | null;
  failure: ReportFailure | null;
}

export type ReportEvent =
  | { type: "start"; field: boolean }
  | { type: "located"; point: LngLat; accuracyM: number }
  | { type: "found"; crosswalk: ReportCrosswalk | null }
  | { type: "send"; value: ReportValue }
  | { type: "sent" }
  | { type: "fail"; failure: ReportFailure }
  | { type: "retry" }
  | { type: "close" };

function locating(field: boolean): ReportState {
  return {
    phase: "locating",
    field,
    point: null,
    accuracyM: null,
    crosswalk: null,
    sent: null,
    failure: null,
  };
}

export function reportReducer(s: ReportState | null, e: ReportEvent): ReportState | null {
  if (e.type === "start") return locating(e.field);
  if (e.type === "close" || !s) return null;
  switch (e.type) {
    case "located":
      if (s.phase !== "locating") return s;
      return e.accuracyM > ACCURACY_MAX_M
        ? { ...s, phase: "error", failure: "inaccurate", accuracyM: e.accuracyM }
        : { ...s, phase: "finding", point: e.point, accuracyM: e.accuracyM };
    case "found":
      if (s.phase !== "finding") return s;
      return e.crosswalk
        ? { ...s, phase: "ready", point: null, crosswalk: e.crosswalk }
        : { ...s, phase: "error", point: null, failure: "none" };
    case "send":
      return s.phase === "ready" ? { ...s, phase: "sending", sent: e.value } : s;
    case "sent":
      return s.phase === "sending" ? { ...s, phase: "sent" } : s;
    case "fail":
      return s.phase === "sent" ? s : { ...s, phase: "error", point: null, failure: e.failure };
    case "retry":
      // 보내다 실패했으면 같은 횡단보도로 다시, 그 밖(위치·없음·429)은 위치부터
      return s.failure === "failed" && s.crosswalk
        ? { ...s, phase: "ready", failure: null, sent: null }
        : locating(s.field);
  }
}

export function crosswalkOf(r: NearestCrosswalkResponse): ReportCrosswalk | null {
  const c = r.crosswalk;
  const point = c ? crosswalkLngLat(c) : null;
  if (!c || !point) return null;
  return { id: c.id, name: c.name, district: c.district, point, distanceM: c.distance_m };
}

/** 보내기 실패 — 같은 기기·같은 횡단보도 간격(429)만 따로 */
export function failureOf(e: unknown): ReportFailure {
  return e instanceof NaruApiError && e.body?.error.code === "too_many_reports"
    ? "too_many"
    : "failed";
}

export function fieldModeFromLocation(search: string): boolean {
  return new URLSearchParams(search).get("mode") === "field";
}

let sessionToken: string | null = null;

function newToken(): string {
  return crypto.randomUUID();
}

/** 기기 토큰 — 이 브라우저에 한 번 만들어 둔 무작위 값(서버는 해시만). 저장소가 막히면 이 화면 동안만 */
export function deviceToken(storage: Storage | null): string {
  try {
    const kept = storage?.getItem(DEVICE_KEY);
    if (kept && DEVICE_RE.test(kept)) return kept;
    if (storage) {
      const made = newToken();
      storage.setItem(DEVICE_KEY, made);
      return made;
    }
  } catch {
    // 사생활 모드 등 — 아래 화면 동안의 값
  }
  sessionToken ??= newToken();
  return sessionToken;
}
