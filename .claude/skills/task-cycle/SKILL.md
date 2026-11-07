---
name: task-cycle
description: Naru에서 ROADMAP Task 하나를 수행하는 절차. Task를 시작하거나, "다음", "진행해", "T2.3 먼저"라는 말이 나오면 이 스킬을 따른다.
---

# Task 사이클

Task 하나를 끝까지 → 보고 한 번 → 멈춤 → 태우 "다음" → 다음 Task. 중간 승인 없음.

## 0. 어느 Task인가
1. 세션 첫 Task면 `harness/progress.md` 마지막 항목과 `git log --oneline -10`부터. 브랜치가 `develop`인지 확인 (`git branch --show-current`). 아니면 `git switch develop`.
2. `harness/ROADMAP.md`에서 `status: DOING`인 Task. 없으면 ★ 경로에서 `depends`가 전부 `DONE`인 첫 `TODO`. 태우가 Task를 지정하면 그것.
3. 그 Task의 status를 `DOING`으로 바꾼다. (하네스 변경 — 코드와 같이 커밋하지 않는다)
4. `docs/INTERFACE.md`·`harness/ARCHITECTURE.md`에서 이 Task가 건드리는 부분, `docs/CONVENTIONS.md`의 해당 레인 섹션을 읽는다. FE Task면 `docs/mockups/`의 해당 화면도.
5. 쓸 실데이터가 `data/MANIFEST.md`·`data/recorded/`에 있는지 확인. 없으면 멈추고 말한다 — 가짜로 대체하지 않는다.

## 1. 시작 메모 (3줄, 기다리지 않는다)
`harness/plans/active/<task-id>.md`:
```
# T1.2 CrosswalkIndex.from_segment
- 무엇: 구간(from/to/via/road) → 도로 그래프 최단경로 → 등급별 버퍼 → 횡단보도 ID 집합
- 파일: packages/be/naru_be/models/domain/crosswalk_index.py, road_graph.py, tests/test_crosswalk_index.py
- 검증: data/raw/nodelink_seoul_<date>/ + data/raw/seoul_crosswalks_<date>.csv — 세종대로 숭례문→시청 구간
```
쓰자마자 2로 간다.

## 2. 구현 (보고 없이)
- 테스트 먼저. `.claude/skills/real-data-testing/SKILL.md`대로 실데이터 fixture. 기대값은 데이터를 열어 확인한 값, 확인 방법 주석.
- `make check`로 테스트가 **실패**하는 걸 본 뒤 구현. 통과시키는 최소 구현 → 정리 → `make check` 초록.
- 한 Task가 두 계층(BE Model/View/Controller, FE Server/Client)을 건드리면 커밋을 계층별로 나눈다. 커밋당 200줄 이하.
- 커밋: `T<id>: <무엇> — <한 줄 왜>`. develop에 직접.
- 막히면(데이터 없음, 키 없음, 계약과 다름, 외부 API 실패) 거기서 멈추고 보고 형식으로 상황을 적는다.

## 3. 보고 (Task 끝, 한 번)
```
## T1.2 끝 — CrosswalkIndex.from_segment

한 것: 구간(from/to/via/road)을 횡단보도 ID 집합으로 바꾸는 from_segment. RoadGraph는 표준노드링크를 NetworkX로.

파일
- packages/be/naru_be/models/domain/road_graph.py (+92): 노드링크 적재, shortest_path(points, road). road 주면 그 도로명 링크만
- packages/be/naru_be/models/domain/crosswalk_index.py (+41): from_segment = shortest_path → 버퍼(대로 25/로 15/길 8m) → from_line
- packages/be/tests/test_crosswalk_index.py (+38): 숭례문→시청 구간 → 세종대로 횡단보도 7개

확인한 방법
- 실데이터: data/raw/nodelink_seoul_20261108/ (링크 184,203), data/raw/seoul_crosswalks_20261108.csv (행 31,882)
- 기대값: csv에서 교차로명 '세종대로' 필터 → 관리번호 7개 (테스트 주석에 행 번호)
- make check ✅ ruff · mypy · lint-imports 6 kept · no-fakes · pytest 12 passed

직접 확인
- uv run pytest packages/be/tests/test_crosswalk_index.py -v
- uv run python -m naru_be.models.domain.crosswalk_index --from 숭례문 --to 시청교차로 --road 세종대로   (ID 7개 출력)

정한 것
- 버퍼 안에 일부만 걸친 횡단보도도 포함 (통제는 넓게 잡는 게 안전). 중심점 기준으로 바꾸려면 crosswalk_index.py의 INCLUDE_PARTIAL
- road 미지정이면 전체 그래프 최단경로

커밋: a1b2c3d, d4e5f6a
다음: T1.3 TimeDependentRouter 뼈대
```
- "직접 확인"은 태우가 복붙해서 돌릴 수 있는 명령이어야 한다. 출력이 뭐여야 하는지 괄호로.
- "정한 것"에는 선택지가 있었던 결정만. 바꾸는 위치(파일·상수)를 같이 적는다.
- 보고 뒤 **멈춘다.** 다음 Task를 시작하지 않는다.

## 4. 태우의 응답
- **"다음"** → ROADMAP status `DONE`, `git mv harness/plans/active/<id>.md harness/plans/completed/`, `harness/progress.md`에 항목 추가, `git commit -m "harness: <id> done"`, 0으로.
- **"잠깐" / 질문** → 답한다. 코드 안 건드림.
- **"고쳐 …"** → 고치고 `make check` → 보고의 바뀐 부분만 다시.
- **"T2.3 먼저"** → 현재 Task는 `DOING` 그대로 두고 메모에 "보류: <이유>" 한 줄, 지정된 Task로.

## PC (Prototype Check)
Plan 끝의 PC는 태우가 눈으로 확인하는 관문. PC 직전 Task 보고에 PC 체크리스트를 붙이고, 태우가 "PC 통과"라고 해야 다음 Plan으로 간다.

## 하지 않는 것
- "다음" 없이 다음 Task
- 단계마다 멈춰서 묻기, 퀴즈, 읽기 순서 설명 (태우가 물으면 그때 답한다)
- 서브에이전트, 병렬 파일 생성, 백그라운드 실행
- 데이터 없을 때 가짜로 대체
- 설계 변경. 필요하면 `docs/decisions/ADR-xxx.md` 초안 → 보고에 적고 멈춤
