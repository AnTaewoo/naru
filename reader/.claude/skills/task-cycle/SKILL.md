---
name: task-cycle
description: notice-ner에서 ROADMAP Task 하나를 수행하는 절차. Task를 시작하거나 "다음 Task", "GO", "진행해"라는 말이 나오면 따른다. 🧪 실험 Task는 experiment-protocol 스킬도 같이 따른다.
---

# Task 사이클

목적: 태우가 매 단계를 보고 이해한 채로 진행한다. 속도보다 이해, 숫자보다 절차.

## 0. 시작 조건
1. `ROADMAP.md`에서 `status: GO`인 Task를 찾는다. 없으면 멈추고 다음 Task ID를 제안한다.
2. `depends`가 전부 `DONE`(또는 PC 통과)인지 확인한다. 아니면 멈추고 말한다.
3. 종류를 확인한다 (ROADMAP 아이콘):
   - 🧩 코드: CLAUDE.md §5 규약과 패키지 경계(`.importlinter`)
   - 🗂 데이터: `docs/data_sources.md`의 출처·라이선스·접근 방식, CLAUDE.md §4 수집 원칙
   - 🧪 실험: `experiment-protocol` 스킬. 사전 등록 없이 학습·추론을 돌리지 않는다
   - 🧑 사람: Claude는 체크리스트와 진행률 도구까지만
4. 이 Task가 쓸 데이터가 `data/MANIFEST.md`(라벨이면 `data/splits/<ver>/SPLIT.md`)에 있는지. 없으면 멈추고 그 데이터 Task를 제안한다.
5. 이 Task가 sealed 경로나 test 산출물을 건드려야 하나? → R4.7 말고는 아니다. 필요해 보이면 멈추고 이유를 말한다.

## 1. PLAN (코드 수정 금지)
- `docs/walkthrough/<task-id>.md`를 만들고 PLAN을 쓴다. 템플릿은 `walkthrough` 스킬. 15줄 이내 (🧪 사전 등록은 별도 블록)
- 첫 줄에 종류·패키지: `🗂 collect` / `🧪 models · exp002`
- 결정이 필요한 건 "질문"으로, 추천안과 이유를 붙인다. 태우에게는 한 번에 하나씩 묻는다
- 외부 API 호출 수, 예상 비용, 예상 실행 시간을 숫자로 쓴다
- 태우 `ok`를 받으면 그 아래 `ok (YYYY-MM-DD, 결정 요약)`을 적고 status → `DOING`

## 2. Red
- 테스트부터. 실데이터 fixture (`real-data-testing` 스킬)
- 기대값은 데이터를 열어 확인한 값 + 확인 주석
- `make check` → **실패**를 확인하고 실패 메시지를 태우에게 보여 준다 (실패하지 않으면 테스트가 틀린 것)

## 3. Green
- 테스트를 통과시키는 최소 구현. 파일 하나 만들 때마다 "이 파일: 역할 한 줄"
- 200줄을 넘을 것 같으면 멈추고 쪼개자고 제안
- `make check` 초록 → 바뀐 파일과 이유 5줄 이내 → 멈춤

## 4. Refactor
- 이름·중복·구조 정리. 동작 변경 없음. `make check` 초록 유지
- 할 게 없으면 "없음"

## 5. Gate
- `make check` 최종 초록 (🧪는 `make check-gpu`도)
- 실행 결과가 있는 Task는 실행 명령·로그 경로·`run.json`의 커밋 해시를 walkthrough에
- 커밋: `R<id>: <무엇> — <한 줄 왜>`. 쪼갰으면 `R<id>.a`, `R<id>.b`

## 6. READ-ALONG + QUIZ (+ RESULT)
- `walkthrough` 스킬 템플릿. 🧪는 RESULT에 사전 등록 대비 결과 (`make report-table` 출력 그대로)
- status → `REVIEW`. 태우가 QUIZ 답을 쓰면 채점, 틀린 문제는 해당 코드를 같이 다시 읽는다
- `DONE`은 태우가 쓴다

## 하지 않는 것
- 다음 Task로 자동 진행
- 서브에이전트, 병렬 작업, 백그라운드 실행
- PLAN 없이 실행 ("일단 한 번 돌려 보기"도 실행이다)
- 데이터가 없을 때 대체물 만들기. 없으면 멈춘다
- val 결과가 나쁘다고 test로 확인해 보기
- 라벨 고치기 (→ `labeling/issues.md`)
- 설계 변경 (→ `docs/decisions/` ADR 초안 → 태우 승인 → 그다음)

## 보고 형식 (각 단계 끝)
```
[R1.2 · Green · 🗂 collect] 바뀐 파일
- src/notice_ner/collect/article.py (+92): robots 확인 → 1rps GET → trafilatura 본문 → 후보 문장
- tests/test_article.py (+28): data/raw/news/<run_ts>.jsonl로 출처 3종·robots 제외 검증
make check: ✅ (ruff ok, mypy ok, layers 2 kept, no-fakes ok, 6 passed)
다음: Refactor. 계속할까요?
```
