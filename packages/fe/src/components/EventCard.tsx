"use client";

import { useState } from "react";
import {
  AVOID_KO,
  GRACE_NOTE_KO,
  TYPE_KO,
  confidenceKo,
  dayKo,
  eventDetailKo,
  eventTitleKo,
  inGrace,
  kindBadgeKo,
  longRouteKo,
  remainKo,
  sourceKo,
  windowKo,
} from "../i18n/ko";
import { KIND_BG, KIND_COLOR, eventKind } from "../map/eventKinds";
import type { ClosureEvent } from "../types/contracts";
import styles from "./EventCard.module.css";

// 사건 카드 (T7.5, 목업 03_closure) — 배지(상태·원인) → 제목 → 둘째 줄·지나는 곳 → 날짜·창 → 남은 시간(가장 큰 글자)
// → 출처·확신도·막히는 횡단보도 → 이 구역 피해서 길찾기(T7.6) · 통제 근거 보기(공지 원문). ☆ 알림은 T7.10
export function EventCard({
  event,
  atMs,
  onClose,
  onAvoid,
}: {
  event: ClosureEvent;
  atMs: number;
  onClose: () => void;
  /** 이 사건을 피해서 길찾기 (T7.6) — 없으면 버튼을 안 그린다 */
  onAvoid?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const kind = eventKind(event, atMs);
  const title = eventTitleKo(event);
  const detail = eventDetailKo(event);
  const route = longRouteKo(event);
  return (
    <article className={styles.card} aria-label={title}>
      <div className={styles.top}>
        <div className={styles.badges}>
          <span
            className={styles.badge}
            style={{ background: KIND_BG[kind], color: KIND_COLOR[kind] }}
          >
            {kindBadgeKo(event, atMs)}
          </span>
          {event.type && (
            <span className={`${styles.badge} ${styles.gray}`}>{TYPE_KO[event.type]}</span>
          )}
        </div>
        <button type="button" className={styles.close} aria-label="카드 닫기" onClick={onClose}>
          ×
        </button>
      </div>
      <h2 className={styles.title}>{title}</h2>
      {detail && <p className={styles.detail}>{detail}</p>}
      {route && <p className={styles.route}>{route}</p>}
      <div className={styles.when}>
        <span>{dayKo(event.window.start)}</span>
        <span>{windowKo(event.window.start, event.window.end)}</span>
      </div>
      <p className={styles.remain} style={{ color: KIND_COLOR[kind] }}>
        {remainKo(event, atMs)}
      </p>
      {/* 해제 예정이 지났는데 아직 통제 중 — 정리 시간 까닭 (태우 11/10) */}
      {event.status === "confirmed" && inGrace(event.window.end, atMs) && (
        <p className={styles.grace}>{GRACE_NOTE_KO}</p>
      )}
      <dl className={styles.facts}>
        <div>
          <dt>출처</dt>
          <dd>{sourceKo(event)}</dd>
        </div>
        <div>
          <dt>확신도</dt>
          <dd>{confidenceKo(event.confidence)}</dd>
        </div>
        <div>
          <dt>막히는 횡단보도</dt>
          <dd>{event.crosswalks}곳</dd>
        </div>
      </dl>
      {onAvoid && (
        <button type="button" className={`${styles.cta} ${styles.primary}`} onClick={onAvoid}>
          {AVOID_KO.button}
        </button>
      )}
      {event.notice && (
        <>
          <button
            type="button"
            className={styles.cta}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            통제 근거 보기
          </button>
          {open && <p className={styles.excerpt}>{event.notice.excerpt}</p>}
        </>
      )}
    </article>
  );
}
