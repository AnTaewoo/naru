# ADR-006 스택: Next.js · Flask(MVC) · MySQL · Context Provider
- 상태: 승인 (2026-11-04, 태우) — 개정 1 (2026-11-04): React → Next.js, BE MVC, LLM 보류 · 개정 2 (2026-11-06): LLM은 ADR-007로 확정(Claude API)
- 규약: `docs/CONVENTIONS.md`

## 결정
| 레인 | 선택 | 대안(검토했으나 안 씀) |
|---|---|---|
| FE | **Next.js (App Router)** + React 19 + TS strict, 상태는 **Context Provider + useReducer**, 지도는 maplibre-gl 직접 | React+Vite 단독, Zustand, react-map-gl |
| BE | **Flask 3, MVC** (Controller = Blueprint, Model = 도메인+DB, View = 응답 직렬화), SQLAlchemy 2 + Alembic | FastAPI |
| DB | **MySQL 8.4** | PostGIS |
| LLM | **Claude API** (ADR-007). 로컬 사후학습은 해커톤 이후 실측 | 로컬 Kanana-2 확정 (개정 전 안) |
| 그래프 | NetworkX 인메모리 | pgRouting |
| AI↔BE | AI는 독립 워커 프로세스, `POST /internal/candidates`로 BE에 전달 | BE 스케줄러가 AI 모듈을 직접 호출 |

## 결과 — 이 선택 때문에 바뀌는 것
1. **MySQL → 공간 연산은 전부 Python.** PostGIS의 `ST_DWithin`·범위 타입·pgRouting이 없다. `CrosswalkIndex`(Shapely STRtree, EPSG:5179)와 `PedGraph`(NetworkX)가 계산하고 MySQL은 결과만 저장한다. 서울 횡단보도는 수만 행이라 인메모리로 충분하다.
2. **Flask → 계약 동기화를 직접 한다.** OpenAPI 자동 생성이 없으므로 `naru_contracts`(pydantic)를 단일 원천으로 두고 `model_json_schema()` → `contracts.d.ts`를 스크립트로 생성한다.
3. **MVC → 계층 규칙을 Gate로 강제한다.** 문서만으로는 Controller에 로직이 새고 Model이 Flask를 import한다. `.importlinter` 계약(`be-mvc-layers`, `models-no-flask`, `views-no-db`, `controllers-thin`)을 `make check`에 넣었다. 의존은 controllers → views → models, 아래로만.
4. **AI↔BE를 HTTP로 끊었다.** 개정 전에는 BE의 IngestScheduler가 AI Ingestor를 부르는 구조였는데, 이는 "AI↔BE 직접 import 금지"와 모순이었다. AI가 독립 워커(`naru_ai.worker`)로 돌며 `ClosureCandidate`를 BE의 `candidate_controller`로 POST한다. `RouteSectionIndex`도 AI로 옮겼다(버스 이탈 감지만 쓴다).
5. **Next.js → 화면만 맡긴다.** Route Handler·Server Actions에 로직을 두지 않는다(백엔드는 Flask 하나). BE 호출은 `rewrites`로 같은 오리진 `/api/*` 프록시 → CORS 불필요, 운영은 `next start`. maplibre는 `dynamic(..., { ssr: false })`로 클라이언트에서만.
6. **Context Provider → 재렌더 관리가 우리 몫.** Provider를 Api·Time·Closure·Route 4개로 쪼개고 state/dispatch Context를 분리한다. 지도 레이어는 `setData()` 명령형 갱신.
7. **LLM → ADR-007.** 클라이언트는 `AnthropicClient` 하나. 가짜 구현 금지는 그대로. 응답은 전부 기록·재생.

## 버전 (T0.1·T5.0·T6.0에서 실제 설치 후 채운다)
| 항목 | 버전 | 기록일 |
|---|---|---|
| Python | 3.12.8 | 2026-11-07 (T0.1) |
| Flask / gunicorn | 3.1.3 / 26.2.0 | 2026-11-07 (T0.1) |
| SQLAlchemy / Alembic / PyMySQL | 2.1.8 / 1.20.1 / 1.2.3 | 2026-11-07 (T0.1) |
| pydantic / pydantic-settings | 2.14.3 / 2.16.2 | 2026-11-07 (T0.1) |
| GeoPandas / Shapely / pyproj / NetworkX | 1.2.0 / 2.2.0 / 3.8.0 / 3.7 | 2026-11-07 (T0.1) |
| httpx / anthropic SDK | 0.28.1 / 2.6.0 | 2026-11-07 (T0.1) |
| import-linter | 2.16 | 2026-11-07 (T0.1) |
| MySQL 이미지 | mysql:8.4 (서버 8.4.13, 호스트 포트 3307) | 2026-11-07 (T0.1) |
| Node / pnpm | | |
| Next.js / React / TypeScript / maplibre-gl | | |
