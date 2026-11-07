# ADR-005 baseline 경로는 자체 그래프, TMAP은 QA 샘플링만
- 상태: 승인 (2026-11-03)
- 맥락: baseline을 TMAP 보행자 API로 받으면 사용자 호출당 과금(무료 1,000/일, 초과 ₩11/건). 1,000 DAU면 월 ≈ ₩100만.
- 결정: BaselineRouter = 같은 PedGraph에서 closures 미적용. TMAP은 `scripts/qa_tmap_compare.py`로 20쌍 비교(1회 live → recorded)에만.
- 근거: 사용자 요청 경로에 외부 호출 0. 비교 공신력은 QA 리포트로 확보.
- 결과: ARCHITECTURE v0.2 BaselineRouter, ROADMAP T3.2·T3.4.
