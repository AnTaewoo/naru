# CONVENTIONS.md — 언어·프레임워크 규약

스택 결정은 `docs/decisions/ADR-006-stack.md`. 이 문서는 그 스택을 **어떻게 쓰는지**다. 바꾸려면 ADR 먼저.
Claude는 코드를 쓰기 전에 해당 레인 섹션을 읽는다. 여기 없는 선택이 필요하면 추측하지 말고 태우에게 묻는다.

| 레인 | 언어 | 프레임워크 | 저장소·모델 |
|---|---|---|---|
| contracts | Python 3.12 | pydantic v2 | — |
| AI | Python 3.12 | anthropic SDK · Shapely · pyproj · httpx · pdfplumber | 공지 파서 = **Claude API** (ADR-007). 로컬 사후학습은 해커톤 이후 |
| BE | Python 3.12 | **Flask 3 — MVC** · SQLAlchemy 2 · Alembic · NetworkX | **MySQL 8.4** |
| FE | TypeScript (strict) | **Next.js (App Router)** · React 19 · maplibre-gl · Context Provider | — |

---

## 0. 전 레인 공통

- **식별자는 영어, 주석·docstring은 한국어 허용.** 커밋 제목은 `T1.2: 무엇 — 왜` (한국어 가능).
- **시간**: DB는 UTC `DATETIME(0)`. API 입출력은 ISO 8601 **오프셋 필수**(naive 금지), 서버 응답은 `+09:00`로 통일. Python `datetime`은 항상 tz-aware — `datetime.now()` 금지, `datetime.now(UTC)` 또는 `datetime.now(KST)`.
- **좌표**: 저장·전송은 WGS84, 순서는 GeoJSON대로 `[lng, lat]`. 거리·버퍼 계산은 **EPSG:5179로 투영한 뒤 미터**로. 도(degree)에 미터를 더하지 않는다.
- **enum 코드값은 영어 snake_case.** 한국어는 FE 라벨에서만. (`scheduled` → "예정")
- **버전 고정**: `uv.lock`, `pnpm-lock.yaml` 커밋. 실제 설치된 버전은 ADR-006 "버전" 표에 기록한다.
- **파일 400줄 넘으면 쪼갠다.** 함수 50줄 넘으면 쪼갠다.

## 1. Python 공통 (contracts · ai · be)

