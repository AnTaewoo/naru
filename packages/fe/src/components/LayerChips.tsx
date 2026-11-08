"use client";

import { STATUS_COLOR } from "../map/colors";
import { countByStatus } from "../map/layers/closureLayer";
import { useClosures } from "../state/ClosureProvider";
import type { Status } from "../types/contracts";
import styles from "./LayerChips.module.css";

// 목업 01_home 상단 칩: "통제 중 N" 처럼 상태별 개수 + 지도 필터 토글
export const CHIP_STATUSES: readonly Status[] = ["confirmed", "scheduled", "zone_scheduled"];
const CHIP_LABEL: Record<Status, string> = {
  confirmed: "통제 중",
  scheduled: "예정",
  zone_scheduled: "예정 구역",
  released: "해제",
};

export function LayerChips({
  visible,
  onToggle,
}: {
  visible: readonly Status[];
  onToggle: (s: Status) => void;
}) {
  const { closures } = useClosures();
  const counts = countByStatus(closures);
  return (
    <div className={styles.chips} role="group" aria-label="지도 레이어">
      {CHIP_STATUSES.map((s) => {
        const on = visible.includes(s);
        return (
          <button
            key={s}
            type="button"
            className={on ? `${styles.chip} ${styles.on}` : styles.chip}
            aria-pressed={on}
            onClick={() => onToggle(s)}
          >
            <i className={styles.dot} style={{ background: STATUS_COLOR[s] }} />
            {CHIP_LABEL[s]} {counts[s]}
          </button>
        );
      })}
    </div>
  );
}
