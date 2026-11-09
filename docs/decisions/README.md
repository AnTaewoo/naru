# ADR (Architecture Decision Record)

설계를 바꾸려면 여기 먼저. 형식: `ADR-NNN-<slug>.md`, 섹션 = 맥락 / 결정 / 근거 / 결과 / 상태(제안|승인|폐기). 승인은 태우.
Notion "결정 기록" DB와 동기화한다 (Notion이 팀용, 여기는 코드와 같이 움직이는 사본).
- ADR-007 공지 파서는 Claude API (승인)
- ADR-008 공지 파서 v2 출력(impact·toward·approx)을 BE가 받는 규칙 + INTERFACE v0.6 (승인, 2026-11-07)
- ADR-009 경로 레그가 선의 어디인지 — `legs[].coord_range` + INTERFACE v0.7 (승인, 2026-11-08)
- ADR-010 통제 사건 목록 — `GET /closures/events` + INTERFACE v0.8 (승인, 2026-11-08)
- ADR-011 실서버 운영 결정 묶음 — 라우터 비용(예정 +300초)·그래프 밖·지오코딩·데이터 신선도·운영 워커 live·외부 수집 (승인, 2026-11-08)
- ADR-012 통제 목록 — 파서 요약(구조화 칸)·공지 원문·데이터 기준 시각을 사건까지 + INTERFACE v0.12 (승인, 2026-11-08)
- ADR-013 버스 신호는 확신도 보정(이진 규칙 대체, 계산은 BE, base_confidence) · ADR-011 E 범위는 웹 페이지 수집만 (승인 2026-11-08 → **보류** 2026-11-09: 1개 차로 행진 시간 안에 버스가 구간을 124회 경로대로 지나감 — 버스는 전면 통제·마라톤만 기록, '통제 중' 근거는 시간표·TOPIS 돌발. E 범위(H)는 유효)
- ADR-014 실시간 통제 지도(사건 id·통제 구역 area·centroid, 사건 API 시간 창·ETag, route avoid)·TOPIS 통제지도 예정 통제·PWA 알림(구독·관심 지역·발송 표, pywebpush) (초안, 2026-11-09)