- Python 3.12, uv 워크스페이스. 패키지 셋: `packages/contracts`(`naru_contracts`), `packages/ai`(`naru_ai`), `packages/be`(`naru_be`).
- **이름**: 모듈·함수·변수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE`. 메서드도 snake_case — `from_segment`, `active_at`.
- **ruff**: `select = ["E","F","I","B","UP","SIM","N","RUF"]`, `line-length = 100`, `ruff format`.
- **mypy `--strict` 전 패키지.** `Any` 반환 금지. 외부 라이브러리 타입 stub이 필요하면 추가하고 보고의 "정한 것"에 적는다.
- **docstring**: Google 스타일. 공개 함수·클래스만. "무엇을"보다 "왜"를.
- **예외**: 패키지별 `errors.py`에 도메인 예외. `except Exception:` 금지. 잡으면 로그 남기고 다시 던지거나 명시적으로 변환.
- **로깅**: 표준 `logging` + JSON 한 줄 포맷 (`naru_*/log.py` 하나). `print` 금지. 외부 호출은 `api`, `params`(키 제거), `status`, `elapsed_ms`를 남긴다.
- **설정**: `pydantic-settings`의 `Settings` 하나(`naru_*/config.py`). 코드에서 `os.environ` 직접 읽지 않는다. 임계값(0.7, 0.8, ×3, 30분, 점 반경 30m, 선 버퍼 15m, 도로 등급별 버퍼 대로 25m/로 15m/길 8m)은 전부 여기.
- **의존 방향** (`.importlinter`가 `make check`에서 강제):
  - `ai → contracts`, `be → contracts`. **ai ↔ be 직접 import 금지.** AI→BE는 HTTP(`POST /internal/candidates`)로만 넘긴다.
  - `naru_contracts`는 우리 패키지를 import하지 않는다.

## 2. contracts — `packages/contracts` (`naru_contracts`)

- `docs/INTERFACE.md`의 **유일한 코드 구현**. pydantic v2 `BaseModel`, `model_config = ConfigDict(extra="forbid", frozen=True)`.
- 모듈: `enums.py`, `closure.py`(ClosureCandidate, ClosureState, Evidence, Window, Geometry 유니온, CandidateBatch), `route.py`(RouteQuery, RouteResponse, Leg, Avoided), `closures_api.py`(ClosuresQuery, FeatureCollection), `errors.py`(ErrorBody).
- `scripts/export_schema.py` → `model_json_schema()` → `packages/fe/src/types/contracts.d.ts`(`json-schema-to-typescript`). **FE 타입을 손으로 쓰지 않는다.** Flask라 OpenAPI 자동 생성이 없으므로 이게 계약 동기화의 유일한 경로다.
- 테스트: INTERFACE.md의 예시 JSON 블록을 뽑아 그대로 `model_validate`. 문서와 코드가 어긋나면 테스트가 깨진다.

## 3. AI — `packages/ai` (`naru_ai`)

### 3.1 구조
```
naru_ai/
  config.py  log.py  errors.py
  ingest/course.py  ingest/incident.py
  notice/source.py        # NoticeSource — smpa PDF 표·TOPIS·보도 → 문장 레코드
  notice/parser.py        # NoticeParser — Claude API tool use → spans + segments, 정렬·검증
  notice/resolver.py      # Resolver — 정규형 → PlacePoint (지명사전: 교차로·도로명·카카오 기록)
  notice/gazetteer.py     # 지명사전 적재 (data/raw/seoul_spatial, roads, data/recorded/kakao)
  notice/candidates.py    # CandidateBuilder — ParsedNotice → ClosureCandidate (segment / point)
  notice/eval.py          # 라벨 정답 대비 정규형 F1·구간 F1
  signal/route_section_index.py  signal/bus_deviation.py     # P6 (해커톤 이후)
  llm/client.py           # AnthropicClient — 유일한 LLM 클라이언트
  llm/recorder.py         # 요청·응답 원문 기록·재생 (data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json)
  llm/prompts/notice_v1.md
  worker.py               # IngestWorker — 스케줄로 위 Ingestor들을 돌린다
  publish.py              # CandidatePublisher — CandidateBatch를 BE로 POST
