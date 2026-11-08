"use client";

import { useState } from "react";
import { LEG_KO, distanceKo, hhmm, routeErrorKo, routeNoteKo } from "../i18n/ko";
import { CROSSING_KINDS } from "../map/layers/routeLayer";
import { useRoute } from "../state/RouteProvider";
import { useTime } from "../state/TimeProvider";
import type { LegKind, RouteResponse } from "../types/contracts";
import { ClosureEvents } from "./ClosureEvents";
import { EvidencePopover } from "./EvidencePopover";
import { LegList } from "./LegList";
import styles from "./RouteCard.module.css";
import { TimeSlider } from "./TimeSlider";

// 길찾기 결과 하단 시트 (시안 02): 가장 빠른 길 카드 · 원래 길 카드(막힘·해제 시각) · 안내 문장 · 출발 시각
// · 경로 상세(LegList) / 통제 근거(EvidencePopover). 숫자는 전부 /route 응답에서
export interface FastestCard {
  minutes: number;
  distance: string;
  arrive: string;
  facts: { kind: LegKind; count: number }[];
}

export interface OriginalCard {
  minutes: number;
  distance: string;
  /** 피한 횡단보도에 확인(confirmed)이 있으면 지금 못 가는 길 */
  blocked: boolean;
  crosswalks: number;
  /** 가장 늦은 해제 시각. 하나라도 종료 미정이면 null */
  until: string | null;
}

/** 카드에 세는 레그 종류와 순서 — 길을 건너는 방법 */
const FACT_KINDS: readonly LegKind[] = ["underpass", "overpass", "crosswalk", "stairs", "elevator"];

export function minutesOf(seconds: number): number {
  return Math.round(seconds / 60);
}

export function fastestCard(route: RouteResponse, t: string): FastestCard {
  const minutes = minutesOf(route.duration_s);
  const arrive = new Date(new Date(t).getTime() + minutes * 60_000).toISOString();
  const facts = FACT_KINDS.map((kind) => ({
    kind,
    count: route.legs.filter((l) => l.kind === kind).length,
  })).filter((f) => f.count > 0);
  return { minutes, distance: distanceKo(route.distance_m), arrive: hhmm(arrive), facts };
}

export function originalCard(route: RouteResponse): OriginalCard | null {
  if (route.avoided.length === 0) return null;
  const untils = route.avoided.map((a) => a.until ?? null);
  let until: string | null = null;
  if (!untils.includes(null)) {
    for (const u of untils) {
      if (u && (!until || new Date(u).getTime() > new Date(until).getTime())) until = u;
    }
  }
  return {
    minutes: minutesOf(route.baseline.duration_s),
    distance: distanceKo(route.baseline.distance_m),
    blocked: route.avoided.some((a) => a.status === "confirmed"),
    crosswalks: new Set(route.avoided.map((a) => a.crosswalk_id)).size,
    until,
  };
}

/** 경로가 건너는 첫 지하보도·육교 — 이름이 없으면 종류 라벨 */
export function routeCrossing(route: RouteResponse): string | null {
  const leg = route.legs.find((l) => CROSSING_KINDS.includes(l.kind));
  return leg ? leg.name || LEG_KO[leg.kind] : null;
}

type Panel = "legs" | "evidence" | "events" | null;

export function RouteCard() {
  const { status, route, errorCode, at } = useRoute();
  const { t } = useTime();
  const [panel, setPanel] = useState<Panel>(null);
  const toggle = (p: Exclude<Panel, null>) => setPanel((v) => (v === p ? null : p));
  const fast = route ? fastestCard(route, at ?? t) : null;
  const orig = route ? originalCard(route) : null;
  const hasAvoided = (route?.avoided.length ?? 0) > 0;
  return (
    <section className={styles.sheet} aria-label="길찾기 결과">
      <div className={styles.handle} />
      {route && fast ? (
        <>
          <div className={styles.cards}>
            <article className={`${styles.card} ${styles.sel}`} aria-label="가장 빠른 길">
              <span className={`${styles.badge} ${styles.blue}`}>가장 빠름</span>
              <div className={styles.t}>
                {fast.minutes}
                <small>분</small>
                <span>
                  {fast.distance} · {fast.arrive} 도착
                </span>
              </div>
              <div className={styles.facts}>
                {fast.facts.map((f) => (
                  <span key={f.kind}>
                    {LEG_KO[f.kind]} <b>{f.count}</b>
                  </span>
                ))}
                {fast.facts.length === 0 && <span>보도만 걸어요</span>}
              </div>
            </article>
            {orig && (
              <article
                className={`${styles.card} ${orig.blocked ? styles.blocked : ""}`}
                aria-label="원래 길"
              >
                <span className={`${styles.badge} ${orig.blocked ? styles.stop : styles.slow}`}>
                  {orig.blocked ? "지금 못 감" : "통제 예정"}
                </span>
                <div className={styles.t}>
                  {orig.minutes}
                  <small>분</small>
                  <span>{orig.distance}</span>
                </div>
                <div className={styles.facts}>
                  <span>
                    횡단보도 {orig.crosswalks}곳 통제{orig.blocked ? "" : " 예정"} ·{" "}
                    {orig.until ? `${hhmm(orig.until)} 해제` : "종료 미정"}
                  </span>
                </div>
              </article>
            )}
          </div>
          <p className={orig ? styles.note : `${styles.note} ${styles.ok}`}>
            {routeNoteKo({
              crosswalks: orig?.crosswalks ?? 0,
              until: orig?.until ?? null,
              blocked: orig?.blocked ?? false,
              crossing: routeCrossing(route),
            })}
            {!orig && (
              <>
                {" "}
                <button type="button" className={styles.inline} onClick={() => toggle("events")}>
                  통제 불러오기
                </button>
              </>
            )}
          </p>
        </>
      ) : (
        <p className={status === "error" ? `${styles.msg} ${styles.error}` : styles.msg}>
          {status === "error"
            ? routeErrorKo(errorCode)
            : status === "loading"
              ? "경로 찾는 중…"
              : "지도를 눌러 출발·도착을 골라 주세요"}
        </p>
      )}
      <TimeSlider />
      {route && (
        <div className={styles.cta}>
          <button type="button" aria-pressed={panel === "legs"} onClick={() => toggle("legs")}>
            경로 상세
          </button>
          {hasAvoided && (
            <button
              type="button"
              aria-pressed={panel === "evidence"}
              onClick={() => toggle("evidence")}
            >
              통제 근거
            </button>
          )}
        </div>
      )}
      {route && panel === "legs" && <LegList route={route} />}
      {route && hasAvoided && panel === "evidence" && <EvidencePopover route={route} />}
      {panel === "events" && <ClosureEvents focusMap={false} onDone={() => setPanel(null)} />}
    </section>
  );
}
