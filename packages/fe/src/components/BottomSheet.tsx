"use client";

import { useRef, useState, type PointerEvent, type ReactNode } from "react";
import styles from "./BottomSheet.module.css";

// 하단 시트 (T5.6) — 손잡이를 끌어 접힘(96px) / 절반 / 전체 세 단계. 놓으면 가까운 단계, 손잡이 탭은
// 접힘↔절반(전체에서 탭하면 접힘). 높이는 부모(.app) 기준이고 단계는 부모 컴포넌트가 들고 있다.
// 전체는 위에 떠 있는 UI(길찾기 바·칩 / 출발·도착 패널) 아래까지 — 부모의 CSS 변수 --sheet-top.
// 그래야 전체에서도 손잡이가 패널에 가리지 않아 다시 접을 수 있다
export type SheetStage = "collapsed" | "half" | "full";

export const SHEET_COLLAPSED_PX = 96;
const RATIO = { half: 0.5, full: 0.88 } as const;
const STAGES: readonly SheetStage[] = ["collapsed", "half", "full"];
/** 이보다 덜 움직였으면 끌기가 아니라 탭 */
const TAP_SLOP_PX = 6;

/** topInset = 위에 떠 있는 UI 높이(px). 없으면 전체는 88% */
export function stageHeight(stage: SheetStage, containerH: number, topInset?: number): number {
  if (stage === "collapsed") return SHEET_COLLAPSED_PX;
  if (stage === "full" && topInset !== undefined) return Math.round(containerH - topInset);
  return Math.round(containerH * RATIO[stage]);
}

export function nearestStage(heightPx: number, containerH: number, topInset?: number): SheetStage {
  let best: SheetStage = "collapsed";
  for (const s of STAGES) {
    const d = Math.abs(stageHeight(s, containerH, topInset) - heightPx);
    if (d < Math.abs(stageHeight(best, containerH, topInset) - heightPx)) best = s;
  }
  return best;
}

/** 부모의 --sheet-top (px). 없으면 undefined */
function topInsetOf(el: HTMLElement): number | undefined {
  const parent = el.parentElement;
  if (!parent) return undefined;
  const v = parseFloat(getComputedStyle(parent).getPropertyValue("--sheet-top"));
  return Number.isFinite(v) ? v : undefined;
}

interface Drag {
  pointerId: number;
  y0: number;
  h0: number;
  containerH: number;
  topInset: number | undefined;
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
      topInset: topInsetOf(el),
      moved: false,
    };
  };
  const onPointerMove = (e: PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const dy = e.clientY - d.y0;
    if (!d.moved && Math.abs(dy) < TAP_SLOP_PX) return;
    d.moved = true;
    const max = stageHeight("full", d.containerH, d.topInset);
    setDragH(Math.min(Math.max(d.h0 - dy, SHEET_COLLAPSED_PX), max));
  };
  const onPointerEnd = (e: PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    drag.current = null;
    draggedLast.current = d.moved;
    if (d.moved) {
      const h = Math.min(Math.max(d.h0 - (e.clientY - d.y0), SHEET_COLLAPSED_PX), d.containerH);
      onStage(nearestStage(h, d.containerH, d.topInset));
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
