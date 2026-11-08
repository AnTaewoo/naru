"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import { useRoute } from "../state/RouteProvider";
import type { Status } from "../types/contracts";
import { ClosureSheet } from "./ClosureSheet";
import { CHIP_STATUSES, LayerChips } from "./LayerChips";
import styles from "./NaruApp.module.css";
import { RouteCard } from "./RouteCard";
import { RoutePanel } from "./RoutePanel";

// 'use client' 경계 2/2 — 화면 루트. maplibre 는 window 가 필요해 ssr: false 로 여기서만 부른다 (§5.3)
const MapView = dynamic(() => import("../map/MapView"), {
  ssr: false,
  loading: () => <div className={styles.mapLoading}>지도 불러오는 중…</div>,
});

// 홈(시안 01): 길찾기 바 + 칩 + 오늘 통제 시트. 길찾기(시안 02): 출발·도착 패널 + 경로 카드 시트
export function NaruApp() {
  const { active } = useRoute();
  const [visible, setVisible] = useState<readonly Status[]>(CHIP_STATUSES);
  const toggle = useCallback(
    (s: Status) => setVisible((v) => (v.includes(s) ? v.filter((x) => x !== s) : [...v, s])),
    [],
  );
  return (
    <main className={styles.app} data-mode={active ? "route" : "home"}>
      <h1 className={styles.srOnly}>나루</h1>
      <MapView visible={visible} />
      <RoutePanel />
      {!active && <LayerChips visible={visible} onToggle={toggle} />}
      {active ? <RouteCard /> : <ClosureSheet />}
    </main>
  );
}
