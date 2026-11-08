"use client";

import { useRef, useState, type PointerEvent, type ReactNode } from "react";
import styles from "./BottomSheet.module.css";

// 하단 시트 (T5.6) — 손잡이를 끌어 접힘(96px) / 절반 / 전체 세 단계. 놓으면 가까운 단계, 손잡이 탭은
// 접힘↔절반(전체에서 탭하면 접힘). 높이는 부모(.app) 기준이고 단계는 부모 컴포넌트가 들고 있다
export type SheetStage = "collapsed" | "half" | "full";

export const SHEET_COLLAPSED_PX = 96;
const RATIO = { half: 0.5, full: 0.88 } as const;
const STAGES: readonly SheetStage[] = ["collapsed", "half", "full"];
/** 이보다 덜 움직였으면 끌기가 아니라 탭 */
const TAP_SLOP_PX = 6;

export function stageHeight(stage: SheetStage, containerH: number): number {
  return stage === "collapsed" ? SHEET_COLLAPSED_PX : Math.round(containerH * RATIO[stage]);
}

export function nearestStage(heightPx: number, containerH: number): SheetStage {
  let best: SheetStage = "collapsed";
  for (const s of STAGES) {
    const d = Math.abs(stageHeight(s, containerH) - heightPx);
    if (d < Math.abs(stageHeight(best, containerH) - heightPx)) best = s;
  }
  return best;
}

interface Drag {
  pointerId: number;
  y0: number;
  h0: number;
  containerH: number;
  moved: boolean;
}

export function BottomSheet({
  label,
  stage,
  onStage,
  children,
}: {
  label: string;
  stage: SheetStage;
  onStage: (s: SheetStage) => void;
  children: ReactNode;
}) {
  const sheet = useRef<HTMLElement | null>(null);
  const drag = useRef<Drag | null>(null);
  const draggedLast = useRef(false);
  const [dragH, setDragH] = useState<number | null>(null);

  const onPointerDown = (e: PointerEvent<HTMLButtonElement>) => {
    const el = sheet.current;
    if (!el) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = {
      pointerId: e.pointerId,
      y0: e.clientY,
      h0: el.getBoundingClientRect().height,
      containerH: el.parentElement?.clientHeight ?? window.innerHeight,
      moved: false,
    };
  };
  const onPointerMove = (e: PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const dy = e.clientY - d.y0;
    if (!d.moved && Math.abs(dy) < TAP_SLOP_PX) return;
    d.moved = true;
    const max = stageHeight("full", d.containerH);
    setDragH(Math.min(Math.max(d.h0 - dy, SHEET_COLLAPSED_PX), max));
  };
  const onPointerEnd = (e: PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    drag.current = null;
    draggedLast.current = d.moved;
    if (d.moved) {
      const h = Math.min(Math.max(d.h0 - (e.clientY - d.y0), SHEET_COLLAPSED_PX), d.containerH);
      onStage(nearestStage(h, d.containerH));
    }
    setDragH(null);
  };
  const onClick = () => {
    if (draggedLast.current) {
      draggedLast.current = false; // 끌고 난 뒤 따라오는 click 은 탭이 아니다
      return;
    }
    onStage(stage === "collapsed" ? "half" : "collapsed");
  };

  return (
    <section
      ref={sheet}
      className={`${styles.sheet} ${styles[stage] ?? ""} ${dragH !== null ? styles.dragging : ""}`}
      style={dragH !== null ? { height: dragH } : undefined}
      aria-label={label}
      data-stage={stage}
    >
      <button
        type="button"
        className={styles.grip}
        aria-label="시트 높이"
        aria-expanded={stage !== "collapsed"}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onClick={onClick}
      >
        <span className={styles.bar} />
      </button>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
