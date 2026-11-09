"use client";

import { useEffect, useMemo, useState } from "react";
import {
  GROUP_KO,
  dataAsOfKo,
  eventDetailKo,
  eventTitleKo,
  hhmm,
  liveTitleKo,
  rowBadgeKo,
  windowKo,
} from "../i18n/ko";
import {
  KIND_BG,
  KIND_COLOR,
  byDistrict,
  chipCounts,
  districtChips,
  listedEvents,
  liveGroups,
  type ListedEvent,
} from "../map/eventKinds";
import { asBbox4, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { useTime } from "../state/TimeProvider";
import { BottomSheet, type SheetStage } from "./BottomSheet";
import { ClosureTimeline } from "./ClosureTimeline";
import { EventCard } from "./EventCard";
import styles from "./LiveSheet.module.css";
import { TimeSlider } from "./TimeSlider";

// 지금 서울 통제 (T7.5, ADR-014 A) — 하단 시트 기본. 제목·부제·기준 시각 → 시간표·슬라이더 → 구 칩 → 묶음
// (통제 중 → 1시간 안 시작 → 오늘 → 내일) 행. 행·지도를 누르면 사건 카드, 클러스터·겹친 구역이면 그 묶음 목록.
// 해제·확신도 0.7 미만은 목록에 없다(칩과 같다) — 지도에서 고른 묶음엔 흐린 사건도
export function LiveSheet() {
  const { events, eventsAt, eventsError, truncated, dataAsOf, bbox, selected, picked } =
    useClosures();
  const dispatch = useClosureDispatch();
  const { t, ready } = useTime();
  const atMs = eventsAt ? Date.parse(eventsAt) : 0;
  const [district, setDistrict] = useState<string | null>(null);
  const [stage, setStage] = useState<SheetStage>("half");
  const card = (selected && events?.find((e) => e.id === selected)) || null;
  // 지도·?event= 로 카드를 열면 접힌 시트를 절반으로
  useEffect(() => {
    if (card) setStage((s) => (s === "collapsed" ? "half" : s));
  }, [card]);
  const listed = useMemo(
    () => listedEvents(events ?? [], atMs).map((r) => r.event),
    [events, atMs],
  );
  const chips = useMemo(
    () => districtChips(listed, asBbox4(bbox.split(",").map(Number))),
    [listed, bbox],
  );
  const groups = useMemo(() => {
    const all = events ?? [];
    const scope = picked ? all.filter((e) => picked.includes(e.id)) : byDistrict(all, district);
    return liveGroups(scope, atMs, picked !== null);
  }, [events, atMs, picked, district]);
  const counts = useMemo(() => chipCounts(events ?? [], atMs), [events, atMs]);
  // 서버 렌더·하이드레이션 중엔 시각이 없다 — 정해진 뒤에야 지금과 비교한다
  const title = ready ? liveTitleKo(t, Date.now()) : "지금 서울 통제";
  const total = counts.confirmed + counts.scheduled + counts.zone;
  const zone = counts.zone > 0 ? `, 예정 구역 ${counts.zone}건` : "";
  const subtitle = !ready
    ? "시각 확인 중…"
    : events === null
      ? `${hhmm(t)} 기준`
      : total === 0
        ? `${hhmm(t)} 기준 통제 없음`
        : `${hhmm(t)} 기준 · 서울 통제 중 ${counts.confirmed}건, 예정 ${counts.scheduled}건${zone}`;
  // 슬라이더를 옮겨 새 시각의 사건을 받는 중
  const loading = ready && (events === null || (eventsAt !== null && atMs !== Date.parse(t)));
  const asof = ready && dataAsOf ? dataAsOfKo(dataAsOf, Date.now()) : null;
  const row = ({ event, kind }: ListedEvent) => {
    const detail = eventDetailKo(event);
    return (
      <button
        key={event.id}
        type="button"
        className={styles.row}
        onClick={() => dispatch({ type: "select", id: event.id })}
      >
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
          {rowBadgeKo(event, atMs)}
        </em>
      </button>
    );
  };
  return (
    <BottomSheet label={title} stage={stage} onStage={setStage}>
      {card ? (
        <EventCard
          event={card}
          atMs={atMs}
          onClose={() => dispatch({ type: "select", id: null })}
        />
      ) : (
        <>
          <div className={styles.pad}>
            <div className={styles.title}>{title}</div>
            <div className={styles.sub}>
              {subtitle}
              {loading && !eventsError && <span className={styles.loading}> · 불러오는 중</span>}
              {eventsError && <span className={styles.error}> · {eventsError}</span>}
              {truncated && <span className={styles.loading}> · 가까운 300건만</span>}
            </div>
            {asof && (
              <div className={styles.asof}>
                <span>{asof.text}</span>
                {asof.warning && <span className={styles.asofWarn}>{asof.warning}</span>}
              </div>
            )}
          </div>
          <ClosureTimeline />
          <TimeSlider />
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
          <div className={styles.rows}>
            {groups.map((g) => (
              <section key={g.key} aria-label={GROUP_KO[g.key]}>
                <h3 className={styles.groupHead}>
                  {GROUP_KO[g.key]}
                  <span>{g.items.length}</span>
                </h3>
                {g.items.map(row)}
              </section>
            ))}
            {events !== null && groups.length === 0 && (
              <p className={styles.empty}>이 시각부터 내일까지 서울에 잡힌 통제가 없어요.</p>
            )}
          </div>
        </>
      )}
    </BottomSheet>
  );
}
