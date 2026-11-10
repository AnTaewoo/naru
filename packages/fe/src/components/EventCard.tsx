"use client";

import { useState } from "react";
import {
  AVOID_KO,
  GRACE_NOTE_KO,
  MARCH_KO,
  TYPE_KO,
  confidenceKo,
  dayKo,
  eventDetailKo,
  eventTitleKo,
  inGrace,
  kindBadgeKo,
  longRouteKo,
  marchProbabilityKo,
  remainKo,
  sourceKo,
  windowKo,
} from "../i18n/ko";
import { KIND_BG, KIND_COLOR, eventKind } from "../map/eventKinds";
import { pColor, probabilityAt } from "../map/layers/marchLayer";
import type { ClosureEvent, MarchResponse } from "../types/contracts";
import styles from "./EventCard.module.css";

// 사건 카드 (T7.5, 목업 03_closure) — 배지(상태·원인) → 제목 → 둘째 줄·지나는 곳 → 날짜·창 → 남은 시간(가장 큰 글자)
// → 출처·확신도·막히는 횡단보도 → 이 구역 피해서 길찾기(T7.6) · 통제 근거 보기(공지 원문). ☆ 알림은 T7.10
// 행진 확률 모델 사건(T7.16, ADR-015 G)은 남은 시간 아래 "이 시각 막혀 있을 확률 N%"(경로 위 가장 높은 P)
// + "공지 일정 기준 예상 위치" + 재생 버튼(통제 시간 전체를 12초에)
export function EventCard({
  event,
  atMs,
  onClose,
  onAvoid,
  march = null,
  playMs = null,
  onPlay,
}: {
  event: ClosureEvent;
  atMs: number;
  onClose: () => void;
  /** 이 사건을 피해서 길찾기 (T7.6) — 없으면 버튼을 안 그린다 */
  onAvoid?: () => void;
  /** 행진 예상 위치 키프레임 (T7.16) — 대상이 아니면 null */
  march?: MarchResponse | null;
  /** 재생 중인 시각 — 확률은 이 시각으로 */
  playMs?: number | null;
  /** 재생·정지 (T7.16) */
  onPlay?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const kind = eventKind(event, atMs);
  const probability = march ? probabilityAt(march, playMs ?? atMs) : null;
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
      {march && probability !== null && (
        <div className={styles.march}>
          <p className={styles.probability} style={{ color: pColor(probability) }}>
            {marchProbabilityKo(probability)}
          </p>
          <p className={styles.basis}>
            {MARCH_KO.basis}
            {playMs !== null && ` · ${MARCH_KO.playing}`}
          </p>
          {onPlay && (
            <button
              type="button"
              className={styles.play}
              aria-pressed={playMs !== null}
              onClick={onPlay}
            >
              {playMs !== null ? MARCH_KO.stop : MARCH_KO.play}
            </button>
          )}
        </div>
      )}
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
