"use client";

import { useEffect, useState } from "react";
import { staleWarningKo } from "../i18n/ko";
import { useClosures } from "../state/ClosureProvider";

/** 다시 볼 간격 — TOPIS 가 멈추면 사건 응답이 그대로(304)라 시트가 다시 그려지지 않는다 */
const RECHECK_MS = 60_000;

// 통제 정보 멈춤 경고 (T7.13, 태우 11/10) — TOPIS 돌발 배치를 30분 넘게 못 받았을 때만 한 줄, 평소엔 아무것도 없다
export function StaleWarning({ className }: { className?: string }) {
  const { dataAsOf } = useClosures();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), RECHECK_MS);
    return () => clearInterval(timer);
  }, []);
  const warning = staleWarningKo(dataAsOf, now);
  return warning ? (
    <p role="status" className={className}>
      {warning}
    </p>
  ) : null;
}
