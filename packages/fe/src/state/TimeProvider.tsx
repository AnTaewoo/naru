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

// Provider 2/4 — 기준 시각 t (ISO 8601 +09:00). state·dispatch Context 를 따로 둔다 (CONVENTIONS §5.5)
export interface TimeState {
  /** ISO 8601 +09:00 */
  t: string;
  /** 슬라이더 범위 — t 가 속한 날 00:00 ~ 24:00 (KST) */
  dayStart: string;
  dayEnd: string;
  /** 슬라이더 한 칸 (분) */
  stepMin: number;
  /**
   * false = 서버 렌더·하이드레이션 중이라 시각이 아직 없다(자리값). 페이지가 정적 프리렌더라 Date.now() 를
   * 초기값으로 쓰면 서버 HTML(빌드 시각)과 첫 클라이언트 렌더가 달라 하이드레이션이 깨진다(React #418)
   */
  ready: boolean;
  /**
   * 지금 모드 (T7.4) — ?t= 없이 열었거나 '지금으로'를 눌렀다. 5분마다 t 가 실제 지금으로 간다. 그 사이엔 t 가
   * 그대로라 60초 사건 요청이 같은 at 이고 ETag 가 맞으면 304. 슬라이더를 만지거나 시각을 정해 옮기면 꺼진다
   */
  live: boolean;
}

export type TimeAction =
  | { type: "set"; t: string; live?: boolean }
  | { type: "setMinutes"; minutesFromDayStart: number }
  | { type: "step"; deltaMin: number }
  | { type: "tick"; nowMs: number };

/** 지금 모드에서 t 를 지금으로 옮기는 간격 — TOPIS 돌발 수신(5분)·'지금' 배지(±5분)와 같다 */
export const LIVE_STEP_MS = 5 * 60_000;

const KST = "+09:00";
const MS_MIN = 60_000;
const KST_MS = 9 * 60 * MS_MIN;

/** ms(UTC) → "YYYY-MM-DDTHH:MM:00+09:00" */
/** 기준 시각이 실제 지금인가 — ±5분(슬라이더 한 칸의 절반) 안. '지금' 배지는 이때만 (T5.9) */
export function isNowAt(t: string, nowMs: number): boolean {
  return Math.abs(Date.parse(t) - nowMs) <= 5 * 60_000;
}

export function kstIso(ms: number): string {
  const d = new Date(ms + KST_MS);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, "0");
  const da = String(d.getUTCDate()).padStart(2, "0");
  const h = String(d.getUTCHours()).padStart(2, "0");
  const mi = String(d.getUTCMinutes()).padStart(2, "0");
  return `${y}-${mo}-${da}T${h}:${mi}:00${KST}`;
}

export function dayBoundsKst(t: string): { dayStart: string; dayEnd: string } {
  const kst = new Date(new Date(t).getTime() + KST_MS);
  const startUtcMs = Date.UTC(kst.getUTCFullYear(), kst.getUTCMonth(), kst.getUTCDate()) - KST_MS;
  return { dayStart: kstIso(startUtcMs), dayEnd: kstIso(startUtcMs + 24 * 60 * MS_MIN) };
}

export function minutesFromDayStart(state: TimeState): number {
  return Math.round((new Date(state.t).getTime() - new Date(state.dayStart).getTime()) / MS_MIN);
}

export function initialTimeState(t: string, stepMin = 10, live = false): TimeState {
  const iso = kstIso(new Date(t).getTime());
  return { t: iso, ...dayBoundsKst(iso), stepMin, ready: true, live };
}

/** 하이드레이션까지의 자리값 — 서버와 클라이언트가 같은 값. 화면엔 "—" 로만 보인다 */
const PLACEHOLDER_T = "2026-01-01T00:00:00+09:00";

export function pendingTimeState(stepMin = 10): TimeState {
  return { ...initialTimeState(PLACEHOLDER_T, stepMin), ready: false };
}

export function timeReducer(state: TimeState, action: TimeAction): TimeState {
  switch (action.type) {
    case "set":
      return initialTimeState(action.t, state.stepMin, action.live ?? false);
    case "setMinutes": {
      if (!state.ready) return state; // 시각이 정해지기 전엔 움직이지 않는다
      const clamped = Math.min(Math.max(action.minutesFromDayStart, 0), 24 * 60);
      const t = kstIso(new Date(state.dayStart).getTime() + clamped * MS_MIN);
      return { ...state, t, live: false };
    }
    case "tick":
      if (!state.live || action.nowMs - Date.parse(state.t) < LIVE_STEP_MS) return state;
      return initialTimeState(kstIso(action.nowMs), state.stepMin, true);
    case "step":
      return timeReducer(state, {
        type: "setMinutes",
        minutesFromDayStart: minutesFromDayStart(state) + action.deltaMin,
      });
  }
}

/**
 * URL `?t=` 가 있으면 그 시각, 없으면 지금 (시연은 ?t=2026-03-15T07:45:00+09:00).
 * 주소창에 `+09:00` 을 그대로 치면 쿼리 해석에서 `+` 가 공백이 된다 — ISO 시각엔 공백이 없으니 되돌린다
 */
export function tFromLocation(search: string, now: () => number = Date.now): string {
  const q = new URLSearchParams(search).get("t")?.replace(/ /g, "+");
  if (q && !Number.isNaN(new Date(q).getTime())) return kstIso(new Date(q).getTime());
  return kstIso(now());
}

/** ?t= 가 없거나 읽을 수 없으면 지금 모드 (T7.4) — tFromLocation 이 지금으로 가는 경우와 같다 */
export function liveFromLocation(search: string): boolean {
  const q = new URLSearchParams(search).get("t")?.replace(/ /g, "+");
  return !q || Number.isNaN(new Date(q).getTime());
}

const TimeStateCtx = createContext<TimeState | null>(null);
const TimeDispatchCtx = createContext<Dispatch<TimeAction> | null>(null);

export function TimeProvider({ children, initialT }: { children: ReactNode; initialT?: string }) {
  const [state, dispatch] = useReducer(timeReducer, initialT, (t) =>
    t === undefined ? pendingTimeState() : initialTimeState(t),
  );
  useEffect(() => {
    // 마운트 뒤에야 실제 시각을 넣는다 — URL 의 ?t=, 없으면 지금
    if (initialT !== undefined) return;
    const search = window.location.search;
    dispatch({ type: "set", t: tFromLocation(search), live: liveFromLocation(search) });
  }, [initialT]);
  // 지금 모드면 1분마다 확인 — 5분이 지났으면 t 를 지금으로 (사건·통제·경로가 다시 받는다)
  useEffect(() => {
    if (!state.live) return;
    const timer = setInterval(() => dispatch({ type: "tick", nowMs: Date.now() }), 60_000);
    return () => clearInterval(timer);
  }, [state.live]);
  const value = useMemo(() => state, [state]);
  return (
    <TimeStateCtx.Provider value={value}>
      <TimeDispatchCtx.Provider value={dispatch}>{children}</TimeDispatchCtx.Provider>
    </TimeStateCtx.Provider>
  );
}

export function useTime(): TimeState {
  const v = useContext(TimeStateCtx);
  if (!v) throw new Error("TimeProvider 밖에서 useTime 호출");
  return v;
}

export function useTimeDispatch(): Dispatch<TimeAction> {
  const v = useContext(TimeDispatchCtx);
  if (!v) throw new Error("TimeProvider 밖에서 useTimeDispatch 호출");
  return v;
}
