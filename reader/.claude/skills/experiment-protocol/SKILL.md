---
name: experiment-protocol
description: notice-ner 🧪 실험 Task(R4.x)의 절차 — 사전 등록, val 실행, 오류 분석, 동결, test 1회 공개, 결과 기록. 학습·추론·평가를 돌리거나, 실험 설정을 바꾸거나, 실험 숫자를 보고할 때 반드시 따른다.
---

# 실험 프로토콜

대회처럼 한다. val은 공개 리더보드, test는 비공개 리더보드. 비공개는 마지막(R4.7)에 한 번 열린다.
지표·분할·부트스트랩 정의는 `docs/experiments.md`. 여기는 절차다.

## 0. 들어가기 전
- `docs/experiments.md` §1(분할)·§3(지표)을 읽는다
- `configs/<exp>.yaml` 초안과 `docs/decisions/ADR-R01-judgement.md`(판정 규칙)를 확인한다
- 비교 기준: 직전 실험의 val 숫자를 `make report-table`로 본다. 기억으로 말하지 않는다

## 1. 사전 등록 (PLAN 아래, 실행 전)
- `docs/experiments.md` §2 형식으로 가설·비교·주지표·기대 범위·판정 규칙·실패 시 할 일·시도 상한
- config의 `hypothesis`·`expected`·`decision_rule` 칸에 같은 내용 → **커밋**. 이 커밋이 실행보다 앞서야 한다
- 태우 `ok` 전엔 학습도 추론도 돌리지 않는다

## 2. 구현 (Red → Green)
- 정확성은 실데이터 테스트로: 정렬 왕복, 출력 schema·오프셋, `gpu` 스모크
- 하이퍼파라미터는 config에서만 읽는다. 코드에 숫자를 박지 않는다
- 모델 코드(`notice_ner.models`)는 `notice_ner.eval`을 import하지 않는다. 학습 중 val 지표는 `notice_ner.metrics`

## 3. val 실행
```
make train EXP=exp00N         # 규칙·API 실험은 할 일 없음
make predict EXP=exp00N SPLIT=val
make eval EXP=exp00N SPLIT=val
```
- 실행 전 `git status`가 깨끗해야 한다 (run.json에 커밋이 남는다)
- 학습은 포그라운드. 예상 시간을 PLAN에 적고, 두 배를 넘기면 멈추고 보고
- 파인튜닝 실험은 seed 3개 (exp005는 VRAM·시간상 1개 — PLAN에 명시)
- API 실험: 실행 전 예상 비용 = 문장 수 × 평균 토큰 × config 가격. 상한을 넘으면 멈춤

## 4. 오류 분석 (val만)
- `errors_val.jsonl`을 유형별로 센다: 경계 · 태그 혼동 · 놓침 · 헛것 · 정규형 틀림
- 유형별 실제 val 사례 3개씩 RESULT에
- 라벨이 틀린 것 같으면 `labeling/issues.md`. 정답을 고치지 않는다. 고쳐진 라벨로 다시 재려면 data_version을 올린다

## 5. 설정을 바꾸고 싶을 때
- val을 보고 바꾸는 건 허용 (그게 val의 용도다)
- 대신 시도마다 config를 커밋하고, RESULT에 "몇 번째 시도"를 쓴다 — 시도 수도 결과다
- 시도 상한(사전 등록에 적은 수, 기본 5)을 넘으면 멈추고 태우와 상의
- 가설 자체를 바꾸면 새 exp_id

## 6. RESULT (walkthrough)
- `make report-table` 출력을 그대로 붙인다
- 사전 등록 대비 맞음/틀림과 이유
- 다음 실험에 넘기는 것

## 7. 동결과 test (PC-4, R4.7에서만)
- 태우가 직접 `make freeze EXP=…` → `experiments/<id>/FROZEN.json` (config sha·commit)
- R4.7 GO 뒤 Claude가 `make test-run EXP=…` → `predictions_test*`, `metrics_test*.json`, results.csv
- 동결 뒤 config를 바꾸면 새 exp_id
- test 오류 열람은 태우가 settings.json 잠금을 푼 뒤에만. 그 분석은 보고서에 "[사후]"

## 8. 숫자를 말하는 규칙
- 숫자는 `metrics_*.json`·`results.csv`에서만. 대화에 쓸 때 출처 파일을 같이 적는다
- 소수 셋째 자리 + CI: `0.812 [0.771, 0.848]`
- "좋아졌다"는 paired Δ의 CI가 0을 넘을 때만. 아니면 "차이 불분명"
- val 숫자는 반드시 "val"이라고 붙인다. test처럼 말하지 않는다
- LLM 비용은 usage 토큰 × config 가격(출처 URL·확인일)

## 하지 않는 것
- 사전 등록 없이 실행
- test·sealed 열기 (R4.7 전, 그리고 R4.7에서도 `make test-run` 말고는)
- 실패한 시도 지우기 (results.csv에 남는다)
- 결과에 맞춰 가설 고쳐 쓰기
- 서로 다른 data_version의 숫자를 한 표에서 비교
