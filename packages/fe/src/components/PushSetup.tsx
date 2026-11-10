"use client";

import { PUSH_KO } from "../i18n/ko";
import { usePush } from "../push/usePush";
import type { PushState } from "../push/support";
import styles from "./PushSetup.module.css";

// 알림 켜기 (T7.7, ADR-014 C) — 시트 맨 아래 한 칸. 권한은 버튼으로만 묻는다. iPhone 브라우저 탭은 홈 화면 안내.
// 관심 지역 등록·구독은 T7.8~T7.10 — 그때까지 허용돼도 알림은 오지 않는다고 적는다
export function PushSetupView({ state, onEnable }: { state: PushState; onEnable: () => void }) {
  if (state === "unknown") return null;
  return (
    <section className={styles.box} aria-label={PUSH_KO.title}>
      <h3 className={styles.head}>{PUSH_KO.title}</h3>
      {state === "default" && (
        <>
          <p className={styles.sub}>{PUSH_KO.why}</p>
          <button type="button" className={styles.enable} onClick={onEnable}>
            {PUSH_KO.enable}
          </button>
        </>
      )}
      {state === "granted" && (
        <p className={styles.sub} role="status">
          {PUSH_KO.granted}
        </p>
      )}
      {state === "denied" && <p className={styles.sub}>{PUSH_KO.denied}</p>}
      {state === "ios_install" && <p className={styles.sub}>{PUSH_KO.iosInstall}</p>}
      {state === "unsupported" && <p className={styles.sub}>{PUSH_KO.unsupported}</p>}
    </section>
  );
}

export function PushSetup() {
  const { state, enable } = usePush();
  return <PushSetupView state={state} onEnable={enable} />;
}
