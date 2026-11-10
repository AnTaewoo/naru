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
import { NaruApiError, placeLngLat } from "../api/naruApiClient";
import type { LngLat } from "../map/layers/routeLayer";
import type { Place, RouteResponse } from "../types/contracts";
import { useNaruApi } from "./ApiProvider";
import { inBbox, useClosures, type Bbox4 } from "./ClosureProvider";
import { useTime } from "./TimeProvider";

// Provider 4/4 — 길찾기: 출발·도착과 /api/route 결과. t·출발·도착이 바뀌면 다시 받는다 (이전 요청은 Abort)
export type RouteStatus = "idle" | "loading" | "ready" | "error";
export type OdField = "from" | "to";
/** 지도·카드에서 고른 길 (T5.11) — 원래 길은 피한 통제가 있을 때만 */
export type RouteView = "fastest" | "original";

/** 내 위치 찾기 (T5.7) — 어느 칸을 채우려는지와 진행. 거부·실패·범위 밖이면 칸은 비우고 안내 */
export type LocateStatus = "locating" | "denied" | "unavailable" | "outside";
export interface LocateState {
  which: OdField;
  status: LocateStatus;
}

/** 칸에 보일 이름 (T5.8) — 그 점을 검색으로 골랐으면 장소 이름, 지도로 골랐으면 주소(label).
 * text null = 주소 없음·실패 → "선택한 위치". point 가 칸의 점과 다르면 지난 이름이다 */
export interface PlaceName {
  point: LngLat;
  text: string | null;
}

/** 검색한 장소 (T7.14) — 홈 검색 결과를 누르면 핀·장소 카드. 출발·도착으로 고르면 사라진다 */
export interface PlacePick {
  id: string;
  name: string;
  /** 도로명 주소, 없으면 지번 (INTERFACE §7.1) */
  address: string;
  point: LngLat;
}

export function placePick(p: Place): PlacePick | null {
  const point = placeLngLat(p);
  return point ? { id: p.id, name: p.name, address: p.address, point } : null;
}

