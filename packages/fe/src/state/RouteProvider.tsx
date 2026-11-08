"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type Dispatch,
  type ReactNode,
} from "react";
import { NaruApiError } from "../api/naruApiClient";
import type { LngLat } from "../map/layers/routeLayer";
import type { RouteResponse } from "../types/contracts";
import { useNaruApi } from "./ApiProvider";
import { inBbox, useClosures, type Bbox4 } from "./ClosureProvider";
import { useTime } from "./TimeProvider";

// Provider 4/4 — 길찾기: 출발·도착과 /api/route 결과. t·출발·도착이 바뀌면 다시 받는다 (이전 요청은 Abort)
export type RouteStatus = "idle" | "loading" | "ready" | "error";
export type OdField = "from" | "to";

/** 내 위치 찾기 (T5.7) — 어느 칸을 채우려는지와 진행. 거부·실패·범위 밖이면 칸은 비우고 안내 */
export type LocateStatus = "locating" | "denied" | "unavailable" | "outside";
export interface LocateState {
  which: OdField;
  status: LocateStatus;
}

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
  /** 내 위치 찾기 — 길찾기를 켜면 출발부터 (T5.7). null = 안 찾음 */
  locate: LocateState | null;
  /** 마지막으로 받은 내 위치(보행망 안) — 이 점인 칸은 "내 위치" 라고 쓴다 */
  mine: LngLat | null;
}

export type RouteAction =
  | { type: "open" }
  | { type: "close" }
  | { type: "pick"; point: LngLat }
  | { type: "unset"; which: OdField }
  | { type: "swap" }
  | { type: "setOd"; from: LngLat | null; to: LngLat | null }
  | { type: "request"; at: string }
  | { type: "receive"; at: string; route: RouteResponse }
  | { type: "fail"; error: string; code: string | null }
  | { type: "locate"; which: OdField }
  | { type: "located"; point: LngLat; coverage: Bbox4 | null }
  | { type: "locateFail"; reason: "denied" | "unavailable" };

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
    locate: null,
    mine: null,
    ...partial,
  };
}

function same(a: LngLat | null, b: LngLat | null): boolean {
  return a === b || (a !== null && b !== null && a[0] === b[0] && a[1] === b[1]);
}

/** 출발·도착이 바뀌면 이전 경로는 버린다. 내 위치 찾기도 멈춘다 (지도 누르기는 pick 이 따로 본다) */
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
    locate: null,
  };
}

function withField(state: RouteState, which: OdField, p: LngLat): RouteState {
  return which === "from" ? withOd(state, p, state.to) : withOd(state, state.from, p);
}

export function routeReducer(state: RouteState, action: RouteAction): RouteState {
  switch (action.type) {
    case "open":
      // 출발 기본값은 내 위치 — 출발이 이미 있으면(URL) 찾지 않는다 (T5.7)
      if (state.active) return state;
      return { ...state, active: true, locate: state.from ? null : FROM_MINE };
    case "close":
      return initialRouteState();
    case "pick": {
      if (!state.active) return state;
      const which: OdField | null = !state.from ? "from" : !state.to ? "to" : null;
      if (!which) return state; // 둘 다 골랐으면 무시 — 다시 고르려면 칸을 누르거나 뒤로
      const next = withField(state, which, action.point);
      // 찾던 칸을 지도로 채웠으면 찾기를 멈추고(늦은 위치는 버림), 다른 칸이면 계속 찾는다
      return state.locate && state.locate.which !== which
        ? { ...next, locate: state.locate }
        : next;
    }
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
    case "locate":
      return state.active
        ? { ...state, locate: { which: action.which, status: "locating" } }
        : state;
    case "located": {
      const l = state.locate;
      if (l?.status !== "locating") return state; // 그새 지도로 골랐거나 닫았다
      // 범위를 아직 모르면 그대로 넣는다 — BE /route 가 out_of_coverage 로 답한다
      if (action.coverage && !inBbox(action.point, action.coverage)) {
        return { ...state, locate: { ...l, status: "outside" } };
      }
      return { ...withField(state, l.which, action.point), mine: action.point };
    }
    case "locateFail": {
      const l = state.locate;
      return l?.status === "locating"
        ? { ...state, locate: { ...l, status: action.reason } }
        : state;
    }
  }
}

