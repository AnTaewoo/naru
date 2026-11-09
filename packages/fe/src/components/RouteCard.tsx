"use client";

import { useEffect, useState, type ReactNode } from "react";
import { LEG_KO, distanceKo, hhmm, locateNoteKo, routeErrorKo, routeNoteKo } from "../i18n/ko";
import { CROSSING_KINDS, routeOdKey } from "../map/layers/routeLayer";
import { useRoute, useRouteDispatch, type RouteView } from "../state/RouteProvider";
import { useTime } from "../state/TimeProvider";
import type { LegKind, RouteResponse } from "../types/contracts";
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
  const ids = (status: string) =>
    new Set(route.avoided.filter((a) => a.status === status).map((a) => a.crosswalk_id)).size;
  return {
    minutes: minutesOf(route.baseline.duration_s),
    distance: distanceKo(route.baseline.distance_m),
    blocked: route.avoided.some((a) => a.status === "confirmed"),
    crosswalks: new Set(route.avoided.map((a) => a.crosswalk_id)).size,
    confirmed: ids("confirmed"),
    scheduled: ids("scheduled"),
    until,
  };
}

/** 원래 길 카드 둘째 줄 — "횡단보도 통제 중 2곳 · 08:30 해제", 예정이면 "공지상 통제 시간 1곳 · 현장 확인 전" */
export function originalFactsKo(orig: OriginalCard): string {
  const parts: string[] = [];
  if (orig.confirmed > 0) parts.push(`통제 중 ${orig.confirmed}곳`);
  if (orig.scheduled > 0) parts.push(`공지상 통제 시간 ${orig.scheduled}곳 · 현장 확인 전`);
  const until = orig.until ? `${hhmm(orig.until)} 해제` : "종료 미정";
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
  const { status, route, errorCode, at, locate, view } = useRoute();
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
  const orig = route ? originalCard(route) : null;
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
                    {orig.blocked ? "지금 못 감" : "공지상 통제 시간"}
                  </span>
                  <span className={styles.t}>
                    {orig.minutes}
                    <small>분</small>
                    <span>{orig.distance}</span>
                  </span>
                  <span className={styles.facts}>
                    <span>{originalFactsKo(orig)}</span>
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