/** 지도를 옮길 점 (T7.14) — 검색으로 고른 장소·칸. seq 가 바뀌면 MapView 가 flyTo */
export interface MapFocus {
  point: LngLat;
  seq: number;
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
  /** 칸 이름 (T5.8) — 좌표는 화면에 안 쓴다 */
  names: { from: PlaceName | null; to: PlaceName | null };
  /** 입력 중인 칸 (T5.8) — 그동안 지도를 누르면 이 칸에 넣는다 */
  editing: OdField | null;
  /** 고른 길 (T5.11) — 원래 길 카드를 누르면 original */
  view: RouteView;
  /** 피할 사건 id (T7.6) — 사건 카드 "이 구역 피해서 길찾기"·?avoid=. 시각·확신도와 상관없이 막는다 */
  avoid: string | null;
  /** 검색한 장소 (T7.14) — 핀·장소 카드, 길찾기를 켜지 않는다 */
  place: PlacePick | null;
  /** 지도를 옮길 점 (T7.14) */
  focus: MapFocus | null;
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
  | { type: "locateFail"; reason: "denied" | "unavailable" }
  | { type: "edit"; which: OdField | null }
  | { type: "choose"; which: OdField; point: LngLat; name: string }
  | { type: "named"; which: OdField; point: LngLat; text: string | null }
  | { type: "view"; view: RouteView }
  | { type: "avoid"; id: string | null }
  | { type: "place"; place: PlacePick | null };

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
    names: { from: null, to: null },
    editing: null,
    view: "fastest",
    avoid: null,
    place: null,
    focus: null,
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
    editing: null,
    view: "fastest",
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
    case "avoid": {
      // 이 구역 피해서 길찾기 (T7.6) — 길찾기를 켜고(출발이 없으면 내 위치부터), 받은 경로는 버리고 다시 받는다
      const opened = state.active
        ? state
        : { ...state, active: true, locate: state.from ? null : FROM_MINE };
      return {
        ...opened,
        avoid: action.id,
        status: "idle",
        route: null,
        at: null,
        error: null,
        errorCode: null,
        view: "fastest",
      };
    }
    case "pick": {
      if (!state.active) return state;
      // 입력 중인 칸이 있으면 그 칸(T5.8), 아니면 빈 칸 차례로
      const which: OdField | null =
        state.editing ?? (!state.from ? "from" : !state.to ? "to" : null);
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
      return {
        ...withOd(state, state.to, state.from),
        names: { from: state.names.to, to: state.names.from },
      };
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
        // 피한 통제가 없으면 원래 길 카드도 없다 (T5.11)
        view: action.route.avoided.length > 0 ? state.view : "fastest",
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
      // 입력 중이었으면 입력은 끝난다 (T5.8)
      return state.active
        ? { ...state, locate: { which: action.which, status: "locating" }, editing: null }
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
    case "edit":
      return state.active ? { ...state, editing: action.which } : state;
    case "place":
      // 검색한 장소 (T7.14) — 핀·카드, 지도는 그리로. 다른 검색·지도 누르기·카드 닫기는 null
      return action.place
        ? {
            ...state,
            place: action.place,
            focus: { point: action.place.point, seq: (state.focus?.seq ?? 0) + 1 },
          }
        : state.place === null
          ? state
          : { ...state, place: null };
    case "choose": {
      // 검색으로 고른 장소 (T5.8) — 칸 이름은 장소 이름. 홈에서 고르면 길찾기가 켜진다.
      // 지도도 그 점으로(T7.14), 장소 카드는 닫는다
      const name: PlaceName = { point: action.point, text: action.name };
      const next = {
        ...withField(state, action.which, action.point),
        names: { ...state.names, [action.which]: name },
        place: null,
        focus: { point: action.point, seq: (state.focus?.seq ?? 0) + 1 },
      };
      // 홈에서 도착을 고르면 출발은 내 위치부터(T5.7 기본값). 다른 칸을 찾던 중이면 계속
      if (!state.active && action.which === "to" && !state.from)
        return { ...next, locate: FROM_MINE };
      return state.locate && state.locate.which !== action.which
        ? { ...next, locate: state.locate }
        : next;
    }
    case "view":
      return state.view === action.view ? state : { ...state, view: action.view };
    case "named":
      // 주소는 그 점일 때만 — 그새 칸이 바뀌었으면 버린다
      if (!same(state[action.which], action.point)) return state;
      return {
        ...state,
        names: { ...state.names, [action.which]: { point: action.point, text: action.text } },
      };
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

/** URL `?avoid=<사건 id>` (T7.6) — 계약의 사건 id(소문자 16진수 12자리)만, 아니면 null */
export function avoidFromLocation(search: string): string | null {
  const id = new URLSearchParams(search).get("avoid");
  return id && /^[0-9a-f]{12}$/.test(id) ? id : null;
}

/** URL `?from=lat,lng&to=lat,lng` — 시연은 README 의 주소 (t 와 함께) */
export function odFromLocation(search: string): { from: LngLat | null; to: LngLat | null } {
  const q = new URLSearchParams(search);
  return { from: parseLatLng(q.get("from")), to: parseLatLng(q.get("to")) };
}

/** 지도·주소창으로 정한 칸의 주소 (T5.8) — 그 점의 이름이 없을 때만 /geocode/reverse.
 * 실패·주소 없음은 text null("선택한 위치"). 내 위치인 칸은 묻지 않는다 */
function useReverseName(
  which: OdField,
  p: LngLat | null,
  name: PlaceName | null,
  mine: LngLat | null,
  enabled: boolean,
  dispatch: Dispatch<RouteAction>,
) {
  const api = useNaruApi();
  useEffect(() => {
    if (!enabled || !p || same(p, mine) || (name && same(name.point, p))) return;
    const controller = new AbortController();
    api
      .geocodeReverse({ lat: p[1], lng: p[0] }, controller.signal)
      .then((r) => dispatch({ type: "named", which, point: p, text: r.label }))
      .catch(() => {
        if (!controller.signal.aborted) dispatch({ type: "named", which, point: p, text: null });
      });
    return () => controller.abort();
  }, [api, which, p, name, mine, enabled, dispatch]);
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
  const { active, from, to, avoid } = state;
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
    const id = avoidFromLocation(window.location.search);
    if (id) dispatch({ type: "avoid", id });
  }, [hasInitial]);

  useEffect(() => {
    if (!fetchEnabled || !ready || !active || !from || !to) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      dispatch({ type: "request", at: t });
      api
        .route(
          {
            from: latLngParam(from),
            to: latLngParam(to),
            departAt: t,
            avoid: avoid ? [avoid] : [],
          },
          controller.signal,
        )
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
  }, [api, t, ready, active, from, to, avoid, fetchEnabled, debounceMs]);

  useEffect(() => {
    coverageRef.current = coverage;
  }, [coverage]);

  useReverseName("from", from, state.names.from, state.mine, fetchEnabled, dispatch);
  useReverseName("to", to, state.names.to, state.mine, fetchEnabled, dispatch);

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