```
- AI는 **독립 프로세스**(`python -m naru_ai.worker`)로 돈다. BE를 import하지 않는다.
- 스케줄: 공지 5분 · 돌발 1분 · 버스는 통제 창 ±30분 안 15초 / 밖 5분. 일 호출 예산 상한은 `Settings`.
- `CandidatePublisher`는 httpx로 `POST {NARU_BE_URL}/internal/candidates`, 헤더 `X-Naru-Internal-Token`. 실패 시 3회 재시도 후 로그. **단위 테스트하지 않는다** — e2e에서 실제 BE로만.

### 3.2 LLM — Claude API (ADR-007)
- 공지 파서는 **Claude API** 하나다. 기본 `NARU_LLM_MODEL=claude-haiku-5-5`, 평가 비교용 `claude-sonnet-5-5`. 모델 ID는 실행 시점 Anthropic 문서에서 확인.
- `naru_ai/llm/client.py`의 `AnthropicClient.complete_tool(system, messages, tool)` — strict tool schema + `tool_choice` 강제로 출력을 고정하고, confidence는 규칙(규칙서 §3.8)으로 정한다. 샘플링 파라미터는 보내지 않는다(`claude-haiku-5-5`는 `temperature` 등에 400, SDK 2.6.0엔 키도 없음). `max_tokens=4096`(`NARU_LLM_MAX_TOKENS`). 파라미터명은 설치된 SDK 타입에서 확인하고 주석.
- 출력 스키마(`llm/notice_schema.py`, 규칙서 v2 §9.1): `items[{window{start,end}, approx, kind, impact ∈ blocks|none|unknown, impact_reason, segments[{order, from, to, via[], road, direction, lanes{count, scope}, length_km}], points[{name, road_hint}], toward, road_hints[], reported_people, police_stations[], spans[{text, tag ∈ 6종, canonical}], confidence, notes}]`. **좌표 필드 없음.** strict JSON Schema는 이 pydantic 모델에서 생성(참조 인라인, 전부 required, number의 minimum/maximum 제거 — API가 거부).
- 프롬프트는 `llm/prompts/notice_v<n>.md`. few-shot 예시는 `data/raw/notices/`의 실제 문장 id를 적는다. 바꾸면 버전을 올리고 기록을 새로 만든다.
- 정렬기: `span.text`를 문장에서 문자열 검색해 start/end. 못 찾으면 버리고 개수를 로그. `segments.from/to`는 spans의 canonical과 일치해야 하고, 아니면 segment를 버린다.
- 가짜 클라이언트(`FakeLLM`, `EchoClient`) 금지. 테스트·시연은 `llm/recorder.py` 재생.
- 로컬 모델 사후학습(klue/roberta·LoRA)은 해커톤 이후 `naru-reader` 실측으로 판단. 전환하면 `AnthropicClient` 옆에 두 번째 클라이언트를 추가하고 ADR-007을 개정한다.

### 3.3 LLM 테스트
- `make record-llm NOTICES=<jsonl>`가 실제 공지 문장을 호출하고 `data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json`에 요청(system·messages·input_schema)·원문 응답·usage 저장.
- 테스트는 recorded 재생만. recorded의 `model`·`prompt_version`이 현재 설정과 다르면 **fail**. live는 `make record-llm`에서만(상한 명시).
- 정확도는 `notice/eval.py`가 사람 라벨(`data/raw/notices/labels_v1.jsonl`, naru-reader export)과 비교: 정규형 F1(주지표), 구간 F1, 횡단보도 집합 Jaccard. 임계값은 T4.3 결과를 보고 태우가 정한다.

### 3.4 지명사전(Resolver)
- 교차로: 서울시 교차로·횡단보도 데이터의 교차로명 그대로 정규형. 좌표·횡단보도 ID 포함.
- 도로명: 도로명주소 도로명코드(서울) 공식 도로명. 좌표 없음, `road_class`(대로/로/길)만.
- POI·주소: 카카오 Local 키워드/주소 검색 — 응답 원문을 `data/recorded/kakao/<kind>/<sha1(canonical)>.json`에 기록, 있으면 재생. 1순위 선택 규칙(서울 범위·카테고리)은 `resolver.py` 상단 상수.
- 별칭(세종R → 세종대로사거리)은 `data/raw/gazetteer/aliases.csv`(사람이 정리, 근거 문장 id 필수).
- 못 찾으면 `None`. 추측 좌표·기본 좌표 금지.

## 4. BE — `packages/be` (`naru_be`) — MVC

### 4.1 계층과 책임

| 계층 | 폴더 | 아는 것 | 모르는 것 | 하는 일 |
|---|---|---|---|---|
| **Controller** | `controllers/` | Flask(`Blueprint`, `request`), contracts 요청 타입, views, models | SQLAlchemy · Shapely · NetworkX를 **직접** 쓰지 않음 | HTTP 요청을 받아 검증하고, Model을 부르고, 결과를 View에 넘긴다 |
| **Model** | `models/` | SQLAlchemy, Shapely, NetworkX, contracts 입력 타입 | **Flask, View, Controller** | 데이터와 도메인 로직 전부. 결과는 도메인 객체(frozen dataclass)로 돌려준다 |
| **View** | `views/` | contracts 응답 타입, Flask `jsonify`, models의 도메인 **타입** | DB 세션·쿼리 | 도메인 객체 → contracts 응답 모델 → JSON `Response` |

- 의존 방향: **controllers → views → models** (아래로만). Model은 위를 모른다.
- `.importlinter` 계약 4개가 `make check`에서 강제한다: `be-mvc-layers`, `models-no-flask`, `views-no-db`, `controllers-thin`.
- 비즈니스 규칙(상태 전이, 비용 계산, 임계값 판단)은 **Model에만**. Controller에 `if status == ...`가 보이면 잘못 놓인 것.

### 4.2 구조
```
naru_be/
  app.py               # create_app(settings) — 설정·로그·DB 엔진·Model 싱글턴 로드·Controller 등록·에러 핸들러
  config.py  log.py  errors.py  db.py
  controllers/
    _deps.py                    # naru_models() — current_app.extensions["naru"]를 타입 있게 꺼내는 함수 하나
    route_controller.py         # Blueprint "route"     GET  /route
    closure_controller.py       # Blueprint "closures"  GET  /closures
    candidate_controller.py     # Blueprint "internal"  POST /internal/candidates  (AI 워커 전용, 토큰)
  models/
    entities/closure_state.py           # SQLAlchemy ORM — 테이블 closure_states
    repositories/closure_repository.py  # upsert · active_at. DB 접근은 여기만
    domain/types.py                     # RouteResult, Leg, AvoidedCrosswalk ... (frozen dataclass)
    domain/ped_graph.py
    domain/crosswalk_index.py  domain/intersection_map.py
    domain/closure_engine.py
    domain/routers.py                   # TimeDependentRouter · BaselineRouter
    domain/route_planner.py             # RoutePlanner — 활성 폐쇄 조회 → 두 라우터 → RouteResult
    domain/candidate_intake.py          # CandidateIntake — 후보 → CrosswalkIndex → ClosureEngine → Repository
  views/
    route_view.py      # RouteResult → RouteResponse → JSON
    closure_view.py    # list[ClosureState] + zones → GeoJSON FeatureCollection
    error_view.py      # 도메인 예외·검증 오류 → INTERFACE §6 오류 JSON
