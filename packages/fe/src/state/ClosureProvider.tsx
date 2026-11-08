"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import { NaruApiError } from "../api/naruApiClient";
import type { ClosureEvent, FeatureCollection } from "../types/contracts";
import { useNaruApi } from "./ApiProvider";
import { useTime } from "./TimeProvider";

// Provider 3/4 — /api/closures 결과. t·bbox 가 바뀌면 다시 받는다 (이전 요청은 Abort). CONVENTIONS §5.5
export type ClosureStatus = "idle" | "loading" | "ready" | "error";

export interface ClosureState {
  status: ClosureStatus;
  /** 마지막으로 받은 결과 (loading 중에도 유지해 깜빡임 없음) */
  closures: FeatureCollection;
  /** 결과가 기준한 시각·bbox */
  at: string | null;
  bbox: string;
  error: string | null;
  /** 통제 불러오기 목록 (GET /closures/events, T5.4). null = 아직 못 받음 */
  events: ClosureEvent[] | null;
  eventsError: string | null;
  /** 지도 맞춤 요청 — 같은 범위를 다시 눌러도 맞추도록 순번을 올린다 (MapView 가 본다) */
  focus: { bbox: Bbox4; seq: number } | null;
}

/** [minLng, minLat, maxLng, maxLat] */
export type Bbox4 = [number, number, number, number];

/** 사건의 bbox (생성 타입이 unknown 튜플이라 숫자를 확인한다) */
export function eventBbox(e: ClosureEvent): Bbox4 | null {
  const [w, s, n1, n2] = e.bbox;
  return [w, s, n1, n2].every((x) => typeof x === "number") ? ([w, s, n1, n2] as Bbox4) : null;
}

export type ClosureAction =
  | { type: "request"; at: string; bbox: string }
  | { type: "receive"; at: string; bbox: string; closures: FeatureCollection }
  | { type: "fail"; error: string }
  | { type: "setBbox"; bbox: string }
  | { type: "receiveEvents"; events: ClosureEvent[] }
  | { type: "failEvents"; error: string }
  | { type: "focus"; bbox: Bbox4 };

export const EMPTY_CLOSURES: FeatureCollection = { type: "FeatureCollection", features: [] };
/** 광화문 일대 — 데모 범위(BE Settings.districts 종로·중구) 안의 기본 bbox. 지도가 움직이면 setBbox */
export const DEFAULT_BBOX = "126.965,37.555,126.990,37.580";

export function initialClosureState(partial: Partial<ClosureState> = {}): ClosureState {
  return {
    status: "idle",
    closures: EMPTY_CLOSURES,
    at: null,
    bbox: DEFAULT_BBOX,
    error: null,
    events: null,
    eventsError: null,
    focus: null,
    ...partial,
  };
}

export function closureReducer(state: ClosureState, action: ClosureAction): ClosureState {
  switch (action.type) {
    case "request":
      return { ...state, status: "loading", error: null };
    case "receive":
      return {
        ...state,
        status: "ready",
        closures: action.closures,
        at: action.at,
        bbox: action.bbox,
        error: null,
      };
    case "fail":
      return { ...state, status: "error", error: action.error };
    case "setBbox":
      return state.bbox === action.bbox ? state : { ...state, bbox: action.bbox };
    case "receiveEvents":
      return { ...state, events: action.events, eventsError: null };
    case "failEvents":
      return { ...state, eventsError: action.error };
    case "focus":
      return { ...state, focus: { bbox: action.bbox, seq: (state.focus?.seq ?? 0) + 1 } };
  }
}

const ClosureStateCtx = createContext<ClosureState | null>(null);
const ClosureDispatchCtx = createContext<Dispatch<ClosureAction> | null>(null);

export function ClosureProvider({
  children,
  initialState,
  fetchEnabled = true,
  debounceMs = 250,
}: {
  children: ReactNode;
  /** 렌더 테스트: recorded 응답을 넣고 네트워크 없이 그린다 */
  initialState?: Partial<ClosureState>;
  fetchEnabled?: boolean;
  debounceMs?: number;
}) {
  const [state, dispatch] = useReducer(closureReducer, initialState, initialClosureState);
  const api = useNaruApi();
  const { t, ready } = useTime();
  const bbox = state.bbox;

  useEffect(() => {
    if (!fetchEnabled || !ready) return; // 시각이 정해지기 전엔 받지 않는다
    const controller = new AbortController();
    const timer = setTimeout(() => {
      dispatch({ type: "request", at: t, bbox });
      api
        .closures({ bbox, at: t }, controller.signal)
        .then((closures) => dispatch({ type: "receive", at: t, bbox, closures }))
        .catch((e: unknown) => {
          if (controller.signal.aborted) return;
          const msg = e instanceof NaruApiError ? e.message : "통제 정보를 받지 못했다";
          dispatch({ type: "fail", error: msg });
        });
    }, debounceMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [api, t, ready, bbox, fetchEnabled, debounceMs]);

  // 통제 불러오기 목록 — 시각·범위와 상관없어 마운트 때 한 번 (ADR-010)
  useEffect(() => {
    if (!fetchEnabled) return;
    const controller = new AbortController();
    api
      .events({}, controller.signal)
      .then((r) => dispatch({ type: "receiveEvents", events: r.events }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        const msg = e instanceof NaruApiError ? e.message : "통제 목록을 받지 못했다";
        dispatch({ type: "failEvents", error: msg });
      });
    return () => controller.abort();
  }, [api, fetchEnabled]);

  const value = useMemo(() => state, [state]);
  return (
    <ClosureStateCtx.Provider value={value}>
      <ClosureDispatchCtx.Provider value={dispatch}>{children}</ClosureDispatchCtx.Provider>
    </ClosureStateCtx.Provider>
  );
}

export function useClosures(): ClosureState {
  const v = useContext(ClosureStateCtx);
  if (!v) throw new Error("ClosureProvider 밖에서 useClosures 호출");
  return v;
}

export function useClosureDispatch(): Dispatch<ClosureAction> {
  const v = useContext(ClosureDispatchCtx);
  if (!v) throw new Error("ClosureProvider 밖에서 useClosureDispatch 호출");
  return v;
}
