# CLAUDE.md — Naru (하네스 v1)

Naru(나루)는 마라톤·집회 행진으로 횡단보도가 막힐 때, 통제 공지를 Claude API로 읽어 보행 그래프에 반영하고 지하도·육교로 건너는 우회 경로를 안내하는 서비스다.
이 파일은 원칙과 지도다. 자세한 건 아래를 **필요할 때 열어 읽는다**.

| 무엇 | 어디 |
|---|---|
| 레인·클래스·흐름·상태기계 (설계의 진실) | `harness/ARCHITECTURE.md` (+ `docs/architecture.png`) |
| 단계·Task·PC (진행 상태의 진실) | `harness/ROADMAP.md` |
| Task 기록 (진행 중 / 끝남) · 세션 로그 | `harness/plans/active/`, `harness/plans/completed/`, `harness/progress.md` |
| AI→BE, BE→FE 계약 | `docs/INTERFACE.md` ↔ `packages/contracts/naru_contracts/` (둘은 같아야 한다) |
| 레인별 언어·프레임워크 규약 | `docs/CONVENTIONS.md` — 코드 쓰기 전에 해당 레인 섹션을 읽는다 |
| FE 화면 목업 (참고용, 데이터는 예시) | `docs/mockups/01_home.html` · `02_route.html` · `03_closure.html` — 규칙은 CONVENTIONS §5.9 |
| 결정 기록 | `docs/decisions/ADR-*.md` — 바꾸려면 여기 먼저 |
| 절차 | `.claude/skills/` (task-cycle, real-data-testing) |
| 공지 파서 규칙 (프롬프트의 원본) | `docs/data/notice_parser_rules_v2.md` — 바꾸면 프롬프트 버전도 올린다 |

ARCHITECTURE·INTERFACE와 충돌하는 구현은 하지 않는다. 바꾸려면 ADR 초안 → 태우 승인. 이 파일은 스킬보다 우선한다.

## 1. 진행 방식 (최우선)
Task 하나를 끝까지 하고, **보고하고, 멈춘다.** 태우가 "다음"이라고 하면 다음 Task로 간다. 중간에 묻지 않는다.
1. **한 번에 Task 하나.** `harness/ROADMAP.md`에서 `status: DOING`인 Task. 없으면 ★ 경로에서 `depends`가 전부 DONE인 첫 `TODO`를 고르고 `DOING`으로 바꾼 뒤 시작한다. 태우가 "T2.3 먼저"라고 하면 그걸로.
2. **시작 메모 3줄** (`harness/plans/active/<task-id>.md`): 무엇을 / 어느 파일에 / 어떤 실데이터로 검증. 쓰고 **바로 진행한다.** 승인을 기다리지 않는다.
3. **구현은 테스트부터.** 실데이터 테스트 → 실패 확인 → 구현 → `make check` 초록 → 커밋. 이 과정은 보고하지 않고 한다. 커밋당 200줄 넘으면 둘로 나눈다.
4. **끝나면 보고 한 번** (형식은 `.claude/skills/task-cycle/SKILL.md`): 한 것 / 파일별 한 줄 / 어떤 실데이터로 어떻게 확인했나 / 태우가 직접 확인하는 명령 1~2개 / 내가 정한 것. 그리고 멈춘다.
5. **"다음"** → ROADMAP `DONE`, plan을 `completed/`로, `progress.md` 한 항목, 하네스 커밋, 다음 Task 시작. **"잠깐"·질문** → 답하고 기다린다. **"고쳐 …"** → 고치고 다시 보고.
6. **선택지가 있으면 추천안으로 진행하고 보고의 "정한 것"에 적는다.** 묻는 건 되돌리기 어려운 것뿐: 스키마·계약 변경, 외부 API 유료 호출, 데이터 삭제.
7. **서브에이전트·병렬·백그라운드 금지.** 확인할 수 있는 건 열어 보고 말한다 — 데이터 컬럼명, API 응답 필드, Anthropic tool use 파라미터명, 가격. 기억으로 쓰지 않는다.
8. **막히면 멈추고 말한다.** 데이터가 없다, 키가 없다, 계약과 다르다 — 가짜로 메우지 않는다.