migrations/            # Alembic
```

### 4.3 Controller
- Flask 3, **app factory** `create_app(settings: Settings) -> Flask`. 전역 `app = Flask(__name__)` 금지.
- 리소스별 Blueprint 하나 = 파일 하나. **핸들러는 3줄**: 검증 → Model → View.
  ```python
  bp = Blueprint("route", __name__)

  @bp.get("/route")
  def get_route() -> Response:
      query = RouteQuery.model_validate(request.args.to_dict())   # 실패 → error_view가 400
      result = naru_models().route_planner.plan(query)            # Model
      return route_view.render(result)                             # View
  ```
- 검증은 pydantic으로 **직접**. flask-pydantic·flask-smorest·APIFlask 같은 확장 쓰지 않는다 — 요청이 어디서 검증되는지 코드에서 바로 보이게.
- `/internal/*`는 `X-Naru-Internal-Token` 헤더를 `Settings.internal_token`과 비교, 다르면 401. 이 검사는 Blueprint `before_request` 한 곳.
- 동기(sync). 운영은 gunicorn `workers=2, threads=4`.
- CORS 설정 없음 — FE는 Next.js rewrites로 같은 오리진에서 호출한다(§5.2).

### 4.4 Model
- **Flask를 import하지 않는다.** `request`, `current_app`, `g`, `jsonify` 전부 금지. 필요한 건 생성자로 주입받는다.
- 무거운 Model(PedGraph, CrosswalkIndex, RoutePlanner)은 `create_app`에서 **한 번** 만들어 `app.extensions["naru"]`에 둔다. Model이 직접 자기를 등록하지 않는다 — 조립은 `app.py`만.
- 공간 연산은 Python에서 한다: `CrosswalkIndex`(Shapely STRtree, EPSG:5179), `PedGraph`(NetworkX 인메모리). MySQL은 결과 저장소. **MySQL 공간 함수(`ST_*`, `SPATIAL INDEX`)는 쓰지 않는다.**
- 도메인 결과는 `domain/types.py`의 frozen dataclass. **Model은 contracts 응답 타입(RouteResponse 등)을 만들지 않는다** — 그건 View 일. 입력 타입(RouteQuery, ClosureCandidate)은 받아도 된다.
- **DB**: MySQL 8.4, SQLAlchemy 2.x ORM(`Mapped[...]`, `mapped_column`) + **PyMySQL**, Alembic. Flask-SQLAlchemy 안 씀.
  - `db.py`가 엔진과 `sessionmaker`를 만들고, Repository가 생성자로 `sessionmaker`를 받는다.
  - Repository 공개 메서드마다 `with self._sessions.begin() as s:` — 짧은 세션, 메서드 하나 = 트랜잭션 하나. Controller·View는 세션을 모른다.
  - 컬럼 규칙: 시간 `DATETIME(0)` UTC, 좌표 `lng DECIMAL(10,7)`·`lat DECIMAL(10,7)` + 복합 인덱스 `(lng, lat)`(bbox는 `BETWEEN`), evidence처럼 문서형만 `JSON`, enum은 `VARCHAR(32)` + 앱 레벨 검증(MySQL ENUM 타입 안 씀).
  - `utf8mb4` / `utf8mb4_0900_ai_ci`, InnoDB, 서버 타임존 UTC (docker compose).

### 4.5 View
- 함수 모듈. `render(domain_obj) -> Response` 형태. 클래스 상태 없음.
- 도메인 객체 → **contracts 응답 모델 생성** → `jsonify(body.model_dump(mode="json"))`. contracts 모델을 거치므로 INTERFACE와 어긋나면 여기서 터진다.
- 시간은 여기서 `+09:00`로 변환, 한국어 라벨은 넣지 않는다(FE 몫).
- DB를 부르지 않는다. 추가 데이터가 필요하면 Controller가 Model에서 받아 넘긴다.

### 4.6 계층별 테스트
| 계층 | 테스트 | 입력 |
|---|---|---|
| Model | Flask 없이 순수 파이썬. **테스트 대부분이 여기** | `data/raw/` 실데이터, recorded 후보 |
| View | Model을 실데이터로 돌린 실제 출력 → `render` → 응답이 contracts로 `model_validate` 되는지 | Model 테스트 픽스처 재사용 |
| Controller | `create_app(test_settings).test_client()` — 실제 앱 인프로세스. 잘못된 요청 → 400, 토큰 없음 → 401 | 실데이터 + recorded 후보 |

- DB 테스트: compose의 실제 MySQL `naru_test`. 테스트 후 픽스처가 테이블을 `TRUNCATE`. SQLite로 대체 금지.
- 뷰·서비스를 patch하지 않는다.

## 5. FE — `packages/fe` — Next.js (App Router)

### 5.1 툴체인
- **Next.js(App Router)** + React 19 + TypeScript `strict: true`(+ `noUncheckedIndexedAccess`), **pnpm**. 메이저 버전은 T5.0 설치 후 ADR-006에 기록.
- 지도: **maplibre-gl 직접**(react-map-gl 같은 래퍼 안 씀). 배경 타일 VWorld.
- 린트: eslint CLI 직접 실행(`eslint-config-next` + `typescript-eslint` strict + `react-hooks`), prettier. 테스트 vitest + `@testing-library/react`(jsdom). e2e Playwright.
- `pnpm check` = `tsc --noEmit && eslint . && prettier --check . && vitest run`. `make check`가 이걸 부른다.

### 5.2 Next.js는 화면만
- **Route Handler(`app/api/*`), Server Actions, middleware에 비즈니스 로직 금지.** 백엔드는 Flask 하나다. 같은 로직이 두 곳에 생기면 계약이 깨진다.
- BE 호출은 **같은 오리진 `/api/*`** → `next.config.ts`의 `rewrites`가 Flask(`NARU_API_ORIGIN`)로 프록시. 브라우저는 Flask 주소를 모르고, CORS가 필요 없다.
- 운영은 `next start`(Node). static export는 rewrites가 안 되므로 안 쓴다.
- 환경변수: 브라우저에 노출되는 건 `NEXT_PUBLIC_VWORLD_KEY` 하나. `NARU_API_ORIGIN`은 서버 전용(`NEXT_PUBLIC_` 붙이지 않는다).

### 5.3 Server / Client 경계
- 기본은 Server Component. `app/layout.tsx`·`app/page.tsx`는 서버 — HTML 뼈대·메타데이터·푸터만.
- **`'use client'` 경계는 두 파일뿐**: `app/providers.tsx`(Provider 묶음)와 `components/NaruApp.tsx`(지도 화면 루트). Context·hooks·maplibre를 쓰는 코드는 전부 이 둘 아래.
- `MapView`는 `next/dynamic(() => import("../map/MapView"), { ssr: false })` — maplibre는 `window`가 필요하다. `ssr: false`는 클라이언트 컴포넌트 안에서만 쓸 수 있으므로 `NaruApp.tsx`에서 부른다.
- 서버 컴포넌트에서 BE를 fetch하지 않는다. 지도 데이터는 시각 `t`에 따라 클라이언트가 다시 받는다.

### 5.4 구조
```
packages/fe/
  next.config.ts                 # rewrites: /api/:path* → ${NARU_API_ORIGIN}/:path*
  src/app/layout.tsx             # (server) <html>, <Providers>, <Footer>
  src/app/page.tsx               # (server) <NaruApp />
  src/app/providers.tsx          # 'use client' — ApiProvider > TimeProvider > ClosureProvider > RouteProvider
  src/components/NaruApp.tsx     # 'use client' — 화면 루트, MapView dynamic import
  src/components/TimeSlider.tsx  LegList.tsx  EvidencePopover.tsx  Footer.tsx
  src/api/naruApiClient.ts       # fetch("/api/route"), fetch("/api/closures") — 네트워크 만지는 유일한 파일
  src/state/ApiProvider.tsx  TimeProvider.tsx  ClosureProvider.tsx  RouteProvider.tsx
  src/map/MapView.tsx  src/map/colors.ts
  src/map/layers/closureLayer.ts  routeLayer.ts  zoneLayer.ts   # 순수 함수
  src/i18n/ko.ts                 # enum → 한국어 라벨
  src/types/contracts.d.ts       # 생성물. 수정 금지
```
- 이름: 컴포넌트 `PascalCase.tsx`, 훅 `useXxx.ts`, 나머지 `camelCase.ts`. 컴포넌트당 파일 하나. Next가 요구하는 `page`·`layout` 외에는 named export만.
- 스타일: CSS Modules.

### 5.5 상태 — Context Provider
- 외부 상태 라이브러리 쓰지 않는다. **`createContext` + `useReducer`**.
- Provider를 관심사별로 **4개로 쪼갠다** (위 구조). 하나의 거대 Context 금지 — 슬라이더 한 칸 움직일 때 전 화면이 다시 렌더된다.
- 각 Provider는 **state Context와 dispatch Context를 따로** 만든다. dispatch만 쓰는 컴포넌트(TimeSlider)는 state가 바뀌어도 재렌더되지 않는다.
  ```tsx
  const TimeStateCtx = createContext<TimeState | null>(null);
  const TimeDispatchCtx = createContext<Dispatch<TimeAction> | null>(null);
  export function useTime(): TimeState {
    const v = useContext(TimeStateCtx);
    if (!v) throw new Error("TimeProvider 밖에서 useTime 호출");
    return v;
  }
  ```
- reducer는 순수 함수로 같은 파일 하단에 export → vitest로 단독 테스트.
- 비동기(fetch)는 reducer 밖, Provider 안의 `useEffect`에서. `t`가 바뀌면 `/api/closures`·`/api/route` 재요청, 이전 요청은 `AbortController`로 취소.
- Provider value는 `useMemo`. 컴포넌트는 `useContext`를 직접 부르지 않고 커스텀 훅만 쓴다.

### 5.6 지도와 React의 경계
- `MapView`가 `useRef`로 `maplibregl.Map` 하나를 보유. **레이어는 React로 다시 그리지 않는다.** Context 값이 바뀌면 `useEffect`에서 `map.getSource(id).setData(geojson)`로 명령형 갱신.
- GeoJSON 변환(`closureLayer.ts` 등)은 **순수 함수** — 입력은 contracts 타입, 출력은 MapLibre source/layer 스펙. FE 단위 테스트의 중심.
- React StrictMode의 이중 마운트에서 map이 두 번 생기지 않게 cleanup에서 `map.remove()`.

### 5.7 FE 테스트 — 실데이터 원칙 그대로
- 입력은 `data/recorded/naru_api/<endpoint>/<ts>.json` — `scripts/record_naru_api.py`가 **로컬에서 실제 Flask를 띄워** `/route`·`/closures`를 호출하고 응답을 저장한 것.
- **fetch를 가로채지 않는다.** `msw`, `vi.mock`, `vi.fn`, `vi.spyOn`, `jest.*`, `nock`, `sinon` 금지(check-no-fakes가 잡는다).
- 테스트 종류는 셋뿐:
  1. 순수 함수(레이어 변환, reducer, 라벨 매핑) ← recorded 응답
  2. 렌더 테스트: Provider **초기 state에 recorded 응답을 넣어** 클라이언트 컴포넌트를 렌더(네트워크 없음)
  3. e2e(Playwright): `make dev`로 실제 Flask(:5000) + `next dev`(:3000)를 띄우고 rewrites·`NaruApiClient`까지 끝에서 끝으로
- Server Component(`layout`, `page`)는 단위 테스트하지 않는다 — 얇게 유지하고 e2e로 본다.
- 하드코딩 GeoJSON·좌표 금지. 필요한 좌표는 recorded 응답에서 꺼낸다.

### 5.8 라벨·표기
- enum → 한국어는 `i18n/ko.ts` 한 곳: `scheduled: "예정"`, `confirmed: "확인"`, `released: "해제"`, `zone_scheduled: "예정 구역"`.
- 상태 색: scheduled 노랑, confirmed 빨강, released 회색, zone_scheduled 주황 음영. 색 상수는 `map/colors.ts`.

### 5.9 화면 목업 — `docs/mockups/`
- `01_home.html`(지도 홈: 통제 레이어·오늘의 통제 시간표·시간 슬라이더) · `02_route.html`(길찾기: 가장 빠른 길 / 원래 길(막힘·해제) / 계단 없는 길 카드, LegList) · `03_closure.html`(통제 상세: 해제 시각·근거·확신도·가까운 지하보도). 카카오맵 UI 톤.
- **따르는 것**: 화면 구성, 카드·탭·바텀시트 구조, 라벨 문구, 색(목업 CSS 변수 → `map/colors.ts`·CSS Modules로 옮긴다), 범례.
- **가져오지 않는 것**: 목업 안의 숫자·좌표·공지 문장·시각은 전부 예시다. 코드·테스트에 한 글자도 복사하지 않는다. 화면 데이터는 `/closures`·`/route`의 recorded 응답에서만.
- 목업의 지도는 모식도 SVG다. 실제는 maplibre + VWorld 타일. SVG를 옮기지 않는다.
- 목업과 계약(`contracts.d.ts`)이 다르면 계약이 맞다. 목업에 있는데 계약에 없는 필드(예: 혼잡도)는 화면에서 뺀다.
- 시작 메모에 "어느 목업의 어느 영역을 어느 컴포넌트로"를 한 줄씩 적고 시작한다.
