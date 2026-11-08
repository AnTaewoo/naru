"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import type { Status } from "../types/contracts";
import { ClosureSheet } from "./ClosureSheet";
import { CHIP_STATUSES, LayerChips } from "./LayerChips";
import styles from "./NaruApp.module.css";

// 'use client' 경계 2/2 — 화면 루트. maplibre 는 window 가 필요해 ssr: false 로 여기서만 부른다 (§5.3)
const MapView = dynamic(() => import("../map/MapView"), {
  ssr: false,
  loading: () => <div className={styles.mapLoading}>지도 불러오는 중…</div>,
});

export function NaruApp() {
  const [visible, setVisible] = useState<readonly Status[]>(CHIP_STATUSES);
  const toggle = useCallback(
    (s: Status) => setVisible((v) => (v.includes(s) ? v.filter((x) => x !== s) : [...v, s])),
    [],
  );
  return (
    <main className={styles.app}>
      <h1 className={styles.srOnly}>나루</h1>
      <MapView visible={visible} />
      <LayerChips visible={visible} onToggle={toggle} />
      <ClosureSheet />
    </main>
  );
}
