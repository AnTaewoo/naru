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
import type { ClosureEvent, DataAsOf, FeatureCollection } from "../types/contracts";
import { useNaruApi } from "./ApiProvider";
import { useTime } from "./TimeProvider";

// Provider 3/4 — 지금 지도 사건(/api/closures/events?at=t, 60초 ETag)과 화면의 횡단보도(/api/closures).
// t·화면이 바뀌면 다시 받는다 (이전 요청은 Abort). CONVENTIONS §5.5, T7.4
export type ClosureStatus = "idle" | "loading" | "ready" | "error";

export interface ClosureState {
  status: ClosureStatus;
  /** 마지막으로 받은 결과 (loading 중에도 유지해 깜빡임 없음) */
  closures: FeatureCollection;
  /** 결과가 기준한 시각·bbox */
  at: string | null;
  bbox: string;
  error: string | null;
  /** 지금 지도 사건 (GET /closures/events?at=t, ADR-014 A). null = 아직 못 받음 */
  events: ClosureEvent[] | null;
  /** 사건 status 의 기준 시각 (응답 at) */
  eventsAt: string | null;
  /** 마지막 사건 응답의 ETag — 60초 요청의 If-None-Match */
  eventsEtag: string | null;
  /** 300건 상한에 잘렸나 */
  truncated: boolean;
  eventsError: string | null;
  /** 보행망 범위 (같은 응답의 coverage, INTERFACE v0.10) — 내 위치가 밖이면 안내 (T5.7). null = 모름 */
  coverage: Bbox4 | null;
  /** 출처별 기준 시각 (같은 응답의 data_as_of, v0.12) — 목록 위에 쓴다 (T5.9). null = 모름 */
  dataAsOf: DataAsOf | null;
  /** 지도 맞춤 요청 — 같은 범위를 다시 눌러도 맞추도록 순번을 올린다 (MapView 가 본다) */
  focus: { bbox: Bbox4; seq: number } | null;
}

/** [minLng, minLat, maxLng, maxLat] */
export type Bbox4 = [number, number, number, number];

/** 숫자 4개면 Bbox4 (생성 타입이 unknown 튜플이라 숫자를 확인한다) */
export function asBbox4(xs: readonly unknown[]): Bbox4 | null {
  const [w, s, e, n] = xs;
  if (xs.length !== 4) return null;
  if (typeof w !== "number" || typeof s !== "number") return null;
  if (typeof e !== "number" || typeof n !== "number") return null;
  return [w, s, e, n];
}

/** 사건의 bbox */
export function eventBbox(e: ClosureEvent): Bbox4 | null {
  return asBbox4(e.bbox);
}

/** [lng, lat] 가 bbox 안(경계 포함)인가 */
export function inBbox(p: readonly [number, number], b: Bbox4): boolean {
  return b[0] <= p[0] && p[0] <= b[2] && b[1] <= p[1] && p[1] <= b[3];
}

export type ClosureAction =
  | { type: "request"; at: string; bbox: string }
  | { type: "receive"; at: string; bbox: string; closures: FeatureCollection }
  | { type: "fail"; error: string }
  | { type: "setBbox"; bbox: string }
  | {
      type: "receiveEvents";
      events: ClosureEvent[];
      at: string;
      etag: string | null;
      truncated: boolean;
      coverage: Bbox4 | null;
      dataAsOf: DataAsOf | null;
    }
  | { type: "failEvents"; error: string }
  | { type: "focus"; bbox: Bbox4 };

export const EMPTY_CLOSURES: FeatureCollection = { type: "FeatureCollection", features: [] };
/** 처음 화면 광화문 일대 — 서비스 범위(BE Settings.districts 서울 25개 구, T6.9) 안. 지도가 움직이면 setBbox */
export const DEFAULT_BBOX = "126.965,37.555,126.990,37.580";

export function initialClosureState(partial: Partial<ClosureState> = {}): ClosureState {
  return {
    status: "idle",
    closures: EMPTY_CLOSURES,
    at: null,
    bbox: DEFAULT_BBOX,
    error: null,
    events: null,
    eventsAt: null,
    eventsEtag: null,
    truncated: false,
    eventsError: null,
    coverage: null,
    dataAsOf: null,
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
      return {
        ...state,
        events: action.events,
        eventsAt: action.at,
        eventsEtag: action.etag,
        truncated: action.truncated,
        coverage: action.coverage,
        dataAsOf: action.dataAsOf,
        eventsError: null,
      };
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
  pollMs = 60_000,
}: {
  children: ReactNode;
  /** 렌더 테스트: recorded 응답을 넣고 네트워크 없이 그린다 */
  initialState?: Partial<ClosureState>;
  fetchEnabled?: boolean;
  debounceMs?: number;
  /** 사건 다시 받기 간격 (ADR-014 A — 60초, ETag 가 같으면 304) */
  pollMs?: number;
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

  // 지금 지도 사건 (T7.4) — t 가 바뀌면 바로, 그 뒤 pollMs 마다 If-None-Match. 304 면 dispatch 하지
  // 않는다(다시 그리지 않음). 숨은 탭은 건너뛰고 다시 보이면 바로 한 번
  const etag = useRef(state.eventsEtag);
  useEffect(() => {
    etag.current = state.eventsEtag;
  }, [state.eventsEtag]);
  useEffect(() => {
    if (!fetchEnabled || !ready) return;
    let controller: AbortController | null = null;
    const load = () => {
      controller?.abort();
      const c = new AbortController();
      controller = c;
      api
        .events({ at: t }, c.signal, etag.current)
        .then((r) => {
          if (!r.changed) return;
          dispatch({
            type: "receiveEvents",
            events: r.body.events,
            at: r.body.at,
            etag: r.etag,
            truncated: r.body.truncated ?? false,
            coverage: asBbox4(r.body.coverage),
            dataAsOf: r.body.data_as_of,
          });
        })
        .catch((e: unknown) => {
          if (c.signal.aborted) return;
          const msg = e instanceof NaruApiError ? e.message : "통제 목록을 받지 못했다";
          dispatch({ type: "failEvents", error: msg });
        });
    };
    load();
    const timer = setInterval(() => {
      if (document.visibilityState !== "hidden") load();
    }, pollMs);
    const onVisible = () => {
      if (document.visibilityState === "visible") load();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      controller?.abort();
    };
  }, [api, t, ready, fetchEnabled, pollMs]);

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
