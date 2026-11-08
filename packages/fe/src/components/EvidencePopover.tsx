"use client";

import { Fragment, useMemo } from "react";
import {
  AVOIDED_STATUS_KO,
  EVIDENCE_KO,
  STATUS_KO,
  TYPE_KO,
  evidenceTextKo,
  hhmm,
  reasonKo,
  reasonType,
  untilKo,
  whenKo,
} from "../i18n/ko";
import { STATUS_BG, STATUS_COLOR } from "../map/colors";
import { STATUS_SEVERITY } from "../map/layers/closureLayer";
import { useClosures } from "../state/ClosureProvider";
import { useTime } from "../state/TimeProvider";
import type {
  Avoided,
  ClosureType,
  EvidenceKind,
  FeatureCollection,
  RouteResponse,
  Status,
} from "../types/contracts";
import styles from "./EvidencePopover.module.css";

// 통제 근거 (시안 03 구조) — 이 경로가 피한 통제를 사유별로: 해제 시각, "이렇게 판단했어요", 확신도.
// 확신도는 /route 의 avoided 에 없어서 같은 시각 /closures 의 같은 횡단보도 값을 쓴다 (없으면 숨김)
export interface EvidenceRow {
  key: string;
  at: string;
  when: string;
  text: string;
  kind: EvidenceKind;
}

export interface EvidenceGroup {
  reason: string;
  status: Status;
  type: ClosureType | null;
  crosswalks: number;
  /** null = 종료 미정 */
  until: string | null;
  evidence: EvidenceRow[];
  confidence: number | null;
}

const endMs = (iso: string | null) => (iso ? new Date(iso).getTime() : Number.POSITIVE_INFINITY);

export function evidenceGroups(
  avoided: Avoided[],
  closures: FeatureCollection,
  t: string,
): EvidenceGroup[] {
  const conf = new Map<string, number>();
  for (const f of closures.features) {
    const id = f.properties.crosswalk_id;
    if (id) conf.set(id, Math.max(conf.get(id) ?? 0, f.properties.confidence));
  }
  const groups = new Map<string, EvidenceGroup & { ids: Set<string> }>();
  for (const a of avoided) {
    const until = a.until ?? null;
    let g = groups.get(a.reason);
    if (!g) {
      g = {
        reason: a.reason,
        status: a.status,
        type: reasonType(a.reason),
        crosswalks: 0,
        until,
        evidence: [],
        confidence: null,
        ids: new Set(),
      };
      groups.set(a.reason, g);
    } else {
      if (STATUS_SEVERITY[a.status] < STATUS_SEVERITY[g.status]) g.status = a.status;
      if (endMs(until) > endMs(g.until)) g.until = until;
    }
    g.ids.add(a.crosswalk_id);
    const c = conf.get(a.crosswalk_id);
    if (c !== undefined) g.confidence = Math.max(g.confidence ?? 0, c);
    for (const e of a.evidence) {
      const text = evidenceTextKo(e, t);
      const key = `${e.kind}|${e.at}|${text}`;
      if (g.evidence.some((r) => r.key === key)) continue;
      g.evidence.push({ key, at: e.at, when: whenKo(e.at, t), text, kind: e.kind });
    }
  }
  return [...groups.values()]
    .map(({ ids, ...g }) => ({
      ...g,
      crosswalks: ids.size,
      evidence: [...g.evidence].sort((x, y) => endMs(x.at) - endMs(y.at)),
    }))
    .sort(
      (a, b) =>
        STATUS_SEVERITY[a.status] - STATUS_SEVERITY[b.status] || endMs(a.until) - endMs(b.until),
    );
}

export function EvidencePopover({ route }: { route: RouteResponse }) {
  const { closures } = useClosures();
  const { t } = useTime();
  const groups = useMemo(() => evidenceGroups(route.avoided, closures, t), [route, closures, t]);
  return (
    <section className={styles.pop} aria-label="통제 근거">
      {groups.map((g) => (
        <article key={g.reason} className={styles.group}>
          <div className={styles.badges}>
            <span
              className={styles.badge}
              style={{ background: STATUS_BG[g.status], color: STATUS_COLOR[g.status] }}
            >
              {AVOIDED_STATUS_KO[g.status] ?? STATUS_KO[g.status]}
            </span>
            {g.type && <span className={`${styles.badge} ${styles.gray}`}>{TYPE_KO[g.type]}</span>}
          </div>
          <strong className={styles.title}>{reasonKo(g.reason)}</strong>
          <span className={styles.sub}>이 길이 피한 횡단보도 {g.crosswalks}곳</span>
          <div className={styles.big}>
            {g.until ? `~${hhmm(g.until)}` : "종료 미정"}
            <small style={{ color: STATUS_COLOR[g.status] }}>{untilKo(g.until, t)}</small>
          </div>
          <div className={styles.lbl}>이렇게 판단했어요</div>
          <div className={styles.ev}>
            {g.evidence.map((e) => (
              <Fragment key={e.key}>
                <span className={styles.when}>{e.when}</span>
                <span>{e.text}</span>
                <span className={`${styles.badge} ${styles.gray}`}>{EVIDENCE_KO[e.kind]}</span>
              </Fragment>
            ))}
          </div>
          {g.confidence !== null && (
            <>
              <div className={styles.conf}>
                <i
                  style={{
                    width: `${Math.round(g.confidence * 100)}%`,
                    background: STATUS_COLOR[g.status],
                  }}
                />
              </div>
              <div className={styles.confLbl}>
                <span>확신도</span>
                <span>{g.confidence.toFixed(2)}</span>
              </div>
            </>
          )}
        </article>
      ))}
    </section>
  );
}
