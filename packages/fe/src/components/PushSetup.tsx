"use client";

import Link from "next/link";
import { PUSH_KO, watchAreaKo } from "../i18n/ko";
import type { PushStore } from "../push/store";
import { usePush } from "../push/usePush";
import styles from "./PushSetup.module.css";

// 통제 알림 칸 (T7.7 → T7.10, ADR-014 C) — 시트 맨 아래. 권한은 버튼으로만. 구독되면 관심 지역 목록(장소 카드의
// ☆로 더한 곳·마지막 위치)·빼기·알림 끄기·개인정보 한 줄. iPhone 브라우저 탭은 홈 화면 안내
export interface PushSetupProps {
  store: PushStore;
  onEnable: () => void;
  onDisable: () => void;
  onUnwatch: (id: number) => void;
}

export function PushSetupView({ store, onEnable, onDisable, onUnwatch }: PushSetupProps) {
  const { support, endpoint, areas, labels, busy, error } = store;
  if (support === "unknown") return null;
  const subscribed = endpoint !== null;
  return (
    <section className={styles.box} aria-label={PUSH_KO.title}>
      <h3 className={styles.head}>
        {PUSH_KO.title}
        {subscribed && <span className={styles.on}>{PUSH_KO.on}</span>}
      </h3>
      {subscribed ? (
        <>
          <h4 className={styles.sub2}>{PUSH_KO.areasHead}</h4>
          {areas.length === 0 ? (
            <p className={styles.sub}>{PUSH_KO.noAreas}</p>
          ) : (
            <ul className={styles.list} aria-label={PUSH_KO.areasHead}>
              {areas.map((a) => (
                <li key={a.id} className={styles.item}>
                  <span>
                    {watchAreaKo(labels[String(a.id)] ?? null, a.radius_m, a.kind === "last_seen")}
                  </span>
                  <button
                    type="button"
                    className={styles.remove}
                    aria-label={`${PUSH_KO.remove}: ${labels[String(a.id)] ?? PUSH_KO.lastSeen}`}
                    onClick={() => onUnwatch(a.id)}
                  >
                    {PUSH_KO.remove}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className={styles.off} disabled={busy} onClick={onDisable}>
            {PUSH_KO.off}
          </button>
        </>
      ) : (
        <>
          {(support === "default" || support === "granted") && (
            <>
              <p className={styles.sub}>{support === "granted" ? PUSH_KO.granted : PUSH_KO.why}</p>
              <button type="button" className={styles.enable} disabled={busy} onClick={onEnable}>
                {busy ? PUSH_KO.working : PUSH_KO.enable}
              </button>
            </>
          )}
          {support === "denied" && <p className={styles.sub}>{PUSH_KO.denied}</p>}
          {support === "ios_install" && <p className={styles.sub}>{PUSH_KO.iosInstall}</p>}
          {support === "unsupported" && <p className={styles.sub}>{PUSH_KO.unsupported}</p>}
        </>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error === "limit" ? "저장 관심 지역은 10곳까지예요" : PUSH_KO.failed}
        </p>
      )}
      {(subscribed || support === "default" || support === "granted") && (
        <p className={styles.privacy}>
          {PUSH_KO.privacy} <Link href="/licenses#push">보기</Link>
        </p>
      )}
    </section>
  );
}

export function PushSetup() {
  const push = usePush();
  return (
    <PushSetupView
      store={push}
      onEnable={push.enable}
      onDisable={push.disable}
      onUnwatch={push.unwatch}
    />
  );
}
