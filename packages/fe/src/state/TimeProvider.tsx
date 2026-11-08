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
}

export type TimeAction =
  | { type: "set"; t: string }
  | { type: "setMinutes"; minutesFromDayStart: number }
  | { type: "step"; deltaMin: number };

const KST = "+09:00";
const MS_MIN = 60_000;
const KST_MS = 9 * 60 * MS_MIN;

/** ms(UTC) → "YYYY-MM-DDTHH:MM:00+09:00" */
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

export function initialTimeState(t: string, stepMin = 10): TimeState {
  const iso = kstIso(new Date(t).getTime());
  return { t: iso, ...dayBoundsKst(iso), stepMin, ready: true };
}

/** 하이드레이션까지의 자리값 — 서버와 클라이언트가 같은 값. 화면엔 "—" 로만 보인다 */
const PLACEHOLDER_T = "2026-01-01T00:00:00+09:00";

export function pendingTimeState(stepMin = 10): TimeState {
  return { ...initialTimeState(PLACEHOLDER_T, stepMin), ready: false };
}

export function timeReducer(state: TimeState, action: TimeAction): TimeState {
  switch (action.type) {
    case "set":
      return initialTimeState(action.t, state.stepMin);
    case "setMinutes": {
      if (!state.ready) return state; // 시각이 정해지기 전엔 움직이지 않는다
      const clamped = Math.min(Math.max(action.minutesFromDayStart, 0), 24 * 60);
      return { ...state, t: kstIso(new Date(state.dayStart).getTime() + clamped * MS_MIN) };
    }
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

const TimeStateCtx = createContext<TimeState | null>(null);
const TimeDispatchCtx = createContext<Dispatch<TimeAction> | null>(null);

export function TimeProvider({ children, initialT }: { children: ReactNode; initialT?: string }) {
  const [state, dispatch] = useReducer(timeReducer, initialT, (t) =>
    t === undefined ? pendingTimeState() : initialTimeState(t),
  );
  useEffect(() => {
    // 마운트 뒤에야 실제 시각을 넣는다 — URL 의 ?t=, 없으면 지금
    if (initialT !== undefined) return;
    dispatch({ type: "set", t: tFromLocation(window.location.search) });
  }, [initialT]);
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
