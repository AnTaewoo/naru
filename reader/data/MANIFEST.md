# MANIFEST — 실데이터 출처 대장

형식은 `.claude/skills/real-data-testing/SKILL.md` §2. `tests/test_manifest.py`(R1.1에서 생긴다)가 파일 존재·sha256·행 수를 검사한다.
값은 받은 뒤 파일을 열어 확인한 것만 적는다. 계획 항목은 받으면 아래 "항목"으로 옮겨 채운다.
자라는 캐시(kakao, llm recorded)는 "이미 있는 파일은 바뀌지 않는다"로 검사한다 — 방식은 해당 Task에서 정한다.

## 계획
| 이름 | 위치 | Task |
|---|---|---|
| recorded_api_probe | `data/recorded/{naver,kakao,topis,anthropic}/` | R0.3 |
| naver_news_index | `data/raw/naver/<run_ts>/` | R1.1 |
| news_sentences | `data/raw/news/<run_ts>.jsonl` (+ `.skipped.jsonl`, `.rejected_sample.jsonl`) | R1.2 |
| topis_notices | `data/recorded/topis/`, `data/raw/official/topis_*.jsonl` | R1.3a |
| smpa_daily | `data/raw/smpa/<YYYYMMDD>.*`, `data/raw/official/smpa_*.jsonl` | R1.3b |
| seoul_press | `data/raw/official/seoul_press_*.jsonl` | R1.3c (선택) |
| klue_ner | `data/raw/klue_ner/` | R1.4 |
| seoul_spatial | `data/raw/seoul_spatial/` | R2.1 |
| road_names | `data/raw/roads/` | R2.2 |
| kakao_cache | `data/recorded/kakao/` | R2.3 |
| llm_anthropic | `data/recorded/llm/anthropic/` | R4.5 |
| labels | `data/labeled/` (Label Studio export → `make export`) | R3.4 |

## 항목
(아직 없음)
