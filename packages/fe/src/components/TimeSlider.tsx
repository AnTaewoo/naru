"use client";

import { hhmm } from "../i18n/ko";
import { kstIso, minutesFromDayStart, useTime, useTimeDispatch } from "../state/TimeProvider";
import styles from "./TimeSlider.module.css";

// 기준 시각 슬라이더 — Time state 만 읽는다 (closures 가 바뀌어도 재렌더되지 않는다, CONVENTIONS §5.5)
export function TimeSlider() {
  const time = useTime();
  const dispatch = useTimeDispatch();
  const minutes = minutesFromDayStart(time);
  const day = time.ready ? time.dayStart.slice(0, 10) : "—";
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
            {day}
            {/* 다른 날·시각을 보다가 지금으로 (T5.4 통제 불러오기의 짝) */}
            <button
              type="button"
              className={styles.now}
              aria-label="지금 시각으로"
              disabled={!time.ready}
              onClick={() => dispatch({ type: "set", t: kstIso(Date.now()) })}
            >
              지금
            </button>
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
