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
import type { ClosureEvent, DataAsOf, FeatureCollection, MarchResponse } from "../types/contracts";
import { useNaruApi } from "./ApiProvider";
import { kstIso, useTime } from "./TimeProvider";

// Provider 3/4 — 지금 지도 사건(/api/closures/events?at=t, 60초 ETag)과 화면의 횡단보도(/api/closures,
// 줌 14 이상·길찾기 때만). t·화면이 바뀌면 다시 받는다 (이전 요청은 Abort). CONVENTIONS §5.5, T7.4
export type ClosureStatus = "idle" | "loading" | "ready" | "error";

export interface ClosureState {
  status: ClosureStatus;
  /** 마지막으로 받은 결과 (loading 중에도 유지해 깜빡임 없음) */
  closures: FeatureCollection;
  /** 결과가 기준한 시각·bbox */
  at: string | null;
  bbox: string;
  /** 횡단보도 점이 필요한가 — 줌 14 이상이거나 길찾기 (T7.4). 아니면 /closures 를 받지 않는다 */
  points: boolean;
  error: string | null;
  /** 지금 지도 사건 (GET /closures/events?at=t, ADR-014 A). null = 아직 못 받음 */
  events: ClosureEvent[] | null;
  /** 사건 status 의 기준 시각 (응답 at) */
  eventsAt: string | null;
  /** 마지막 사건 응답의 ETag — 60초 요청의 If-None-Match */
  eventsEtag: string | null;
  /** 300건 상한에 잘렸나 */
  truncated: boolean;
  /** 시트 목록 (T7.12) — t 앞뒤 365일 넓은 창 사건(상태는 t 기준). null = 아직 못 받음 */
  catalog: ClosureEvent[] | null;
  catalogAt: string | null;
  catalogEtag: string | null;
  eventsError: string | null;
  /** 보행망 범위 (같은 응답의 coverage, INTERFACE v0.10) — 내 위치가 밖이면 안내 (T5.7). null = 모름 */
  coverage: Bbox4 | null;
  /** 출처별 기준 시각 (같은 응답의 data_as_of, v0.12) — 목록 위에 쓴다 (T5.9). null = 모름 */
  dataAsOf: DataAsOf | null;
  /** 연 사건 카드 (T7.5) — 행·구역·점·?event= 로 연다. id 만 두고 사건은 events 에서 찾는다 */
  selected: string | null;
  /** 클러스터·겹친 구역을 누르면 그 사건들만 목록으로 (T7.5). null = 지금 서울 통제 전체 */
  picked: string[] | null;
  /** 지도 맞춤 요청 (T7.11 예시로 보기) — 같은 범위를 다시 눌러도 맞추도록 순번을 올린다 */
  frame: { bbox: Bbox4; seq: number } | null;
  /** 고른 행진 사건의 예상 위치 키프레임 (T7.16). 받은 사건 id 와 응답(대상 아니면 null) */
  march: { id: string; body: MarchResponse | null } | null;
  /** 예상 위치 재생 중인 시각(ms) — 네트워크 없이 지도·카드만 이 시각으로. null = 재생 아님 */
  playMs: number | null;
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
  | { type: "setView"; bbox: string; points: boolean }
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
  | { type: "receiveCatalog"; events: ClosureEvent[]; at: string; etag: string | null }
  | { type: "select"; id: string | null }
  | { type: "pick"; ids: string[] }
  | { type: "unpick" }
  | { type: "frame"; bbox: Bbox4 }
  | { type: "receiveMarch"; id: string; body: MarchResponse | null }
  | { type: "play"; ms: number | null };

export const EMPTY_CLOSURES: FeatureCollection = { type: "FeatureCollection", features: [] };

/** 시트 목록 질의 (T7.12) — 기준 시각 앞뒤 365일. t 가 그대로면 같은 질의라 ETag 가 맞으면 304 */
export function catalogParams(t: string): { at: string; from: string; to: string } {
  const at = Date.parse(t);
  const year = 365 * 24 * 60 * 60_000;
  return { at: kstIso(at), from: kstIso(at - year), to: kstIso(at + year) };
}

/**
 * 받기를 되풀이한다 — 바로 한 번, 그 뒤 pollMs 마다(숨은 탭은 건너뛰고 다시 보이면 바로). 이전 요청은 Abort.
 * 정리 함수를 돌려준다 (useEffect)
 */
function poll(load: (signal: AbortSignal) => void, pollMs: number): () => void {
  let controller: AbortController | null = null;
  const run = () => {
    controller?.abort();
    controller = new AbortController();
    load(controller.signal);
  };
  run();
  const timer = setInterval(() => {
    if (document.visibilityState !== "hidden") run();
  }, pollMs);
  const onVisible = () => {
    if (document.visibilityState === "visible") run();
  };
  document.addEventListener("visibilitychange", onVisible);
  return () => {
    clearInterval(timer);
    document.removeEventListener("visibilitychange", onVisible);
    controller?.abort();
  };
}

/** ?event=<사건 id> (T7.5, 알림 클릭은 T7.10) — 12자 소문자 16진만 (INTERFACE §3.1 v0.14 id) */
export function eventFromLocation(search: string): string | null {
  const id = new URLSearchParams(search).get("event");
  return id && /^[0-9a-f]{12}$/.test(id) ? id : null;
}
/** 화면 bbox 자리값(광화문 일대, 장소 검색의 near) — 지도가 뜨면 setView 로 실제 화면 */
export const DEFAULT_BBOX = "126.965,37.555,126.990,37.580";

export function initialClosureState(partial: Partial<ClosureState> = {}): ClosureState {
  return {
    status: "idle",
    closures: EMPTY_CLOSURES,
    at: null,
    bbox: DEFAULT_BBOX,
    points: false,
    error: null,
    events: null,
    eventsAt: null,
    eventsEtag: null,
    truncated: false,
    catalog: null,
    catalogAt: null,
    catalogEtag: null,
    eventsError: null,
    coverage: null,
    dataAsOf: null,
    selected: null,
    picked: null,
    frame: null,
    march: null,
    playMs: null,
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
    case "setView":
      return state.bbox === action.bbox && state.points === action.points
        ? state
        : { ...state, bbox: action.bbox, points: action.points };
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
    case "receiveCatalog":
      return { ...state, catalog: action.events, catalogAt: action.at, catalogEtag: action.etag };
    case "failEvents":
      return { ...state, eventsError: action.error };
    case "select":
      if (state.selected === action.id) return state;
      // 다른 사건을 열면 예상 위치·재생은 그 사건 것이 아니다
      return { ...state, selected: action.id, playMs: null, march: action.id ? state.march : null };
    case "receiveMarch":
      return action.id === state.selected ? { ...state, march: action } : state;
    case "play":
      return state.playMs === action.ms ? state : { ...state, playMs: action.ms };
    case "pick": {
      const [only, ...more] = action.ids;
      if (only === undefined) return state;
      // 하나면 바로 카드, 여럿이면 그 묶음 목록 — 카드를 닫으면 묶음으로 돌아온다
      return more.length === 0
        ? { ...state, selected: only }
        : { ...state, picked: action.ids, selected: null };
    }
    case "unpick":
      return { ...state, picked: null };
    case "frame":
      // 예시로 보기 — 카드·묶음은 닫고 그 구역으로
      return {
        ...state,
        selected: null,
        picked: null,
        frame: { bbox: action.bbox, seq: (state.frame?.seq ?? 0) + 1 },
      };
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
  const { bbox, points } = state;

  useEffect(() => {
    // 시각이 정해지기 전, 횡단보도 점이 필요 없는 화면(서울 전체·구역 줌)에선 받지 않는다 (T7.4)
    if (!fetchEnabled || !ready || !points) return;
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
  }, [api, t, ready, bbox, points, fetchEnabled, debounceMs]);

  // ?event= 로 열면 그 사건 카드 — 사건이 오면 시트가 찾는다 (T7.5)
  useEffect(() => {
    if (!fetchEnabled) return;
    const id = eventFromLocation(window.location.search);
    if (id) dispatch({ type: "select", id });
  }, [fetchEnabled]);

  // 지금 지도 사건 (T7.4) — t 가 바뀌면 바로, 그 뒤 pollMs 마다 If-None-Match. 304 면 dispatch 하지
  // 않는다(다시 그리지 않음). 숨은 탭은 건너뛰고 다시 보이면 바로 한 번
  const etag = useRef(state.eventsEtag);
  useEffect(() => {
    etag.current = state.eventsEtag;
  }, [state.eventsEtag]);
  useEffect(() => {
    if (!fetchEnabled || !ready) return;
    return poll((signal) => {
      api
        .events({ at: t }, signal, etag.current)
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
          if (signal.aborted) return;
          const msg = e instanceof NaruApiError ? e.message : "통제 목록을 받지 못했다";
          dispatch({ type: "failEvents", error: msg });
        });
    }, pollMs);
  }, [api, t, ready, fetchEnabled, pollMs]);