const FROM_MINE: LocateState = { which: "from", status: "locating" };

/** getCurrentPosition — 정확도 우선, 권한 대답 뒤 15초, 1분 안의 위치는 다시 쓴다 (지도 버튼도 같은 값) */
export const POSITION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 15_000,
  maximumAge: 60_000,
};

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

const RouteStateCtx = createContext<RouteState | null>(null);
const RouteDispatchCtx = createContext<Dispatch<RouteAction> | null>(null);

export function RouteProvider({
  children,
  initialState,
  fetchEnabled = true,
  debounceMs = 250,
}: {
  children: ReactNode;
  /** 렌더 테스트: recorded 응답을 넣고 네트워크 없이 그린다 */
  initialState?: Partial<RouteState>;
  fetchEnabled?: boolean;
  debounceMs?: number;
}) {
  const [state, dispatch] = useReducer(routeReducer, initialState, initialRouteState);
  const api = useNaruApi();
  const { t, ready } = useTime();
  const { active, from, to } = state;
  const hasInitial = initialState !== undefined;
  // 내 위치가 보행망 밖인지 — /closures/events 의 coverage (위치를 받는 순간의 값)
  const { coverage } = useClosures();
  const coverageRef = useRef(coverage);
  const locating = state.locate?.status === "locating" ? state.locate.which : null;

  useEffect(() => {
    // 마운트 뒤 URL 의 ?from=&to= 를 넣는다 (TimeProvider 의 ?t= 와 같은 방식)
    if (hasInitial) return;
    const od = odFromLocation(window.location.search);
    if (od.from || od.to) dispatch({ type: "setOd", ...od });
  }, [hasInitial]);

  useEffect(() => {
    if (!fetchEnabled || !ready || !active || !from || !to) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      dispatch({ type: "request", at: t });
      api
        .route({ from: latLngParam(from), to: latLngParam(to), departAt: t }, controller.signal)
        .then((route) => dispatch({ type: "receive", at: t, route }))
        .catch((e: unknown) => {
          if (controller.signal.aborted) return;
          const code = e instanceof NaruApiError ? (e.body?.error.code ?? null) : null;
          const msg = e instanceof Error ? e.message : "경로를 받지 못했다";
          dispatch({ type: "fail", error: msg, code });
        });
    }, debounceMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [api, t, ready, active, from, to, fetchEnabled, debounceMs]);

  useEffect(() => {
    coverageRef.current = coverage;
  }, [coverage]);

  // 내 위치 (T5.7) — 권한을 묻고 받으면 그 칸에. 찾는 동안 지도로 고르면 reducer 가 결과를 버린다
  useEffect(() => {
    if (!fetchEnabled || !locating) return;
    const geo = typeof navigator === "undefined" ? undefined : navigator.geolocation;
    if (!geo) {
      dispatch({ type: "locateFail", reason: "unavailable" });
      return;
    }
    let live = true;
    geo.getCurrentPosition(
      (pos) => {
        const point: LngLat = [pos.coords.longitude, pos.coords.latitude];
        if (live) dispatch({ type: "located", point, coverage: coverageRef.current });
      },
      (err) => {
        const reason = err.code === err.PERMISSION_DENIED ? "denied" : "unavailable";
        if (live) dispatch({ type: "locateFail", reason });
      },
      POSITION_OPTIONS,
    );
    return () => {
      live = false;
    };
  }, [locating, fetchEnabled]);

  const value = useMemo(() => state, [state]);
  return (
    <RouteStateCtx.Provider value={value}>
      <RouteDispatchCtx.Provider value={dispatch}>{children}</RouteDispatchCtx.Provider>
    </RouteStateCtx.Provider>
  );
}

export function useRoute(): RouteState {
  const v = useContext(RouteStateCtx);
  if (!v) throw new Error("RouteProvider 밖에서 useRoute 호출");
  return v;
}

export function useRouteDispatch(): Dispatch<RouteAction> {
  const v = useContext(RouteDispatchCtx);
  if (!v) throw new Error("RouteProvider 밖에서 useRouteDispatch 호출");
  return v;
}
