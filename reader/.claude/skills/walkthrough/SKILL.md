---
name: walkthrough
description: Task별 PLAN · 사전 등록 · READ-ALONG · RESULT · QUIZ 문서(docs/walkthrough/<task-id>.md) 작성 규칙. Task 시작 전과 끝에 쓴다. 태우가 코드·데이터·실험을 이해하고 제어하기 위한 문서다.
---

# Walkthrough

파일: `docs/walkthrough/<task-id>.md`. Task 하나에 하나. 섹션을 순서대로 채운다.

## PLAN (코드 수정 전, 15줄 이내)
```
# R1.5 후보 풀·기간 분리

## PLAN
- 종류·패키지: 🧩 collect
- 목표: 뉴스·공식 문장을 합쳐 근접 중복을 지우고 published_at으로 train/val/test/test_ood에 나눈다
- 왜: 같은 보도자료가 매체 수십 곳에 실린다. 지우지 않으면 train과 test에 같은 문장이 들어가 점수가 부푼다
- 파일: src/notice_ner/collect/pool.py (신규), src/notice_ner/cli/build_pool.py (신규), tests/test_pool.py (신규)
- 실데이터: data/raw/news/<run_ts>.jsonl, data/raw/official/*.jsonl (MANIFEST: news_sentences, topis, smpa)
- 테스트: 풀 안 Jaccard ≥ 0.9 쌍 0개, test_ood 기간 문장이 train에 0개, 같은 그룹이 두 기간에 0개
- 질문: 근접 중복 계산 — (a) 전수 비교: 정확, 문장 수만 개면 수 분 (b) MinHash LSH: 빠름, 놓치는 쌍이 생길 수 있음. 추천 (a) — 풀 크기상 감당되고 정확해야 누수 검사가 의미 있음
- 예상: 구현 ~110줄, 테스트 ~40줄, 실행 수 분
```
- 태우 `ok`나 답을 받으면 그 아래에 `ok (2026-11-08, 전수 비교)`처럼 적는다

## 사전 등록 (🧪만, PLAN 바로 아래, 실행 전, 이후 수정 금지)
`docs/experiments.md` §2 형식. 같은 내용을 config의 `hypothesis`·`expected`·`decision_rule`에 쓰고 커밋 → 그 커밋 해시를 여기에.

## READ-ALONG (Task 끝)
파일마다 아래 4개를 태우가 **읽을 순서**로 쓴다.
```
## READ-ALONG
### 1. src/notice_ner/collect/pool.py
- 하는 일: 문장 레코드를 읽어 정규화 → 완전 중복 → 근접 중복 그룹 → 기간 배정
- 핵심 함수: `normalize_text()` → `char_ngrams(text, n=5)` → `group_near_duplicates(records, threshold)` → `assign_period(published_at)`
- 읽는 순서: 상단 상수 → assign_period(가장 짧고 분할 규칙 전부가 여기) → group_near_duplicates
- 태우가 바꿀 수 있는 지점: `NEAR_DUP_THRESHOLD = 0.9`, `PERIODS`(기간 경계 — 바꾸면 docs/experiments.md §1 ADR 필요), `NGRAM_N = 5`
### 2. tests/test_pool.py
- 하는 일: 실제 풀에서 누수 0을 검사
- 기대값 출처: 주석 참고
- 읽는 순서: fixture → test_no_cross_period_group
```
- "태우가 바꿀 수 있는 지점"은 반드시 쓴다. 상수·설정·임계값·전략 선택 지점. 이게 제어권이다
- 어려운 개념(5-gram Jaccard, 클러스터 부트스트랩, BIO 정렬, QLoRA)은 한 문단으로 설명한다. 링크 말고 설명

## RESULT (🧪만, 실행 후)
```
## RESULT
- 실행: make train EXP=exp003 → make predict … → make eval … (run.json commit <hash>)
- 결과: (make report-table 출력 그대로 붙임 — 숫자를 손으로 쓰지 않는다)
- 사전 등록 대비: 기대 [a, b] → 실제 x. 맞음/틀림. 왜 그런지 한두 줄
- 시도 수: n회 (config 커밋 n개)
- 오류 유형(val): 경계 n · 태그 n · 놓침 n · 헛것 n · 정규형 n — 유형별 val 사례 3개씩
- 다음 실험에 넘기는 것:
```

## QUIZ (Task 끝, 3문제)
능동 회상용. 코드를 안 보고 답할 수 있어야 한다. 유형을 섞는다:
```
## QUIZ
1. [왜] 근접 중복을 분할 **전에** 지우는 이유는? 분할 뒤에 지우면 무슨 일이 생기나?
2. [추적] 2025-01-25에 게시된 기사 문장 하나가 build_pool에 들어가 어느 파일에 떨어지기까지 어떤 함수를 어떤 순서로 지나나?
3. [바꾸기] test_ood 기간을 2025-05-31까지 늘리고 싶다. 어느 파일·상수를 고치고, 무엇을 다시 실행해야 하고, 어떤 문서·ADR이 필요한가?

## 답변 (태우)
1.
2.
3.

## 채점 (Claude)
```
- 태우가 답을 쓰면 채점하고, 틀린 문제는 해당 코드를 같이 다시 읽는다
- 3문제 다 맞을 때까지 다음 Task GO를 권하지 않는다 (강제는 태우 몫)

## 하지 않는 것
- PLAN 건너뛰기, PLAN에 코드 붙여넣기
- 사전 등록을 실행 뒤에 쓰거나 고치기
- RESULT에 숫자를 손으로 쓰기
- READ-ALONG을 자동 요약처럼 쓰기. 읽을 순서와 손댈 지점이 핵심
- QUIZ를 "이 함수 이름은?" 같은 암기 문제로 내기
