"use client";

import { useNaruApi } from "../state/ApiProvider";
import styles from "./NaruApp.module.css";

// 'use client' 경계 2/2 — 화면 루트. MapView 는 T5.1 에서 next/dynamic(ssr: false) 로 여기서 부른다.
export function NaruApp() {
  const api = useNaruApi();
  return (
    <main className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.title}>나루</h1>
        <p className={styles.subtitle}>마라톤·집회로 막힌 횡단보도, 지하도·육교로 건너는 길</p>
      </header>
      <section className={styles.panel} aria-label="상태">
        <p className={styles.meta}>BE 연결: 같은 오리진 {api.baseUrl} (Next.js rewrites → Flask)</p>
      </section>
    </main>
  );
}
