"use client";

import { useState } from "react";
import { dayKo, eventDetailKo, eventTitleKo, windowKo } from "../i18n/ko";
import {
  asBbox4,
  eventBbox,
  useClosureDispatch,
  useClosures,
  type Bbox4,
} from "../state/ClosureProvider";
import { kstIso, useTimeDispatch } from "../state/TimeProvider";
import type { ClosureEvent } from "../types/contracts";
import styles from "./ClosureEvents.module.css";

// 통제 불러오기 (T5.4, ADR-010) — DB 에 있는 통제를 날짜별로. 누르면 그 시작 시각으로 가고,
// 홈에선 지도를 그 범위로 맞춘다(길찾기에선 경로를 보고 있으니 지도는 그대로).
// T5.9: 다가오는(진행 중 포함) 것 먼저 시작 순 — 기준은 실제 지금. 제목·둘째 줄은 파서 요약으로(ko.ts 템플릿)
// T6.9 서울 전체: 오늘·다가오는 것만 펼치고 어제까지 끝난 건 "지난 통제 N건"으로 접는다.
// 위에 구 칩 — 지도 화면과 겹치는 사건의 구 먼저
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

/**
 * 오늘·다가오는(진행 중 포함) 사건은 시작 이른 순, 어제까지 끝난 사건은 최근 날짜 먼저 — 실제 지금 기준.
 * 오늘 시작한 통제는 끝났어도 오늘 묶음에 남는다 (T6.9)
 */
export function eventGroups(
  events: readonly ClosureEvent[],
  nowMs: number,
): { upcoming: EventDay[]; past: EventDay[] } {
  const today = kstIso(nowMs).slice(0, 10);
  const current = (e: ClosureEvent) =>
    endMs(e) >= nowMs ||
    (!!e.window.start && kstIso(Date.parse(e.window.start)).slice(0, 10) >= today);
  const upcoming = events.filter(current);
  const past = events.filter((e) => !current(e)); // API 순서(시작 늦은 순) 그대로
  const startMs = (e: ClosureEvent) => (e.window.start ? Date.parse(e.window.start) : Infinity);
  return {
    upcoming: eventDays([...upcoming].sort((a, b) => startMs(a) - startMs(b))),
    past: eventDays(past),
  };
}

/** 두 bbox 가 겹치나 (경계 포함) */
function overlaps(a: Bbox4, b: Bbox4): boolean {
  return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
}

/**
 * 구 칩 순서 — 지도 화면(view)과 bbox 가 겹치는 사건의 구 먼저(그런 사건이 많은 순), 나머지는 가나다.
 * 구 경계는 FE 에 없어서 사건 bbox 로 본다 — 긴 구간이 화면에 걸치면 그 구간의 다른 구도 앞에 온다
 */
export function districtChips(events: readonly ClosureEvent[], view: Bbox4 | null): string[] {
  const inView = new Map<string, number>();
  const all = new Set<string>();
  for (const e of events) {
    const b = eventBbox(e);
    const seen = view !== null && b !== null && overlaps(b, view);
    for (const d of e.districts ?? []) {
      all.add(d);
      if (seen) inView.set(d, (inView.get(d) ?? 0) + 1);
    }
  }
  const ko = (a: string, b: string) => a.localeCompare(b, "ko");
  const count = (d: string) => inView.get(d) ?? 0;
  const first = [...inView.keys()].sort((a, b) => count(b) - count(a) || ko(a, b));
  return [...first, ...[...all].filter((d) => !inView.has(d)).sort(ko)];
}

/** 고른 구를 지나는 사건만 (null = 전체) */
export function byDistrict(
  events: readonly ClosureEvent[],
  district: string | null,
): ClosureEvent[] {
  if (district === null) return [...events];
  return events.filter((e) => (e.districts ?? []).includes(district));
}

export function ClosureEvents({ focusMap, onDone }: { focusMap: boolean; onDone: () => void }) {
  const { events, eventsError, bbox } = useClosures();
  const timeDispatch = useTimeDispatch();
  const closureDispatch = useClosureDispatch();
  const [district, setDistrict] = useState<string | null>(null);
  const [pastOpen, setPastOpen] = useState(false);
  const pick = (e: ClosureEvent) => {
    if (!e.window.start) return;
    timeDispatch({ type: "set", t: e.window.start });
    const box = eventBbox(e);
    if (focusMap && box) closureDispatch({ type: "focus", bbox: box });
    onDone();
  };
  const chips = districtChips(events ?? [], asBbox4(bbox.split(",").map(Number)));
  const { upcoming, past } = eventGroups(byDistrict(events ?? [], district), Date.now());
  const pastCount = past.reduce((n, d) => n + d.events.length, 0);
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
      {chips.length > 0 && (
        <div role="group" aria-label="구 필터" className={styles.chips}>
          {[null, ...chips].map((d) => (
            <button
              key={d ?? "all"}
              type="button"
              className={styles.chip}
              aria-pressed={district === d}
              onClick={() => setDistrict(d)}
            >
              {d ?? "전체"}
            </button>
          ))}
        </div>
      )}
      {!!events?.length && upcoming.length === 0 && (
        <p className={styles.msg}>오늘·다가오는 통제가 없어요.</p>
      )}
      {upcoming.map(day)}
      {past.length > 0 && (
        <div role="group" aria-label="지난 통제" className={styles.past}>
          <button
            type="button"
            className={styles.pastHead}
            aria-expanded={pastOpen}
            onClick={() => setPastOpen(!pastOpen)}
          >
            지난 통제 {pastCount}건
          </button>
          {pastOpen && past.map(day)}
        </div>
      )}
    </section>
  );
}
