"use client";

import { LEG_KO } from "../i18n/ko";
import { LEG_COLOR } from "../map/colors";
import type { LegKind, RouteResponse } from "../types/contracts";
import styles from "./LegList.module.css";

// 경로 상세 (시안 02 cta "경로 상세") — 레그 한 줄씩: 이름(없으면 종류)·종류·거리
export interface LegRow {
  key: string;
  kind: LegKind;
  title: string;
  sub: string | null;
  distance: string;
}

export function legRows(route: RouteResponse): LegRow[] {
  return route.legs.map((leg, k) => ({
    key: `${k}-${leg.kind}`,
    kind: leg.kind,
    title: leg.name || LEG_KO[leg.kind],
    sub: leg.name ? LEG_KO[leg.kind] : null,
    distance: `${Math.round(leg.distance_m)}m`,
  }));
}

export function LegList({ route }: { route: RouteResponse }) {
  return (
    <ol className={styles.legs} aria-label="경로 상세">
      {legRows(route).map((r) => (
        <li key={r.key} className={styles.row}>
          <span className={styles.ico} style={{ background: LEG_COLOR[r.kind] }} aria-hidden />
          <span className={styles.text}>
            <b className={styles.title}>{r.title}</b>
            {r.sub && <span className={styles.sub}>{r.sub}</span>}
          </span>
          <em className={styles.dist}>{r.distance}</em>
        </li>
      ))}
    </ol>
  );
}