## 2. 실데이터 원칙 (절대)
테스트·개발·데모 전부 실제 데이터로만. 가짜를 만들어 통과시키는 테스트는 테스트가 아니다.
- **금지** — 있으면 `make check` 실패 (`harness/gates/check_no_fakes.sh`): `unittest.mock`·`monkeypatch`·`respx`·`responses`·`vcr`·`httpretty`, FE `msw`·`vi.mock`·`vi.fn`·`jest.*`·`nock`·`sinon`, `faker`, 가짜 LLM 클라이언트(`FakeLLM` 등), 임의 좌표·합성 GeoJSON·손으로 친 공지 문장, 이름의 `fake`·`dummy`·`stub`·`mock`·`sample_`, `pytest.skip`·`xfail`. 데이터가 없으면 **실패**해야 한다.
- **허용 출처는 둘:** `data/raw/`(수집 CLI로 받고 `data/MANIFEST.md`에 출처·수집일·sha256·라이선스·행 수. 받은 뒤 수정 금지) · `data/recorded/<api>/`(실제 API·LLM 응답 원문 그대로. 키 제거. 손 편집 금지. 테스트는 키 있으면 live(상한 명시), 없으면 재생). hook이 둘의 수정을 막는다.
- 공지 텍스트는 실제 서울경찰청·TOPIS·보도 공지에서, 건마다 `source_url`·`published_at`·`fetched_at` 필수.
- 테스트 기대값은 데이터를 열어 확인한 값만, 옆에 확인 방법 주석. 예: `# data/raw/seoul_crosswalks_<date>.csv 행 1234, 교차로명 '세종대로사거리'`
- 외부 API 쿼터(TMAP 1,000/일, 버스 개발계정 1,000/일, Anthropic 월 한도). live 호출은 Task당 10회 이하, 반복은 recorded.
- 위 "Task당 10회"는 개발·테스트 규칙이다. 운영 워커(`naru_ai.worker --loop`)의 Claude live 파싱은 하루 상한 `NARU_LLM_DAILY_CAP`(기본 200, 넘으면 다음 날로)을 따르고, 응답은 전부 `data/recorded/llm/`에 기록한다 (ADR-011 D).
- 버스 폴링(운영 워커)은 전면 통제(공지 `lanes.scope` full·one_side_full)·마라톤 창(시작 1시간 전 ~ 끝+30분)에만 60초, 하루 상한 `NARU_BUS_DAILY_CAP`(기본 900), 응답은 전부 `data/recorded/bus/notice/`·`bus/marathon/`에 기록만 한다(`NARU_BUS_RECORD_ONLY=1` — 후보·상태에 안 보냄, ADR-013 보류 2026-11-09). 노선 경로(getRoutePath)는 노선당 하루 한 번 `data/raw/bus_routes/<날짜>/` (ADR-013 I). ADR-011 E의 "같은 곳 최소 10분"은 웹 페이지 수집에만 — 키로 쓰는 공개 API(돌발 OA-13315 등)는 그 한도와 우리 일 상한을 따른다 (ADR-013 G·H).
- 유일한 예외: 순수 수학 함수의 단위 테스트는 실데이터에서 뽑은 좌표를 상수로 써도 된다. 출처 주석 필수.
- 목업(`docs/mockups/`)의 숫자·좌표·문장도 예시다. 코드·테스트에 가져오지 않는다.

## 3. 스택 (ADR-006 · ADR-007) — 규약은 `docs/CONVENTIONS.md`
| 레인 | 패키지 | 스택 |
|---|---|---|
| contracts | `packages/contracts` (`naru_contracts`) | pydantic v2. INTERFACE.md의 유일한 코드 구현. AI·BE 둘 다 여기서만 import. **코드가 이미 있다** — T0.1에서 읽고 T2.1에서 테스트로 고정 |
| AI | `packages/ai` (`naru_ai`) | Python 3.12 · anthropic SDK · Shapely/pyproj · httpx. **독립 워커** — 후보를 `POST /internal/candidates`로 BE에. 공지 파서는 **Claude API**(`claude-haiku-5-5`, tool use 구조화 출력: spans + segments). 좌표는 지명사전(리졸버)이, 선은 BE가 만든다. 로컬 사후학습은 해커톤 이후(ADR-007) |
| BE | `packages/be` (`naru_be`) | Python 3.12 · **Flask 3, MVC** (controllers / views / models) · SQLAlchemy 2 + PyMySQL + Alembic · **MySQL 8.4** · NetworkX · Shapely STRtree |
| FE | `packages/fe` | **Next.js (App Router)** · React 19 · TypeScript strict · pnpm · maplibre-gl 직접 · **Context Provider + useReducer** (4개 분리) · vitest · Playwright |

