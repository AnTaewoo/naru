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
import { STATUS_BG, STATUS_COLOR } from "../map/colors";
import { countByStatus } from "../map/layers/closureLayer";
import { useClosures } from "../state/ClosureProvider";
import { useTime } from "../state/TimeProvider";
import type { ClosureEvent, FeatureCollection, Status } from "../types/contracts";
import { BottomSheet, type SheetStage } from "./BottomSheet";
import { ClosureEvents } from "./ClosureEvents";
import styles from "./ClosureSheet.module.css";
import { ClosureTimeline } from "./ClosureTimeline";
import { TimeSlider } from "./TimeSlider";

// 목업 01_home 하단 시트: 제목/부제 → 기준 시각 → 타임라인+슬라이더 → 통제 행(사건 한 건 = 한 행).
// T5.9: 행 제목·둘째 줄은 파서 요약(사건 칸), 횡단보도 수는 사건 전체, 출처 줄(시각표·확신)은 쓰지 않고
// 원문은 "공지 원문 보기"에서만
export interface ClosureRow {
  key: string;
  status: Status;
  reason: string;
  crosswalks: number;
  start: string | null;
  end: string | null;
  approx: boolean;
  /** 같은 (reason, window) 의 사건 (/closures/events) — 제목·전체 수·공지 원문 */
  event?: ClosureEvent;
}

const ORDER: Record<Status, number> = {
  confirmed: 0,
  scheduled: 1,
  zone_scheduled: 2,
  released: 3,
};

/** 횡단보도 feature 들을 후보(reason + 창) 단위 행으로 묶는다. 순수 함수 */
export function closureRows(fc: FeatureCollection): ClosureRow[] {
  const rows = new Map<string, ClosureRow>();
  for (const f of fc.features) {
    const p = f.properties;
    const start = (p.window["start"] as string | null | undefined) ?? null;
    const end = (p.window["end"] as string | null | undefined) ?? null;
    const key = `${p.reason}|${start ?? ""}|${end ?? ""}`;
    const row = rows.get(key);
    if (row) {
      row.crosswalks += 1;
      continue;
    }
    rows.set(key, {
      key,
      status: p.status,
      reason: p.reason,
      crosswalks: 1,
      start,
      end,
      approx: p.approx ?? false,
    });
  }
  return [...rows.values()].sort(
    (a, b) => ORDER[a.status] - ORDER[b.status] || (a.start ?? "").localeCompare(b.start ?? ""),
  );
}

const sameTime = (a: string | null | undefined, b: string | null | undefined) =>
  (a ?? null) === (b ?? null) || (!!a && !!b && Date.parse(a) === Date.parse(b));

/** 행마다 같은 (reason, window) 사건을 붙인다 — 횡단보도 수는 화면 영역이 아니라 사건 전체 (T5.9) */
export function withEvents(rows: ClosureRow[], events: readonly ClosureEvent[]): ClosureRow[] {
  return rows.map((row) => {
    const event = events.find(
      (e) =>
        e.reason === row.reason &&
        sameTime(e.window.start, row.start) &&
        sameTime(e.window.end, row.end),
    );
    return event ? { ...row, crosswalks: event.crosswalks, event } : row;
  });
}

function badge(row: ClosureRow, t: string): string {
  if (row.status === "confirmed") return untilKo(row.end, t);
  return STATUS_BADGE_KO[row.status];
}

