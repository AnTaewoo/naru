"use client";

import { dayKo, reasonKo, windowKo } from "../i18n/ko";
import { eventBbox, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { useTimeDispatch } from "../state/TimeProvider";
import type { ClosureEvent } from "../types/contracts";
import styles from "./ClosureEvents.module.css";

// 통제 불러오기 (T5.4, ADR-010) — DB 에 있는 통제를 날짜별로. 누르면 그 시작 시각으로 가고,
// 홈에선 지도를 그 범위로 맞춘다(길찾기에선 경로를 보고 있으니 지도는 그대로)
export interface EventDay {
  key: string;
  label: string;
  events: ClosureEvent[];
}

/** KST 날짜별 묶음. API 가 시작 늦은 순이라 최근 날짜가 먼저, 시작 없는 사건은 끝의 "시간 미정" */
export function eventDays(events: readonly ClosureEvent[]): EventDay[] {
  const days: EventDay[] = [];
  for (const e of events) {
    const label = dayKo(e.window.start);
    const last = days.at(-1);
    if (last && last.label === label) last.events.push(e);
    else days.push({ key: `${days.length}-${label}`, label, events: [e] });
  }
  return days;
}

export function ClosureEvents({ focusMap, onDone }: { focusMap: boolean; onDone: () => void }) {
  const { events, eventsError } = useClosures();
  const timeDispatch = useTimeDispatch();
  const closureDispatch = useClosureDispatch();
  const pick = (e: ClosureEvent) => {
    if (!e.window.start) return;
    timeDispatch({ type: "set", t: e.window.start });
    const bbox = eventBbox(e);
    if (focusMap && bbox) closureDispatch({ type: "focus", bbox });
    onDone();
  };
  return (
    <section className={styles.events} aria-label="통제 불러오기">
      {events === null && <p className={styles.msg}>{eventsError ?? "불러오는 중…"}</p>}
      {events?.length === 0 && <p className={styles.msg}>기록된 통제가 없어요.</p>}
      {eventDays(events ?? []).map((day) => (
        <div key={day.key} role="group" aria-label={day.label}>
          <div className={styles.day}>{day.label}</div>
          <ul className={styles.list}>
            {day.events.map((e) => (
              <li key={`${e.reason}|${e.window.start ?? ""}|${e.window.end ?? ""}`}>
                <button
                  type="button"
                  className={styles.row}
                  disabled={!e.window.start}
                  onClick={() => pick(e)}
                >
                  <b className={styles.title}>{reasonKo(e.reason)}</b>
                  <span className={styles.sub}>
                    {e.approx ? "약 " : ""}
                    {windowKo(e.window.start, e.window.end)} · 횡단보도 {e.crosswalks}곳
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
