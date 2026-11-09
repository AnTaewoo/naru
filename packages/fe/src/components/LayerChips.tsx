"use client";

import { CHIP_KO } from "../i18n/ko";
import { COLORS } from "../map/colors";
import { CHIP_KINDS, chipCounts, type ChipKind } from "../map/eventKinds";
import { useClosures } from "../state/ClosureProvider";
import styles from "./LayerChips.module.css";

// 목업 01_home 상단 칩: "통제 중 N" — 지금 서울 사건 수(해제·확신도 0.7 미만 빼고) + 지도 필터 (T7.4)
const CHIP_COLOR: Record<ChipKind, string> = {
  confirmed: COLORS.stop,
  scheduled: COLORS.slow,
  zone: COLORS.zone,
};

export function LayerChips({
  visible,
  onToggle,
}: {
  visible: readonly ChipKind[];
  onToggle: (k: ChipKind) => void;
}) {
  const { events, eventsAt } = useClosures();
  const counts = chipCounts(events ?? [], eventsAt ? Date.parse(eventsAt) : 0);
  return (
    <div className={styles.chips} role="group" aria-label="지도 레이어">
      {CHIP_KINDS.map((k) => {
        const on = visible.includes(k);
        return (
          <button
            key={k}
            type="button"
            className={on ? `${styles.chip} ${styles.on}` : styles.chip}
            aria-pressed={on}
            onClick={() => onToggle(k)}
          >
            <i className={styles.dot} style={{ background: CHIP_COLOR[k] }} />
            {CHIP_KO[k]}
            {events !== null && ` ${counts[k]}`}
          </button>
        );
      })}
    </div>
  );
}
