"use client";

import { useEffect, useMemo, useState } from "react";
import {
  EXAMPLE_KO,
  SECTION_KO,
  bannerKo,
  dayLabelKo,
  eventDetailKo,
  eventTitleKo,
  hhmm,
  liveTitleKo,
  moreKo,
  nowEmptyKo,
  sheetBadgeKo,
  windowKo,
} from "../i18n/ko";
import {
  KIND_BG,
  KIND_COLOR,
  byDistrict,
  chipCounts,
  districtChips,
  isLow,
  sheetSections,
  type ListedEvent,
} from "../map/eventKinds";
import { EXAMPLES } from "../map/examples";
import { asBbox4, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { useRouteDispatch } from "../state/RouteProvider";
import { isNowAt, kstIso, useTime, useTimeDispatch } from "../state/TimeProvider";
import type { ClosureEvent } from "../types/contracts";
import { BottomSheet, type SheetStage } from "./BottomSheet";
import { ClosureTimeline } from "./ClosureTimeline";
import { EventCard } from "./EventCard";
import styles from "./LiveSheet.module.css";
import { StaleWarning } from "./StaleWarning";
import { TimeSlider } from "./TimeSlider";

/** 지난 통제는 처음에 이만큼, 나머지는 "더 보기" (태우 11/10) */
const PAST_FIRST = 5;

// 서울 통제 시트 (T7.5 → T7.12 세 묶음, ADR-014 A) — 하단 시트 기본. (지금이 아니면 "M월 D일 HH:MM 기준 ·
// 지금으로 돌아가기") 제목·부제 → 시간표·슬라이더 → 구 칩 → 지금(통제 중·1시간 안) · 다가오는 통제(날짜별) ·
// 지난 통제(최근 5 + 더 보기) → 예시로 보기. 목록은 t 앞뒤 365일 넓은 창(catalog, 아직이면 지도 사건).
// 지금 행은 카드, 다가오는·지난 행은 그 시작 시각으로 옮기고 카드. 0.7 미만은 목록에 없다(지도에서 고른 묶음엔 있다)
export function LiveSheet() {
  const { events, eventsAt, eventsError, truncated, bbox, selected, picked, catalog, catalogAt } =
    useClosures();
  const dispatch = useClosureDispatch();
  const timeDispatch = useTimeDispatch();
  const routeDispatch = useRouteDispatch();
  const { t, ready, live: following } = useTime();
  const atMs = eventsAt ? Date.parse(eventsAt) : 0;
  // 목록 — 넓은 창(t 기준 상태)을 받기 전엔 지도 사건으로
  const list = useMemo(() => catalog ?? events ?? [], [catalog, events]);
  const listAtMs = catalog && catalogAt ? Date.parse(catalogAt) : atMs;
  const [district, setDistrict] = useState<string | null>(null);
  const [allPast, setAllPast] = useState(false);
  const [stage, setStage] = useState<SheetStage>("half");
  // 지금 모드(1분마다 확인해 5분마다 따라간다)면 몇 분 뒤처져도 지금이다
  const live = ready && (following || isNowAt(t, Date.now()));
  const fromMap = selected ? events?.find((e) => e.id === selected) : undefined;
  const fromList = selected ? catalog?.find((e) => e.id === selected) : undefined;
  const card: ClosureEvent | null = fromMap ?? fromList ?? null;
  const cardAtMs = fromMap ? atMs : listAtMs;
  // 지도·?event=·목록으로 카드나 묶음을 열면 접힌 시트를 절반으로
  useEffect(() => {
    if (card || picked) setStage((s) => (s === "collapsed" ? "half" : s));
  }, [card, picked]);
  const chips = useMemo(
    () =>
      districtChips(
        list.filter((e) => !isLow(e)),
        asBbox4(bbox.split(",").map(Number)),
      ),
    [list, bbox],
  );
  const sections = useMemo(() => {
    const scope = picked ? list.filter((e) => picked.includes(e.id)) : byDistrict(list, district);
    return sheetSections(scope, listAtMs, picked !== null);
  }, [list, listAtMs, picked, district]);
  const counts = useMemo(() => chipCounts(events ?? [], atMs), [events, atMs]);
  // 서버 렌더·하이드레이션 중엔 시각이 없다 — 정해진 뒤에야 지금과 비교한다
  const title = liveTitleKo(!ready || live);
  const total = counts.confirmed + counts.scheduled + counts.zone;
  const zone = counts.zone > 0 ? `, 예정 구역 ${counts.zone}건` : "";
  const counted =
    events === null
      ? null
      : total === 0
        ? "서울 통제 없음"
        : `서울 통제 중 ${counts.confirmed}건, 예정 ${counts.scheduled}건${zone}`;
  // 지금이면 "02:31 기준 · …", 아니면 시각은 맨 위 기준 줄에 있다
  const at = `${hhmm(t)} 기준`;
  const subtitle = !ready
    ? "시각 확인 중…"
    : live
      ? [at, counted].filter((x) => x !== null).join(" · ")
      : (counted ?? "서울 통제");
  // 슬라이더를 옮겨 새 시각의 사건을 받는 중
  const loading = ready && (events === null || (eventsAt !== null && atMs !== Date.parse(t)));
  // 다가오는·지난 행 — 예전 '통제 불러오기'처럼 그 시작 시각으로(지금 모드 끔) + 카드 + 지도 맞춤
  const jump = (e: ClosureEvent) => {
    if (e.window.start) timeDispatch({ type: "set", t: e.window.start });
    dispatch({ type: "select", id: e.id });
  };
  const backToNow = () => {
    timeDispatch({ type: "set", t: kstIso(Date.now()), live: true });
    dispatch({ type: "select", id: null });
    dispatch({ type: "unpick" });
  };
  // 지금이 아닌 시각이면 시트 맨 위 기준 줄 — 목록에선 제목 자리(절반 시트에 목록이 보이게), 카드 위에도
  const banner = ready && !live && (
    <div className={styles.banner}>
      <span>{bannerKo(t)}</span>
      <button type="button" className={styles.back} onClick={backToNow}>
        지금으로 돌아가기
      </button>
    </div>
  );
  const row = ({ event, kind }: ListedEvent, open: (e: ClosureEvent) => void) => {
    const detail = eventDetailKo(event);
    return (
      <button key={event.id} type="button" className={styles.row} onClick={() => open(event)}>
        <span className={styles.ico} style={{ background: KIND_BG[kind] }}>
          <span className={styles.dot} style={{ background: KIND_COLOR[kind] }} />
        </span>
        <span className={styles.rowText}>
          <b className={styles.rowTitle}>{eventTitleKo(event)}</b>
          {detail && <span className={styles.rowDetail}>{detail}</span>}
          <span className={styles.rowSub}>
            {event.approx ? "약 " : ""}
            {windowKo(event.window.start, event.window.end)} · 횡단보도 {event.crosswalks}곳
          </span>
        </span>
        <em className={styles.badge} style={{ color: KIND_COLOR[kind] }}>
          {sheetBadgeKo(event, listAtMs)}
        </em>
      </button>
    );
  };
  return (
    <BottomSheet label={title} stage={stage} onStage={setStage}>
      {card ? (
        <>
          {banner && <div className={styles.pad}>{banner}</div>}
          <EventCard
            event={card}
            atMs={cardAtMs}
            onClose={() => dispatch({ type: "select", id: null })}
            onAvoid={() => routeDispatch({ type: "avoid", id: card.id })}
          />
        </>
      ) : (
        <>
          <div className={styles.pad}>
            {banner || <div className={styles.title}>{title}</div>}
            <div className={styles.sub}>
              {subtitle}
              {loading && !eventsError && <span className={styles.loading}> · 불러오는 중</span>}
              {eventsError && <span className={styles.error}> · {eventsError}</span>}
              {truncated && <span className={styles.loading}> · 가까운 300건만</span>}
            </div>
            <StaleWarning className={styles.stale} />
          </div>
          <ClosureTimeline />
          <TimeSlider nowButton={false} />
          <div className={styles.rows}>
            {picked ? (
              <div className={styles.picked}>
                <span>여기 통제 {picked.length}건</span>
                <button
                  type="button"
                  className={styles.back}
                  onClick={() => dispatch({ type: "unpick" })}
                >
                  전체 보기
                </button>
              </div>
            ) : (
              chips.length > 0 && (
                <div role="group" aria-label="구 필터" className={styles.chips}>
                  {[null, ...chips].map((d) => (
                    <button
                      key={d ?? "all"}
                      type="button"
                      className={styles.chip}
                      aria-pressed={district === d}
                      onClick={() => setDistrict(d)}
                    >
                      {d ?? "전체"}
                    </button>
                  ))}
                </div>
              )
            )}
            <section aria-label={live ? SECTION_KO.now : SECTION_KO.nowAt}>
              <h3 className={styles.groupHead}>
                {live ? SECTION_KO.now : SECTION_KO.nowAt}
                <span>{sections.now.length}</span>
              </h3>
              {sections.now.map((r) => row(r, (e) => dispatch({ type: "select", id: e.id })))}
              {sections.now.length === 0 && <p className={styles.empty}>{nowEmptyKo(live)}</p>}
            </section>
            {sections.upcoming.length > 0 && (
              <section aria-label={SECTION_KO.upcoming}>
                <h3 className={styles.groupHead}>{SECTION_KO.upcoming}</h3>
                {sections.upcoming.map((g) => (
                  <div key={g.day} role="group" aria-label={dayLabelKo(g.day, listAtMs)}>
                    <h4 className={styles.dayHead}>{dayLabelKo(g.day, listAtMs)}</h4>
                    {g.items.map((r) => row(r, jump))}
                  </div>
                ))}
              </section>
            )}
            {sections.past.length > 0 && (
              <section aria-label={SECTION_KO.past}>
                <h3 className={styles.groupHead}>
                  {SECTION_KO.past}
                  <span>{sections.past.length}</span>
                </h3>
                {(allPast ? sections.past : sections.past.slice(0, PAST_FIRST)).map((r) =>
                  row(r, jump),
                )}
                {!allPast && sections.past.length > PAST_FIRST && (
                  <button type="button" className={styles.more} onClick={() => setAllPast(true)}>
                    {moreKo(sections.past.length - PAST_FIRST)}
                  </button>
                )}
              </section>
            )}
            {/* 예시로 보기 (T7.11) — 그 날짜·시각으로 옮기고 지도를 그 통제 구역에 */}
            <section aria-label="예시로 보기" className={styles.examples}>
              <h3 className={styles.groupHead}>예시로 보기</h3>
              {EXAMPLES.map((x) => (
                <button
                  key={x.key}
                  type="button"
                  className={styles.example}
                  onClick={() => {
                    timeDispatch({ type: "set", t: x.t });
                    dispatch({ type: "frame", bbox: x.bbox });
                  }}
                >
                  <b>{EXAMPLE_KO[x.key].title}</b>
                  <span>{EXAMPLE_KO[x.key].sub}</span>
                </button>
              ))}
            </section>
          </div>
        </>
      )}
    </BottomSheet>
  );
}