  // 시트 목록 (T7.12) — t 앞뒤 365일 넓은 창, 지도 사건과 따로 같은 주기·ETag. 실패하면 받아 둔 목록 그대로
  const catalogEtag = useRef(state.catalogEtag);
  useEffect(() => {
    catalogEtag.current = state.catalogEtag;
  }, [state.catalogEtag]);
  useEffect(() => {
    if (!fetchEnabled || !ready) return;
    return poll((signal) => {
      api
        .events(catalogParams(t), signal, catalogEtag.current)
        .then((r) => {
          if (!r.changed) return;
          dispatch({ type: "receiveCatalog", events: r.body.events, at: r.body.at, etag: r.etag });
        })
        .catch(() => undefined); // 목록은 지도 사건 실패 문구(eventsError)로 충분 — 받아 둔 것을 쓴다
    }, pollMs);
  }, [api, t, ready, fetchEnabled, pollMs]);

  // 행진 예상 위치 (T7.16) — 고른 사건이 행진이면 키프레임을 한 번 받는다(404 면 null = 정지 표시)
  const selectedEvent = useMemo(() => {
    const id = state.selected;
    if (!id) return null;
    return (
      state.events?.find((e) => e.id === id) ?? state.catalog?.find((e) => e.id === id) ?? null
    );
  }, [state.selected, state.events, state.catalog]);
  const marchId = selectedEvent?.type === "march" ? selectedEvent.id : null;
  const marchHave = state.march?.id ?? null;
  useEffect(() => {
    if (!fetchEnabled || !marchId || marchHave === marchId) return;
    const controller = new AbortController();
    api
      .march(marchId, {}, controller.signal)
      .then((body) => dispatch({ type: "receiveMarch", id: marchId, body }))
      .catch(() => {
        if (!controller.signal.aborted) dispatch({ type: "receiveMarch", id: marchId, body: null });
      });
    return () => controller.abort();
  }, [api, marchId, marchHave, fetchEnabled]);

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
