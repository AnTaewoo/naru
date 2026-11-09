"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import { CHIP_KINDS, type ChipKind } from "../map/eventKinds";
import { useRoute } from "../state/RouteProvider";
import { LayerChips } from "./LayerChips";
import { LiveSheet } from "./LiveSheet";
import styles from "./NaruApp.module.css";
import { RouteCard } from "./RouteCard";
import { RoutePanel } from "./RoutePanel";

// 'use client' 경계 2/2 — 화면 루트. maplibre 는 window 가 필요해 ssr: false 로 여기서만 부른다 (§5.3)
const MapView = dynamic(() => import("../map/MapView"), {
  ssr: false,
  loading: () => <div className={styles.mapLoading}>지도 불러오는 중…</div>,
});

// 홈(시안 01): 길찾기 바 + 칩 + 지금 서울 통제 시트(T7.5). 길찾기(시안 02): 출발·도착 패널 + 경로 카드 시트
export function NaruApp() {
  const { active } = useRoute();
  // 칩 = 필터 (T7.4) — 사건 구역·클러스터·횡단보도 점에 같이
  const [visible, setVisible] = useState<readonly ChipKind[]>(CHIP_KINDS);
  const toggle = useCallback(
    (k: ChipKind) => setVisible((v) => (v.includes(k) ? v.filter((x) => x !== k) : [...v, k])),
    [],
  );
  return (
    <main className={styles.app} data-mode={active ? "route" : "home"}>
      <h1 className={styles.srOnly}>나루</h1>
      <MapView visible={visible} />
      <RoutePanel />
      {!active && <LayerChips visible={visible} onToggle={toggle} />}
      {active ? <RouteCard /> : <LiveSheet />}
    </main>
  );
}
