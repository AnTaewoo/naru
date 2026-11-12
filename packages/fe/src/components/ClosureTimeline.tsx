"use client";

import { useMemo } from "react";
import { eventTitleKo } from "../i18n/ko";
import { KIND_COLOR, listedEvents } from "../map/eventKinds";
import { useClosures } from "../state/ClosureProvider";
import { useTime } from "../state/TimeProvider";
import type { ClosureEvent } from "../types/contracts";
import styles from "./ClosureTimeline.module.css";

// 목업 01_home 의 미니 타임라인: 통제 창을 하루 축에 막대로, 기준 시각을 선으로.
// T7.4: 막대는 시트 목록과 같은 사건(지금 지도, 해제·확신도 0.7 미만 빼고) — 그 날에 걸치는 것만
export interface TimelineBar {
  key: string;
  color: string;
  /** 툴팁 — 사건 제목 (원문은 "공지 원문 보기"에서만, T5.9) */
  title: string;
  leftPct: number;
  widthPct: number;
}

const MS_DAY = 24 * 60 * 60_000;

/** 사건 하나 = 막대 하나, 그 날(dayStart~+24시간)에 걸치는 것만. 끝이 없으면 날 끝까지. 순수 함수 */
export function timelineBars(
  events: readonly ClosureEvent[],
  atMs: number,
  dayStart: string,
): TimelineBar[] {
  const start0 = Date.parse(dayStart);
  const bars: TimelineBar[] = [];
  for (const { event, kind } of listedEvents(events, atMs)) {
    if (!event.window.start) continue;
    const from = (Date.parse(event.window.start) - start0) / MS_DAY;
    const to = event.window.end ? (Date.parse(event.window.end) - start0) / MS_DAY : 1;
    if (from >= 1 || to <= 0) continue; // 다른 날
    const left = Math.max(0, from);
    const right = Math.max(left, Math.min(1, to));
    bars.push({
      key: event.id,
      color: KIND_COLOR[kind],
      title: eventTitleKo(event),
      leftPct: left * 100,
      widthPct: Math.max(0.5, (right - left) * 100),
    });
  }
  return bars.sort((a, b) => a.leftPct - b.leftPct);
}

export function nowPct(t: string, dayStart: string): number {
  const pct = ((new Date(t).getTime() - new Date(dayStart).getTime()) / MS_DAY) * 100;
  return Math.max(0, Math.min(100, pct));
}

export function ClosureTimeline() {
  const { events, eventsAt } = useClosures();
  const { t, dayStart, ready } = useTime();
  const atMs = eventsAt ? Date.parse(eventsAt) : 0;
  const bars = useMemo(() => timelineBars(events ?? [], atMs, dayStart), [events, atMs, dayStart]);
  return (
    <div className={styles.mini} aria-label="오늘 통제 시간표">
      <span className={styles.tr} />
      {bars.map((b, i) => (
        <span
          key={b.key}
          className={styles.bar}
          title={b.title}
          style={{
            left: `${b.leftPct}%`,
            width: `${b.widthPct}%`,
            background: b.color,
            top: `${10 + (i % 3) * 6}px`,
          }}
        />
      ))}
      {ready && <span className={styles.now} style={{ left: `${nowPct(t, dayStart)}%` }} />}
      {[0, 6, 12, 18, 24].map((h) => (
        <span key={h} className={styles.ax} style={{ left: `${(h / 24) * 100}%` }}>
          {String(h).padStart(2, "0")}
        </span>
      ))}
    </div>
  );
}
