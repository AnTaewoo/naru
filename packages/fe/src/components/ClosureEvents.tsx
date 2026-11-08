"use client";

import { dayKo, eventDetailKo, eventTitleKo, windowKo } from "../i18n/ko";
import { eventBbox, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { useTimeDispatch } from "../state/TimeProvider";
import type { ClosureEvent } from "../types/contracts";
import styles from "./ClosureEvents.module.css";

// 통제 불러오기 (T5.4, ADR-010) — DB 에 있는 통제를 날짜별로. 누르면 그 시작 시각으로 가고,
// 홈에선 지도를 그 범위로 맞춘다(길찾기에선 경로를 보고 있으니 지도는 그대로).
// T5.9: 다가오는(진행 중 포함) 것 먼저 시작 순, 끝난 건 "지난 통제" 묶음 — 기준은 실제 지금.
// 제목·둘째 줄은 파서 요약으로(ko.ts 템플릿)
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

/** 끝 시각 — 없으면 시작 + 6시간 (BE 임시 end 와 같은 규칙, INTERFACE §1) */
function endMs(e: ClosureEvent): number {
  if (e.window.end) return Date.parse(e.window.end);
  return e.window.start ? Date.parse(e.window.start) + 6 * 3_600_000 : Number.NEGATIVE_INFINITY;
}

/** 다가오는(진행 중 포함) 사건은 시작 이른 순, 끝난 사건은 최근 날짜 먼저 — 실제 지금 기준 */
export function eventGroups(
  events: readonly ClosureEvent[],
  nowMs: number,
): { upcoming: EventDay[]; past: EventDay[] } {
  const upcoming = events.filter((e) => endMs(e) >= nowMs);
  const past = events.filter((e) => endMs(e) < nowMs); // API 순서(시작 늦은 순) 그대로
  const startMs = (e: ClosureEvent) => (e.window.start ? Date.parse(e.window.start) : Infinity);
  return {
    upcoming: eventDays([...upcoming].sort((a, b) => startMs(a) - startMs(b))),
    past: eventDays(past),
  };
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
  const { upcoming, past } = eventGroups(events ?? [], Date.now());
  const day = (d: EventDay) => (
    <div key={d.key} role="group" aria-label={d.label}>
      <div className={styles.day}>{d.label}</div>
      <ul className={styles.list}>
        {d.events.map((e) => {
          const detail = eventDetailKo(e);
          return (
            <li key={`${e.reason}|${e.window.start ?? ""}|${e.window.end ?? ""}`}>
              <button
                type="button"
                className={styles.row}
                disabled={!e.window.start}
                onClick={() => pick(e)}
              >
                <b className={styles.title}>{eventTitleKo(e)}</b>
                {detail && <span className={styles.detail}>{detail}</span>}
                <span className={styles.sub}>
                  {e.approx ? "약 " : ""}
                  {windowKo(e.window.start, e.window.end)} · 횡단보도 {e.crosswalks}곳
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
  return (
    <section className={styles.events} aria-label="통제 불러오기">
      {events === null && <p className={styles.msg}>{eventsError ?? "불러오는 중…"}</p>}
      {events?.length === 0 && <p className={styles.msg}>기록된 통제가 없어요.</p>}
      {upcoming.map(day)}
      {past.length > 0 && (
        <div role="group" aria-label="지난 통제" className={styles.past}>
          <div className={styles.pastHead}>지난 통제</div>
          {past.map(day)}
        </div>
      )}
    </section>
  );
}
