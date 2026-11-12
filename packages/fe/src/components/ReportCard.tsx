"use client";

import { REPORT_FAILURE_KO, REPORT_KO, reportSentKo, reportWhereKo } from "../i18n/ko";
import type { ReportPhase, ReportValue } from "../state/report";
import { useRoute, useRouteDispatch } from "../state/RouteProvider";
import styles from "./ReportCard.module.css";

// 통제 제보 카드 (T7.15, INTERFACE §8) — 지도 "제보" 버튼 → 지금 위치 → 가장 가까운 횡단보도(지도 핀) →
// "이 횡단보도가 맞나요?" [막혔어요] [열렸어요]. 기록만 — 길찾기에는 아직 안 쓴다(카드 아래 한 줄).
// ?mode=field 면 "현장 검증" 배지(출처 field, 11/14 비교 스크립트가 쓴다)
const HEAD: Record<ReportPhase, string> = {
  locating: REPORT_KO.locating,
  finding: REPORT_KO.finding,
  ready: REPORT_KO.title,
  sending: REPORT_KO.title,
  sent: REPORT_KO.button,
  error: REPORT_KO.button,
};

export function ReportCard() {
  const { report } = useRoute();
  const dispatch = useRouteDispatch();
  if (!report) return null;
  const { phase, crosswalk, failure } = report;
  const send = (value: ReportValue) => dispatch({ type: "report", event: { type: "send", value } });
  const choosing = phase === "ready" || phase === "sending";
  return (
    <article className={styles.card} aria-label={REPORT_KO.button}>
      <div className={styles.top}>
        <h2 className={styles.head}>{HEAD[phase]}</h2>
        {report.field && <span className={styles.field}>{REPORT_KO.field}</span>}
        <button
          type="button"
          className={styles.close}
          aria-label={REPORT_KO.close}
          onClick={() => dispatch({ type: "report", event: { type: "close" } })}
        >
          ×
        </button>
      </div>
      {crosswalk && (
        <>
          <p className={styles.name}>
            <b>{crosswalk.name}</b> {crosswalk.district}
          </p>
          <p className={styles.where}>{reportWhereKo(crosswalk.distanceM, report.accuracyM)}</p>
        </>
      )}
      {choosing && (
        <div className={styles.actions}>
          {(["blocked", "open"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={value === "blocked" ? styles.blocked : styles.open}
              disabled={phase === "sending"}
              onClick={() => send(value)}
            >
              {REPORT_KO[value]}
            </button>
          ))}
        </div>
      )}
      {phase === "sending" && <p className={styles.note}>{REPORT_KO.sending}</p>}
      {phase === "sent" && report.sent && (
        <p className={styles.done} role="status">
          {reportSentKo(report.sent)}
        </p>
      )}
      {phase === "error" && failure && (
        <>
          <p className={styles.error} role="alert">
            {REPORT_FAILURE_KO[failure]}
          </p>
          {failure !== "too_many" && (
            <button
              type="button"
              className={styles.retry}
              onClick={() => dispatch({ type: "report", event: { type: "retry" } })}
            >
              {REPORT_KO.retry}
            </button>
          )}
        </>
      )}
      <p className={styles.note}>{REPORT_KO.note}</p>
    </article>
  );
}
