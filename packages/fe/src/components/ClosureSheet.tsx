"use client";

import { useMemo, useState } from "react";
import {
  STATUS_BADGE_KO,
  dataAsOfKo,
  eventDetailKo,
  eventTitleKo,
  hhmm,
  sheetTitleKo,
  untilKo,
  windowKo,
} from "../i18n/ko";
import { COLORS } from "../map/colors";
import {
  KIND_COLOR,
  chipCounts,
  listedEvents,
  type EventKind,
  type ListedEvent,
} from "../map/eventKinds";
import { useClosures } from "../state/ClosureProvider";
import { useTime } from "../state/TimeProvider";
import { BottomSheet, type SheetStage } from "./BottomSheet";
import styles from "./ClosureSheet.module.css";
import { ClosureTimeline } from "./ClosureTimeline";
import { TimeSlider } from "./TimeSlider";

// 목업 01_home 하단 시트: 제목/부제 → 기준 시각 → 타임라인+슬라이더 → 통제 행(사건 한 건 = 한 행).
// T7.4: 행은 지금 지도 사건(서울 전체, /closures/events?at=t) — 칩과 같은 기준(해제·확신도 0.7 미만 빼고).
// 제목·둘째 줄은 파서 요약, 원문은 "공지 원문 보기"에서만 (T5.9). 목록·카드는 T7.5 에서 다시
const KIND_BG: Record<EventKind, string> = {
  confirmed: COLORS.stopBg,
  soon: COLORS.slowBg,
  scheduled: COLORS.slowBg,
  zone: COLORS.zoneBg,
  released: COLORS.grayBg,
};

function badge({ event, kind }: ListedEvent, t: string): string {
  if (kind === "confirmed") return untilKo(event.window.end ?? null, t);
  return STATUS_BADGE_KO[event.status];
}

export function ClosureSheet() {
  const { events, eventsAt, eventsError, truncated, dataAsOf } = useClosures();
  const { t, ready } = useTime();
  const atMs = eventsAt ? Date.parse(eventsAt) : 0;
  const rows = useMemo(() => listedEvents(events ?? [], atMs), [events, atMs]);
  const counts = useMemo(() => chipCounts(events ?? [], atMs), [events, atMs]);
  // "공지 원문 보기"로 펼친 행 (T5.9) — 원문은 여기서만
  const [opened, setOpened] = useState<string | null>(null);
  // 시트는 절반에서 시작 (T5.6)
  const [stage, setStage] = useState<SheetStage>("half");
  // 서버 렌더·하이드레이션 중엔 "오늘" — 시각이 정해진 뒤에야 지금과 비교한다
  const title = ready ? sheetTitleKo(t, Date.now()) : "오늘 통제";
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
  // 목록 위 데이터 기준 시각 (결정 C) — 실시간 돌발이 없거나 30분 넘게 오래면 회색 경고
  const asof = ready && dataAsOf ? dataAsOfKo(dataAsOf, Date.now()) : null;
  return (
    <BottomSheet label={title} stage={stage} onStage={setStage}>
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
      <div className={styles.rows}>
        {rows.map((row) => {
          const { event, kind } = row;
          const detail = eventDetailKo(event);
          const notice = event.notice;
          return (
            <div key={event.id} className={styles.row}>
              <span className={styles.ico} style={{ background: KIND_BG[kind] }}>
                <span className={styles.dot} style={{ background: KIND_COLOR[kind] }} />
              </span>
              <div className={styles.rowText}>
                <b className={styles.rowTitle}>{eventTitleKo(event)}</b>
                {detail && <span className={styles.rowDetail}>{detail}</span>}
                <span className={styles.rowSub}>
                  {event.approx ? "약 " : ""}
                  {windowKo(event.window.start, event.window.end)} · 횡단보도 {event.crosswalks}곳
                </span>
                {notice && (
                  <button
                    type="button"
                    className={styles.raw}
                    aria-expanded={opened === event.id}
                    onClick={() => setOpened(opened === event.id ? null : event.id)}
                  >
                    공지 원문 보기
                  </button>
                )}
                {notice && opened === event.id && (
                  <p className={styles.excerpt}>{notice.excerpt}</p>
                )}
              </div>
              <em className={styles.badge} style={{ color: KIND_COLOR[kind] }}>
                {badge(row, t)}
              </em>
            </div>
          );
        })}
        {events !== null && rows.length === 0 && (
          <p className={styles.empty}>이 시각부터 내일까지 서울에 잡힌 통제가 없어요.</p>
        )}
      </div>
    </BottomSheet>
  );
}
