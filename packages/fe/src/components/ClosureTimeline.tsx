"use client";

import { useMemo } from "react";
import { eventTitleKo } from "../i18n/ko";
import { STATUS_COLOR } from "../map/colors";
import { useClosures } from "../state/ClosureProvider";
import { useTime } from "../state/TimeProvider";
import type { FeatureCollection, Status } from "../types/contracts";
import styles from "./ClosureTimeline.module.css";

// 목업 01_home 의 미니 타임라인: 통제 창을 하루 축에 막대로, 기준 시각을 선으로
export interface TimelineBar {
  key: string;
  status: Status;
  reason: string;
  leftPct: number;
  widthPct: number;
}

const MS_DAY = 24 * 60 * 60_000;

/** 같은 reason(후보 한 건)끼리 한 막대. 창이 없는 feature 는 뺀다. 순수 함수 */
export function timelineBars(fc: FeatureCollection, dayStart: string): TimelineBar[] {
  const start0 = new Date(dayStart).getTime();
  const seen = new Map<string, TimelineBar>();
  for (const f of fc.features) {
    const p = f.properties;
    const s = p.window["start"];
    const e = p.window["end"];
    if (!s) continue;
    const key = `${p.reason}|${s}|${e ?? ""}`;
    if (seen.has(key)) continue;
    const from = (new Date(s).getTime() - start0) / MS_DAY;
    const to = e ? (new Date(e).getTime() - start0) / MS_DAY : 1;
    const left = Math.max(0, Math.min(1, from));
    const right = Math.max(left, Math.min(1, to));
    seen.set(key, {
      key,
      status: p.status,
      reason: p.reason,
      leftPct: left * 100,
      widthPct: Math.max(0.5, (right - left) * 100),
    });
  }
  return [...seen.values()].sort((a, b) => a.leftPct - b.leftPct);
}

export function nowPct(t: string, dayStart: string): number {
  const pct = ((new Date(t).getTime() - new Date(dayStart).getTime()) / MS_DAY) * 100;
  return Math.max(0, Math.min(100, pct));
}

export function ClosureTimeline() {
  const { closures, events } = useClosures();
  // 막대 툴팁은 사건 제목 — 원문은 "공지 원문 보기"에서만 (T5.9)
  const titleOf = (reason: string) =>
    eventTitleKo(events?.find((e) => e.reason === reason) ?? { reason, summary: null });
  const { t, dayStart, ready } = useTime();
  const bars = useMemo(() => timelineBars(closures, dayStart), [closures, dayStart]);
  return (
    <div className={styles.mini} aria-label="오늘 통제 시간표">
      <span className={styles.tr} />
      {bars.map((b, i) => (
        <span
          key={b.key}
          className={styles.bar}
          title={titleOf(b.reason)}
          style={{
            left: `${b.leftPct}%`,
            width: `${b.widthPct}%`,
            background: STATUS_COLOR[b.status],
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
