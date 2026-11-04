# 공지 파싱 실측 보고서 v0 — YYYY-MM-DD

> 숫자는 전부 `make report-table` 출력이나 `experiments/*/metrics_*.json`에서 온다. 손으로 옮겨 적지 않는다.
> 사후 분석(test를 본 뒤 한 것)은 문단 앞에 **[사후]** 를 붙인다.

## 0. 결론 (3줄)
- 판정 (ADR-R01 문장 그대로): 
- 근거: test Norm-F1 paired Δ = … [95% CI …]
- Naru에 주는 결정: 

## 1. 질문과 판정 규칙
- 사전 등록 그대로 인용 (ADR-R01 승인본 커밋 해시)
- 비교쌍: 로컬 대표(val로 고름) vs API 대표(val로 고름)

## 2. 데이터
- 출처별·기간별 문장 수 (`data/interim/pool_v1/STATS.md`, `data/splits/v1/SPLIT.md`)
- 라벨: 주석자 수, 문장 수, drop 수, 가이드 버전
- IAA (exp000_iaa): Span-F1 …, Norm-F1 …
- 정규화기 상한 (exp000_oracle_norm)

## 3. 결과 표
(`make report-table` 출력 붙여넣기 — val과 test를 따로)

## 4. 로컬 vs API
- 주판정: test paired Δ + CI → 판정
- test_ood에서 같은가, 뒤집히나
- Sonnet(참고 상한)과의 거리

## 5. 어디서 차이가 나나
- 태그별 F1
- 슬라이스: novel / official vs news / test_ood
- 학습량 곡선 (val): 라벨을 더 하면 얼마나 오를 것 같은가

## 6. 오류 분석
- val: 유형별 수와 사례 3개씩
- test: [사후] R4.7 뒤 잠금 해제 후에만

## 7. 비용·지연
| 시스템 | 1,000문장당 | p50 | p95 | 하드웨어 |
|---|---|---|---|---|

## 8. 측정하지 않은 것 (필수)
- 관계: 구간 FROM→TO, 시간↔장소, 행진 순서 — API가 앞설 것으로 예상되는 영역
- SCOPE(차로·방향), 지역명(ZONE), ROAD 구간의 E2E, 현장 정확도
- 그 밖에 이번에 빠진 것

## 9. Naru에 주는 결정
- `reports/ADR-007-llm.draft.md` 요약, Naru ROADMAP P5에서 바뀌는 Task

## 10. 재현
- 커밋, data_version, 실행 명령, GPU·드라이버, test 재실행 기록(`test_log.jsonl`)
