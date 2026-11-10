// "예시로 보기" (T7.11 → T7.14, 태우 11/10) — 데모 날짜·시각, 지도를 맞출 통제 구역, 열 사건 카드. 순수 데이터.
// bbox·사건 id 는 사건 v2 기록(scripts/record_live_events.py)을 열어 옮긴 값이다(운영 11/10 GET 에도 같은 id).
// 라벨은 i18n/ko.ts EXAMPLE_KO
import type { Bounds } from "./eventKinds";

export type ExampleKey = "marathon" | "rally" | "march";

export interface Example {
  key: ExampleKey;
  /** 이동할 기준 시각 (KST) */
  t: string;
  /** 지도를 맞출 통제 구역 [minLng, minLat, maxLng, maxLat] */
  bbox: Bounds;
  /** 열 사건 카드 (T7.14) — 없으면(다른 데이터) 지도만 맞춘다 */
  event: string;
}

export const EXAMPLES: readonly Example[] = [
  {
    key: "marathon",
    t: "2026-03-15T07:45:00+09:00",
    // closure_events_live_0315_0745.json — 1구간 adaea2f4cc02 ∪ 출발지 광화문 광장 3d608690c438
    bbox: [126.975691, 37.5607671, 126.9772498, 37.572614],
    event: "adaea2f4cc02", // 1구간 세종대로 사거리~숭례문 오거리 — 07:45 통제 중
  },
  {
    key: "rally",
    t: "2026-11-07T15:00:00+09:00",
    // closure_events_live_1107_1530.json — 경찰청 r04 시의회~숭례문R → 광화문·고용노동청 2e930ec6deeb
    bbox: [126.975691, 37.5605144, 126.9875484, 37.5749426],
    event: "2e930ec6deeb",
  },
  {
    key: "march",
    t: "2026-11-09T12:00:00+09:00",
    // closure_events_live_1109_1330.json — TOPIS 통제지도 1109233 국회의사당앞 → 효자동삼거리 ccaa9980c6ac
    bbox: [126.9174948, 37.5293213, 126.9774352, 37.5830171],
    event: "ccaa9980c6ac",
  },
];
