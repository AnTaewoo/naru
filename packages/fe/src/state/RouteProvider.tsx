"use client";

import type { LngLat } from "../map/layers/routeLayer";
import type { RouteResponse } from "../types/contracts";

// Provider 4/4 — 길찾기: 출발·도착과 /api/route 결과. t·출발·도착이 바뀌면 다시 받는다 (이전 요청은 Abort)
export type RouteStatus = "idle" | "loading" | "ready" | "error";

export interface RouteState {
  /** 길찾기 화면을 켰나 — 켜져 있을 때만 지도 누르기가 출발·도착을 고른다 */
  active: boolean;
  /** [lng, lat] */
  from: LngLat | null;
  to: LngLat | null;
  status: RouteStatus;
  /** 마지막으로 받은 경로 (다시 받는 중에도 유지해 깜빡임 없음) */
  route: RouteResponse | null;
  /** 경로가 기준한 출발 시각 */
  at: string | null;
  error: string | null;
  /** Flask ErrorBody.code (INTERFACE §6) — 화면 문구를 고른다 */
  errorCode: string | null;
}

export type RouteAction =
  | { type: "open" }
  | { type: "close" }
  | { type: "pick"; point: LngLat }
  | { type: "unset"; which: "from" | "to" }
  | { type: "swap" }
  | { type: "setOd"; from: LngLat | null; to: LngLat | null }
  | { type: "request"; at: string }
  | { type: "receive"; at: string; route: RouteResponse }
  | { type: "fail"; error: string; code: string | null };

export function initialRouteState(partial: Partial<RouteState> = {}): RouteState {
  return {
    active: false,
    from: null,
    to: null,
    status: "idle",
    route: null,
    at: null,
    error: null,
    errorCode: null,
    ...partial,
  };
}

function same(a: LngLat | null, b: LngLat | null): boolean {
  return a === b || (a !== null && b !== null && a[0] === b[0] && a[1] === b[1]);
}

/** 출발·도착이 바뀌면 이전 경로는 버린다 */
function withOd(state: RouteState, from: LngLat | null, to: LngLat | null): RouteState {
  return {
    ...state,
    active: true,
    from,
    to,
    status: "idle",
    route: null,
    at: null,
    error: null,
    errorCode: null,
  };
}

export function routeReducer(state: RouteState, action: RouteAction): RouteState {
  switch (action.type) {
    case "open":
      return state.active ? state : { ...state, active: true };
    case "close":
      return initialRouteState();
    case "pick":
      if (!state.active) return state;
      if (!state.from) return withOd(state, action.point, state.to);
      if (!state.to) return withOd(state, state.from, action.point);
      return state; // 둘 다 골랐으면 무시 — 다시 고르려면 칸을 누르거나 뒤로
    case "unset":
      return withOd(
        state,
        action.which === "from" ? null : state.from,
        action.which === "to" ? null : state.to,
      );
    case "swap":
      return withOd(state, state.to, state.from);
    case "setOd":
      if (state.active && same(state.from, action.from) && same(state.to, action.to)) return state;
      return withOd(state, action.from, action.to);
    case "request":
      return { ...state, status: "loading", error: null, errorCode: null };
    case "receive":
      return {
        ...state,
        status: "ready",
        route: action.route,
        at: action.at,
        error: null,
        errorCode: null,
      };
    case "fail":
      return {
        ...state,
        status: "error",
        route: null,
        error: action.error,
        errorCode: action.code,
      };
  }
}

/** "lat,lng" (INTERFACE §2 질의) → [lng, lat]. 숫자가 아니거나 범위 밖이면 null */
export function parseLatLng(s: string | null | undefined): LngLat | null {
  const parts = (s ?? "").split(",");
  if (parts.length !== 2) return null;
  const [lat, lng] = parts.map((x) => (x.trim() === "" ? Number.NaN : Number(x)));
  if (lat === undefined || lng === undefined || !Number.isFinite(lat) || !Number.isFinite(lng))
    return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return [lng, lat];
}

/** [lng, lat] → "lat,lng" */
export function latLngParam(p: LngLat): string {
  return `${p[1]},${p[0]}`;
}

/** URL `?from=lat,lng&to=lat,lng` — 시연은 README 의 주소 (t 와 함께) */
export function odFromLocation(search: string): { from: LngLat | null; to: LngLat | null } {
  const q = new URLSearchParams(search);
  return { from: parseLatLng(q.get("from")), to: parseLatLng(q.get("to")) };
}