export function ClosureSheet() {
  const { closures, status, error, at, events, dataAsOf } = useClosures();
  const { t, ready } = useTime();
  const rows = useMemo(() => withEvents(closureRows(closures), events ?? []), [closures, events]);
  // "공지 원문 보기"로 펼친 행 (T5.9) — 원문은 여기서만
  const [opened, setOpened] = useState<string | null>(null);
  const counts = useMemo(() => countByStatus(closures), [closures]);
  // 통제 불러오기 목록을 펼쳤나 (T5.4). 시트는 절반에서 시작 (T5.6)
  const [picking, setPicking] = useState(false);
  const [stage, setStage] = useState<SheetStage>("half");
  const openList = () => {
    setPicking(true);
    setStage("full"); // 목록은 길다
  };
  // 고르면 시트를 접고 지도가 그 통제 범위로 맞춘다 (ClosureEvents 가 focus 를 보낸다)
  const picked = () => {
    setPicking(false);
    setStage("collapsed");
  };
  // 서버 렌더·하이드레이션 중엔 "오늘" — 시각이 정해진 뒤에야 지금과 비교한다
  const title = ready ? sheetTitleKo(t, Date.now()) : "오늘 통제";
  const subtitle = !ready
    ? "시각 확인 중…"
    : counts.confirmed + counts.scheduled === 0
      ? `${hhmm(t)} 기준 통제 없음`
      : `${hhmm(t)} 기준 · 횡단보도 ${counts.confirmed}곳 통제 중, ${counts.scheduled}곳 예정`;
  // 목록 위 데이터 기준 시각 (결정 C) — 실시간 돌발이 없거나 30분 넘게 오래면 회색 경고
  const asof = ready && dataAsOf ? dataAsOfKo(dataAsOf, Date.now()) : null;
  return (
    <BottomSheet label={title} stage={stage} onStage={setStage}>
      <div className={styles.pad}>
        <div className={styles.head}>
          <div className={styles.title}>{title}</div>
          <button
            type="button"
            className={styles.load}
            aria-pressed={picking}
            onClick={() => (picking ? setPicking(false) : openList())}
          >
            통제 불러오기
          </button>
        </div>
        <div className={styles.sub}>
          {subtitle}
          {status === "loading" && <span className={styles.loading}> · 불러오는 중</span>}
          {status === "error" && <span className={styles.error}> · {error}</span>}
          {at && at !== t && status !== "loading" && (
            <span className={styles.loading}> · {hhmm(at)} 결과</span>
          )}
        </div>
        {asof && (
          <div className={styles.asof}>
            <span>{asof.text}</span>
            {asof.warning && <span className={styles.asofWarn}>{asof.warning}</span>}
          </div>
        )}
      </div>
      {picking ? (
        <ClosureEvents focusMap onDone={picked} />
      ) : (
        <>
          <ClosureTimeline />
          <TimeSlider />
          <div className={styles.rows}>
            {rows.map((row) => {
              const ev: Pick<ClosureEvent, "reason" | "type" | "summary"> = row.event ?? {
                reason: row.reason,
                summary: null,
              };
              const detail = eventDetailKo(ev);
              const notice = row.event?.notice;
              return (
                <div key={row.key} className={styles.row}>
                  <span className={styles.ico} style={{ background: STATUS_BG[row.status] }}>
                    <span className={styles.dot} style={{ background: STATUS_COLOR[row.status] }} />
                  </span>
                  <div className={styles.rowText}>
                    <b className={styles.rowTitle}>{eventTitleKo(ev)}</b>
                    {detail && <span className={styles.rowDetail}>{detail}</span>}
                    <span className={styles.rowSub}>
                      {row.approx ? "약 " : ""}
                      {windowKo(row.start, row.end)} · 횡단보도 {row.crosswalks}곳
                    </span>
                    {notice && (
                      <button
                        type="button"
                        className={styles.raw}
                        aria-expanded={opened === row.key}
                        onClick={() => setOpened(opened === row.key ? null : row.key)}
                      >
                        공지 원문 보기
                      </button>
                    )}
                    {notice && opened === row.key && (
                      <p className={styles.excerpt}>{notice.excerpt}</p>
                    )}
                  </div>
                  <em className={styles.badge} style={{ color: STATUS_COLOR[row.status] }}>
                    {badge(row, t)}
                  </em>
                </div>
              );
            })}
            {rows.length === 0 && (
              <p className={styles.empty}>
                이 시각에 걸린 통제가 없어요.{" "}
                <button type="button" className={styles.inline} onClick={openList}>
                  통제 불러오기
                </button>
              </p>
            )}
          </div>
        </>
      )}
    </BottomSheet>
  );
}