핵심 규칙:
1. **BE는 MVC, 의존은 controllers → views → models 아래로만.** Controller는 검증 → Model → View 3줄, Model은 Flask를 모르고, View는 DB를 모른다. `.importlinter`가 강제
2. **AI ↔ BE 직접 import 금지.** 경계는 HTTP + `naru_contracts`. `.importlinter`가 강제
3. **모델은 좌표를 만들지 않는다.** Claude는 문장 안의 표현(spans)과 구간(segments: from/to/via/road)만 낸다. 좌표는 `naru_ai.notice.resolver`(지명사전·카카오 기록), 선은 BE `CrosswalkIndex.from_segment`(도로 그래프 최단경로 + 도로 등급별 버퍼)
4. **Next.js는 화면만.** Route Handler·Server Actions에 로직 금지. BE 호출은 `/api/*` rewrites. `'use client'` 경계는 `providers.tsx`·`NaruApp.tsx`·`DataAsOf.tsx`(/licenses 데이터 기준 시각, T7.13) 셋
5. 공간 연산은 Python에서. MySQL은 결과 저장소. `ST_*` 안 씀
6. FE 타입은 `make schema`로 생성. 손으로 안 씀
7. 시간은 tz-aware, DB UTC. 좌표는 `[lng, lat]`, 미터 계산은 EPSG:5179. enum 코드값 영어, 한국어는 FE `i18n/ko.ts`에서만
8. LLM 응답은 전부 `data/recorded/llm/`에 기록하고 테스트·시연은 재생. 프롬프트는 `naru_ai/llm/prompts/notice_v<n>.md`로 버전 관리. 출력은 strict tool schema + 규칙 기반 confidence로 고정(샘플링 파라미터 없음 — claude-haiku-5-5는 temperature에 400)

## 4. 명령
```
make setup / check / layers / check-no-fakes / schema / dev
make fetch SRC=seoul_spatial|nodelink|course|station     # P0
make record API=bus|incident|rtd                          # P0
make record-llm NOTICES=data/raw/notices/...             # T4.1 — 실제 Claude 호출을 기록
make record-candidates SOURCE=course|notice|bus           # AI 실행 결과를 BE 테스트 입력으로
make record-naru-api                                      # 로컬 Flask 응답을 FE 테스트 입력으로
```
`make check` = ruff + mypy + lint-imports + check-no-fakes + pytest + FE check. 이게 초록이어야 커밋.

## 5. 하네스·git 규칙
1. **브랜치는 `develop`.** 모든 커밋은 develop에 직접. `main`은 PR로만 — hook이 main 커밋을 막는다. 새 브랜치를 만들지 않는다
2. **커밋을 나눈다.** 코드 커밋(`T1.2: …`)과 하네스 커밋(`harness: T1.2 done` — ROADMAP status, plan, progress)을 섞지 않는다. hook이 막는다
3. **하네스 문서는 `harness/` 밖에 만들지 않는다.** 새 `.md`는 `harness/`, `docs/decisions/`(ADR 초안), `docs/data/`, `packages/fe/`에만 — hook이 그 밖은 막는다
4. **경로는 백틱으로만.** `@` 임포트를 쓰지 않는다
5. **세션 시작:** `harness/progress.md` 마지막 항목 → ROADMAP의 DOING → 해당 plan → `git log --oneline -10` → 이어서 한다. 보고 안 한 Task가 있으면 보고부터
6. 문서와 코드가 어긋나면 고치지 말고 먼저 태우에게 말한다

## 6. 금지
- ROADMAP에 없는 작업, 스코프 확장, "하는 김에" 리팩터링
- `harness/ARCHITECTURE.md`·`docs/INTERFACE.md` 임의 변경. `naru_contracts`를 INTERFACE와 다르게 고치기
- 게이트 약화: `harness/gates/`, `.importlinter`, `.claude/settings.json`, `.claude/hooks/`
- `# noqa`, `# type: ignore`, `except: pass` — 꼭 필요하면 같은 줄에 이유
- 시크릿·`.env`·`data/raw`·`data/recorded` 대용량 파일 커밋
- `main` 직접 커밋, 새 브랜치, "다음" 없이 다음 Task 진행
- 커밋 메시지에 Task ID 누락: `T1.2: CrosswalkIndex.from_segment — 도로 그래프 최단경로 + 등급별 버퍼`

## 7. Definition of Done (Task)
1. 실데이터 테스트 통과 · 2. `make check` 초록 · 3. develop에 코드 커밋 · 4. 보고 · 5. 태우 "다음" → `DONE`, plan을 `completed/`로, 하네스 커밋
