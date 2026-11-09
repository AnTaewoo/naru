"use client";

import { hhmm } from "../i18n/ko";
import {
  isNowAt,
  kstIso,
  minutesFromDayStart,
  useTime,
  useTimeDispatch,
} from "../state/TimeProvider";
import styles from "./TimeSlider.module.css";

// 기준 시각 슬라이더 — Time state 만 읽는다 (closures 가 바뀌어도 재렌더되지 않는다, CONVENTIONS §5.5).
// nowButton false 면 '지금'·'지금으로' 를 안 그린다 — 서울 통제 시트는 맨 위에 "지금으로 돌아가기" (T7.12)
export function TimeSlider({ nowButton = true }: { nowButton?: boolean } = {}) {
  const time = useTime();
  const dispatch = useTimeDispatch();
  const minutes = minutesFromDayStart(time);
  const day = time.ready ? time.dayStart.slice(0, 10) : "";
  return (
    <div className={styles.slider}>
      <button
        type="button"
        className={styles.step}
        aria-label="10분 전"
        disabled={!time.ready}
        onClick={() => dispatch({ type: "step", deltaMin: -time.stepMin })}
      >
        −
      </button>
      <div className={styles.track}>
        <span className={styles.label}>
          <span className={styles.day}>
            {/* 달력 (T7.11) — 바꾸면 그날 같은 시각. 데모·지난 통제를 날짜로 본다 */}
            <input
              type="date"
              aria-label="날짜"
              className={styles.date}
              value={day}
              disabled={!time.ready}
              onChange={(e) => {
                const value = e.currentTarget.value;
                if (value) dispatch({ type: "setDay", day: value });
              }}
            />
            {/* 실제 지금이면 '지금' 배지(T5.9), 다른 날·시각이면 지금으로 돌아가는 버튼(T5.4) */}
            {!nowButton ? null : time.ready && isNowAt(time.t, Date.now()) ? (
              <span className={styles.nowBadge}>지금</span>
            ) : (
              <button
                type="button"
                className={styles.now}
                aria-label="지금 시각으로"
                disabled={!time.ready}
                onClick={() => dispatch({ type: "set", t: kstIso(Date.now()), live: true })}
              >
                지금으로
              </button>
            )}
          </span>
          <strong className={styles.time}>{time.ready ? hhmm(time.t) : "—"}</strong>
        </span>
        <input
          type="range"
          aria-label="기준 시각"
          min={0}
          max={24 * 60}
          step={time.stepMin}
          value={minutes}
          disabled={!time.ready}
          onChange={(e) =>
            dispatch({ type: "setMinutes", minutesFromDayStart: Number(e.currentTarget.value) })
          }
        />
      </div>
      <button
        type="button"
        className={styles.step}
        aria-label="10분 뒤"
        disabled={!time.ready}
        onClick={() => dispatch({ type: "step", deltaMin: time.stepMin })}
      >
        +
      </button>
    </div>
  );
}
