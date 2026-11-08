"use client";

import type { LngLat } from "../map/layers/routeLayer";
import { useRoute, useRouteDispatch } from "../state/RouteProvider";
import { minutesOf } from "./RouteCard";
import styles from "./RoutePanel.module.css";

// 시안 01 검색창 자리 → 길찾기 바. 길찾기를 켜면 시안 02 rpanel(뒤로·출발/도착·바꾸기·탭).
// 장소 검색은 계약에 없어서 지도를 눌러 고른다. 탭은 "가장 빠른 길"만 — 계단 없는 길·기다렸다 출발은 계약에 없다
export function coordLabel(p: LngLat): string {
  return `${p[1].toFixed(5)}, ${p[0].toFixed(5)}`;
}

export function RoutePanel() {
  const { active, from, to, route } = useRoute();
  const dispatch = useRouteDispatch();
  if (!active) {
    return (
      <button
        type="button"
        className={styles.entry}
        aria-label="길찾기"
        onClick={() => dispatch({ type: "open" })}
      >
        <span className={styles.ph}>지도에서 출발·도착을 골라 길찾기</span>
        <span className={styles.go} aria-hidden>
          <svg width="20" height="20" viewBox="0 0 20 20">
            <path
              d="M4 10h10m-4-4 4 4-4 4"
              stroke="#fff"
              strokeWidth="2"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>
    );
  }
  const fromText = from ? coordLabel(from) : "지도를 눌러 출발을 고르세요";
  const toText = to ? coordLabel(to) : "지도를 눌러 도착을 고르세요";
  return (
    <section className={styles.panel} aria-label="출발·도착">
      <div className={styles.od}>
        <button
          type="button"
          className={styles.icon}
          aria-label="뒤로"
          onClick={() => dispatch({ type: "close" })}
        >
          <svg width="22" height="22" viewBox="0 0 22 22">
            <path
              d="M13 5 7 11l6 6"
              stroke="#222"
              strokeWidth="2.2"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          className={styles.f}
          aria-label={`출발 ${fromText}`}
          title="누르면 출발을 다시 고른다"
          onClick={() => dispatch({ type: "unset", which: "from" })}
        >
          <small>출발</small>
          <span className={from ? styles.v : styles.hint}>{fromText}</span>
        </button>
        <button
          type="button"
          className={`${styles.icon} ${styles.swap}`}
          aria-label="출발·도착 바꾸기"
          disabled={!from || !to}
          onClick={() => dispatch({ type: "swap" })}
        >
          <svg width="22" height="22" viewBox="0 0 22 22">
            <path
              d="M7 5v12m0 0-3-3m3 3 3-3M15 17V5m0 0-3 3m3-3 3 3"
              stroke="#777"
              strokeWidth="1.8"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <span aria-hidden />
        <button
          type="button"
          className={styles.f}
          aria-label={`도착 ${toText}`}
          title="누르면 도착을 다시 고른다"
          onClick={() => dispatch({ type: "unset", which: "to" })}
        >
          <small>도착</small>
          <span className={to ? styles.v : styles.hint}>{toText}</span>
        </button>
      </div>
      <div className={styles.modes} role="tablist" aria-label="경로 종류">
        <button type="button" role="tab" aria-selected="true" className={styles.mode}>
          <b>{route ? `${minutesOf(route.duration_s)}분` : "—"}</b>
          가장 빠른 길
        </button>
      </div>
    </section>
  );
}
