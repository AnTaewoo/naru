"use client";

import { LOCATING_KO, MY_LOCATION_KO, locateButtonKo, odHintKo } from "../i18n/ko";
import type { LngLat } from "../map/layers/routeLayer";
import { useRoute, useRouteDispatch, type OdField } from "../state/RouteProvider";
import { minutesOf } from "./RouteCard";
import styles from "./RoutePanel.module.css";

// 시안 01 검색창 자리 → 길찾기 바. 길찾기를 켜면 시안 02 rpanel(뒤로·출발/도착·내 위치·바꾸기·탭).
// 장소 검색은 아직 없어서(T5.8) 지도를 누르거나 내 위치(T5.7). 탭은 "가장 빠른 길"만 — 계단 없는 길·기다렸다 출발은 계약에 없다
export function coordLabel(p: LngLat): string {
  return `${p[1].toFixed(5)}, ${p[0].toFixed(5)}`;
}

function samePoint(a: LngLat, b: LngLat | null): boolean {
  return b !== null && a[0] === b[0] && a[1] === b[1];
}

/** 칸에 쓰는 글 — 찾는 중 / 내 위치 / 좌표 / 비었으면 지도를 누르라고 */
function fieldText(
  which: OdField,
  p: LngLat | null,
  locating: OdField | null,
  mine: LngLat | null,
): string {
  if (locating === which) return LOCATING_KO;
  if (!p) return odHintKo(which);
  return samePoint(p, mine) ? MY_LOCATION_KO : coordLabel(p);
}

function Field({ which, text, filled }: { which: OdField; text: string; filled: boolean }) {
  const dispatch = useRouteDispatch();
  const name = which === "from" ? "출발" : "도착";
  return (
    <button
      type="button"
      className={styles.f}
      aria-label={`${name} ${text}`}
      title={`누르면 ${name}을 다시 고른다`}
      onClick={() => dispatch({ type: "unset", which })}
    >
      <small>{name}</small>
      <span className={filled ? styles.v : styles.hint}>{text}</span>
    </button>
  );
}

/** 칸 옆 '내 위치' — 누르면 그 칸을 내 위치로 (찾는 동안 aria-busy) */
function LocateButton({ which, busy }: { which: OdField; busy: boolean }) {
  const dispatch = useRouteDispatch();
  return (
    <button
      type="button"
      className={
        busy ? `${styles.icon} ${styles.loc} ${styles.busy}` : `${styles.icon} ${styles.loc}`
      }
      aria-label={locateButtonKo(which)}
      aria-busy={busy}
      title={locateButtonKo(which)}
      onClick={() => dispatch({ type: "locate", which })}
    >
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
        <circle cx="10" cy="10" r="5.5" stroke="currentColor" strokeWidth="1.8" fill="none" />
        <circle cx="10" cy="10" r="2.2" fill="currentColor" />
        <path
          d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    </button>
  );
}

export function RoutePanel() {
  const { active, from, to, route, locate, mine } = useRoute();
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
  const locating = locate?.status === "locating" ? locate.which : null;
  const fromText = fieldText("from", from, locating, mine);
  const toText = fieldText("to", to, locating, mine);
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
        <Field which="from" text={fromText} filled={from !== null && locating !== "from"} />
        <LocateButton which="from" busy={locating === "from"} />
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
        <Field which="to" text={toText} filled={to !== null && locating !== "to"} />
        <LocateButton which="to" busy={locating === "to"} />
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
