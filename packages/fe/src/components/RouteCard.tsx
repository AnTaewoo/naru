"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  AVOID_KO,
  LEG_KO,
  avoidBannerKo,
  distanceKo,
  graceEndIso,
  eventTitleKo,
  hhmm,
  locateNoteKo,
  routeErrorKo,
  routeNoteKo,
} from "../i18n/ko";
import { CROSSING_KINDS, routeOdKey } from "../map/layers/routeLayer";
import { useClosures } from "../state/ClosureProvider";
import { useRoute, useRouteDispatch, type RouteView } from "../state/RouteProvider";
import { useTime } from "../state/TimeProvider";
import type { Avoided, LegKind, RouteResponse } from "../types/contracts";
import { BottomSheet, type SheetStage } from "./BottomSheet";
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
  /** 상태별 횡단보도 수 — confirmed "통제 중" / scheduled "공지상 통제 시간 · 현장 확인 전" (ADR-011 A) */
  confirmed: number;
  scheduled: number;
  /** "이 구역 피해서"(T7.6)로 피한 곳 — 지금 통제 중이 아니면 상태(예정·해제)와 상관없이 여기 */
  requested: number;
  /** 상태로 피한 곳의 가장 늦은 해제 시각. 하나라도 종료 미정이거나 상태로 피한 곳이 없으면 null */
  until: string | null;
}

/** 길찾기 avoid 로 보낸 사건 (INTERFACE §2 v0.14) — 응답 avoided 에서 그 사건 항목을 reason·끝으로 알아본다 */
export interface AvoidTarget {
  reason: string;
  end: string | null;
}

function sameEnd(a: string | null, b: string | null): boolean {
  return a === b || (a !== null && b !== null && Date.parse(a) === Date.parse(b));
}

