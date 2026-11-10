"use client";

import { dataAsOfKo } from "../i18n/ko";
import { useClosures } from "../state/ClosureProvider";

// 'use client' 경계 3/3 (T7.13) — 서버 페이지 /licenses 아래 "데이터 기준 시각". layout 의 ClosureProvider 가 받은
// 사건 응답 data_as_of 를 예전 시트 문구 그대로 (태우 11/10 "이미 구현했었던 거 다시 띄우면")
export function DataAsOf({ className }: { className?: string }) {
  const { dataAsOf, eventsError } = useClosures();
  if (!dataAsOf) {
    return (
      <p className={className}>{eventsError ? "기준 시각을 받지 못했어요" : "불러오는 중…"}</p>
    );
  }
  const { text, warning } = dataAsOfKo(dataAsOf, Date.now());
  return (
    <>
      <p className={className}>{text}</p>
      {warning && <p className={className}>{warning}</p>}
    </>
  );
}