/** 피해 달라고 한 구역의 항목 — 통제 중이면 막힘 그대로. 해제·예정 구역은 avoid 로만 오고, 예정은 사건으로 가른다 */
function isRequested(a: Avoided, avoid: AvoidTarget | null): boolean {
  if (a.status === "confirmed") return false;
  if (a.status !== "scheduled") return true;
  return avoid !== null && a.reason === avoid.reason && sameEnd(a.until ?? null, avoid.end);
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

export function originalCard(
  route: RouteResponse,
  avoid: AvoidTarget | null = null,
): OriginalCard | null {
  if (route.avoided.length === 0) return null;
  const ruled = route.avoided.filter((a) => !isRequested(a, avoid));
  const untils = ruled.map((a) => a.until ?? null);
  let until: string | null = null;
  if (!untils.includes(null)) {
    for (const u of untils) {
      if (u && (!until || new Date(u).getTime() > new Date(until).getTime())) until = u;
    }
  }
  const count = (xs: readonly Avoided[]) => new Set(xs.map((a) => a.crosswalk_id)).size;
  return {
    minutes: minutesOf(route.baseline.duration_s),
    distance: distanceKo(route.baseline.distance_m),
    blocked: route.avoided.some((a) => a.status === "confirmed"),
    crosswalks: count(route.avoided),
    confirmed: count(ruled.filter((a) => a.status === "confirmed")),
    scheduled: count(ruled.filter((a) => a.status === "scheduled")),
    requested: count(route.avoided.filter((a) => isRequested(a, avoid))),
    until,
  };
}

/**
 * 원래 길 카드 둘째 줄 — "횡단보도 통제 중 2곳 · 08:30 해제", 예정이면 "공지상 통제 시간 1곳 · 현장 확인 전",
 * 피해 달라고 한 구역(T7.6)은 "피한 구역 1곳"(해제 시각 없음). t(경로 시각)에 해제 예정이 지났으면 "09:00까지 정리 중"
 */
export function originalFactsKo(orig: OriginalCard, t?: string): string {
  const parts: string[] = [];
  if (orig.confirmed > 0) parts.push(`통제 중 ${orig.confirmed}곳`);
  if (orig.scheduled > 0) parts.push(`공지상 통제 시간 ${orig.scheduled}곳 · 현장 확인 전`);
  if (orig.requested > 0) parts.push(`피한 구역 ${orig.requested}곳`);
  if (orig.confirmed + orig.scheduled === 0) return `횡단보도 ${parts.join(" · ")}`;
  // 해제 예정이 지났는데 막혀 있으면 정리 시간(30분) — "09:00까지 정리 중" (태우 11/10)
  const past = orig.until !== null && t !== undefined && Date.parse(t) >= Date.parse(orig.until);
  const until = !orig.until
    ? "종료 미정"
    : past
      ? `${hhmm(graceEndIso(orig.until))}까지 정리 중`
      : `${hhmm(orig.until)} 해제`;
  return `횡단보도 ${parts.join(" · ")} · ${until}`;
}

/** 경로가 건너는 첫 지하보도·육교 — 이름이 없으면 종류 라벨 */
export function routeCrossing(route: RouteResponse): string | null {
  const leg = route.legs.find((l) => CROSSING_KINDS.includes(l.kind));
  return leg ? leg.name || LEG_KO[leg.kind] : null;
}

type Panel = "legs" | "evidence" | null;

function cardClass(
  base: string | undefined,
  pressable: boolean,
  selected: string | false | undefined,
): string {
  return [base, pressable ? styles.pressable : "", selected || ""].filter(Boolean).join(" ");
}

/** 카드 전체가 버튼 (T5.11) — 원래 길 카드가 있을 때만. 버튼 안이라 내용은 span 만 쓴다 */
function CardPress({
  on,
  pressed,
  onPress,
  children,
}: {
  on: boolean;
  pressed: boolean;
  onPress: () => void;
  children: ReactNode;
}) {
  if (!on) return <>{children}</>;
  return (
    <button type="button" className={styles.press} aria-pressed={pressed} onClick={onPress}>
      {children}
    </button>
  );
}

export function RouteCard() {
  const { status, route, errorCode, at, locate, view, avoid } = useRoute();
  // 피할 사건(T7.6) — 지도 사건·넓은 창 목록에서 제목과 reason·끝을 찾는다
  const { events, catalog } = useClosures();
  const target = avoid
    ? (events?.find((e) => e.id === avoid) ?? catalog?.find((e) => e.id === avoid) ?? null)
    : null;
  const dispatch = useRouteDispatch();
  const { t } = useTime();
  const [panel, setPanel] = useState<Panel>(null);
  const [stage, setStage] = useState<SheetStage>("half");
  // 새 출발·도착의 첫 경로가 오면 시트를 접는다 — 지도가 경로 전체를 보여 준다 (T5.6, MapView 와 같은 키)
  const odKey = routeOdKey(route);
  useEffect(() => {
    if (odKey) setStage("collapsed");
  }, [odKey]);
  const toggle = (p: Exclude<Panel, null>) => {
    if (panel !== p) setStage("full"); // 경로 상세·통제 근거는 길다
    setPanel(panel === p ? null : p);
  };
  const fast = route ? fastestCard(route, at ?? t) : null;
  const orig = route
    ? originalCard(route, target ? { reason: target.reason, end: target.window.end ?? null } : null)
    : null;
  const hasAvoided = (route?.avoided.length ?? 0) > 0;
  const original = view === "original" && orig !== null;
  // 카드를 누르면 그 길을 지도에서 본다 — 시트를 접고 MapView 가 그 길에 맞춘다 (T5.11)
  const choose = (v: RouteView) => {
    dispatch({ type: "view", view: v });
    setStage("collapsed");
  };
  // 내 위치를 칸에 못 넣었거나 찾는 중 (T5.7) — 경로가 있어도 맨 위에
  const locateNote = locate ? locateNoteKo(locate.which, locate.status) : null;
  return (
    <BottomSheet label="길찾기 결과" stage={stage} onStage={setStage}>
      {avoid && (
        <p className={styles.avoid}>
          <span>{avoidBannerKo(target ? eventTitleKo(target) : null)}</span>
          <button type="button" onClick={() => dispatch({ type: "avoid", id: null })}>
            {AVOID_KO.remove}
          </button>
        </p>
      )}
      {route && fast ? (
        <>
          {locateNote && <p className={styles.msg}>{locateNote}</p>}
          <div className={styles.cards}>
            <article
              className={cardClass(styles.card, orig !== null, !original && styles.sel)}
              aria-label="가장 빠른 길"
            >
              <CardPress on={orig !== null} pressed={!original} onPress={() => choose("fastest")}>
                <span className={`${styles.badge} ${styles.blue}`}>가장 빠름</span>
                <span className={styles.t}>
                  {fast.minutes}
                  <small>분</small>
                  <span>
                    {fast.distance} · {fast.arrive} 도착
                  </span>
                </span>
                <span className={styles.facts}>
                  {fast.facts.map((f) => (
                    <span key={f.kind}>
                      {LEG_KO[f.kind]} <b>{f.count}</b>
                    </span>
                  ))}
                  {fast.facts.length === 0 && <span>보도만 걸어요</span>}
                </span>
              </CardPress>
            </article>
            {orig && (
              <article
                className={cardClass(
                  `${styles.card} ${orig.blocked ? styles.blocked : ""}`,
                  true,
                  original && (orig.blocked ? styles.selStop : styles.selSlow),
                )}
                aria-label="원래 길"
              >
                <CardPress on pressed={original} onPress={() => choose("original")}>
                  <span className={`${styles.badge} ${orig.blocked ? styles.stop : styles.slow}`}>
                    {orig.blocked
                      ? "지금 못 감"
                      : orig.scheduled > 0
                        ? "공지상 통제 시간"
                        : "피한 구역"}
                  </span>
                  <span className={styles.t}>
                    {orig.minutes}
                    <small>분</small>
                    <span>{orig.distance}</span>
                  </span>
                  <span className={styles.facts}>
                    <span>{originalFactsKo(orig, at ?? t)}</span>
                  </span>
                </CardPress>
              </article>
            )}
          </div>
          <p className={orig ? styles.note : `${styles.note} ${styles.ok}`}>
            {routeNoteKo({
              crosswalks: orig?.crosswalks ?? 0,
              until: orig?.until ?? null,
              blocked: orig?.blocked ?? false,
              crossing: routeCrossing(route),
              requested: orig?.requested ?? 0,
              avoiding: avoid !== null,
              t: at ?? t,
            })}
          </p>
        </>
      ) : (
        <p className={status === "error" ? `${styles.msg} ${styles.error}` : styles.msg}>
          {status === "error"
            ? routeErrorKo(errorCode)
            : status === "loading"
              ? "경로 찾는 중…"
              : (locateNote ?? "지도를 눌러 출발·도착을 골라 주세요")}
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
    </BottomSheet>
  );
}
