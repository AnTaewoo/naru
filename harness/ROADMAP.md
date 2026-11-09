# ROADMAP.md — Naru v1

진행 상태의 진실. Task `status`는 `TODO → DOING → DONE`. Claude가 시작할 때 `DOING`, 태우가 "다음"이라고 하면 `DONE`. ★ 경로에서 depends가 끝난 첫 TODO가 다음 Task다.
**PC(Prototype Check)** 는 태우가 직접 눈으로 확인하는 관문이다. "PC 통과"라고 해야 다음 Plan으로 간다.
한 번에 Task 하나. 절차는 `.claude/skills/task-cycle/SKILL.md`. 🧑는 사람이 하는 Task(Claude는 체크리스트까지만).

## 마일스톤
| | 날짜 | 내용 | 경로 |
|---|---|---|---|
| **M1 데모** | **2026-11-16** 최종 제출 (배포 링크·시연 영상·보고서·포스터), 11-21 본행사 | 광화문 일대, 기록된 공지 1세트(마라톤 코스 + 집회 공지) + 실시간 경로 계산 | P0 → P1 → P2 → P3 → P4 → P5 |
| M2 현장 실증 | 2027-03 서울국제마라톤 | 예측 통제 vs 현장 관측 | P6 → P7 |

**★ 11/16 경로**에 없는 Task는 하지 않는다. 11/16 전까지의 순서: P0(2일) → P1(2일) → P2(1일) → P3(2일) → P4(2일, P1~P3과 병행 가능 — AI 레인) → P5(3일). P5 뒤 P6 은 태우가 당겼다(2026-11-08 실서버 점검).
LLM은 ADR-007로 확정(Claude API). 로컬 사후학습·현장 데이터는 해커톤 이후(보류·P7). 버스는 확신도 보정(ADR-013)으로 P6 T6.2·T6.3.

---

## P0 — 세팅 · 실데이터 수집 ★

목표: 이후 모든 Task가 쓸 실데이터와 툴체인. 여기서 가짜 데이터의 싹을 자른다.

### T0.1 툴체인·계약 읽기 ★
- status: DONE
- depends: —
- 이미 있는 것: `pyproject.toml`(uv 워크스페이스), `packages/{contracts,ai,be}` 뼈대, **`naru_contracts` 코드**(INTERFACE v0.5의 구현), `.importlinter`, `Makefile`, `docker-compose.yml`, `.env.example`, hook·settings
- 할 일: `uv sync` → `uv.lock` 커밋. `make check`가 "테스트 0개"로 초록, `make layers` 계약 6개 KEPT. `docker compose up -d mysql` 후 `SELECT @@time_zone, @@character_set_server` = `+00:00`, `utf8mb4`
- Gate 시연 (선택 — 태우가 원하면. 보고에 결과 한 줄씩):
  1. `naru_be/models/x.py`에 `import flask` → `make layers` BROKEN
  2. `packages/be/tests/test_x.py`에 `pytest.skip` → `make check-no-fakes` 실패
  3. Claude에게 `data/recorded/`에 파일을 써 보라고 → 거부
  4. 루트에 `NOTES.md`를 만들어 보라고 → hook 거부
  5. 코드 파일과 `harness/progress.md`를 같이 커밋하라고 → hook 거부
  6. `git switch -c feat/x` → hook 거부 (develop에서만)
- 기록: 실제 설치 버전 → ADR-006 버전 표. 브랜치 develop. 하네스 파일이 git에 없으면 먼저 `harness: 하네스 v1` 커밋, 그다음 `T0.1: 툴체인`

### T0.2 서울시 공간 데이터 ★
- status: DONE
- depends: T0.1
- 실데이터: 서울 열린데이터광장 — 도보 네트워크(노드·링크), 교차로·횡단보도 위치, 지하도·육교·엘리베이터. **종로구·중구만** (광화문 데모 범위)
- 산출: `scripts/fetch_seoul_spatial.py`(`make fetch SRC=seoul_spatial`), `data/MANIFEST.md` 항목
- 테스트(실데이터): GeoPandas로 열어 행 수 > 0, WGS84, 횡단보도 파일에 교차로명·관리번호 컬럼 존재. 컬럼명은 **파일을 열어 확인한 뒤** 적는다

### T0.3 표준노드링크 (RoadGraph용) ★
- status: DONE
- depends: T0.1
- 실데이터: 공공데이터포털 표준노드링크, 서울 종로구·중구·영등포구 필터
- 산출: `scripts/fetch_nodelink.py`, MANIFEST
- 테스트: 노드 수 > 1,000, 링크에 도로명 컬럼 존재(컬럼명 확인 후)
- 용도: `SegmentGeom` → 선. 도로명 링크 제한과 등급(대로/로/길)은 도로명 문자열 접미사로

### T0.4 마라톤 코스·시각표 ★
- status: DONE
- depends: T0.1
- 실데이터: 2026 서울마라톤 코스(공식 GPX 없으면 지도에서 디지타이즈 — 방법을 MANIFEST에), 구간별 통제·해제 시각표(서울시·경찰 공지)
- 산출: `data/raw/course/seoul_marathon_2026.gpx`, `..._timetable.json`
- 테스트: 길이 42.195km ± 2%, 시각표 구간 ≥ 4

### T0.5 공지 문장 수집 ★
- status: DONE
- depends: T0.1
- 🧑 태우: 서울경찰청 '오늘의 집회' 첨부를 **매일** `data/raw/notices/smpa/<YYYYMMDD>.<pdf|hwp|jpg>`에. 과거분 확보 범위 확인
- 산출: `naru_ai/notice/source.py`(smpa PDF 표 → 문장 레코드, TOPIS 공지 API → 문장, 보도 문장은 naru-reader 수집본 import), `scripts/build_notices.py` → `data/raw/notices/sentences.jsonl`(`sentence_id, text, context_prev, context_next, source_type, source_url, published_at, fetched_at`)
- 테스트(실데이터): PDF 3개 파싱 행 수 = 태우가 센 수(plan에 기록), 모든 레코드에 출처 3종
- 주의: 문장을 다듬거나 지어내지 않는다. 이게 T4.x의 입력이다

### T0.6 라벨 정답 — 케이스 30개 🧑★
- status: TODO
- depends: T0.5
- 🧑 태우 혼자: Syntitan(큐빅 플랫폼)에 실제 공지 107행(경찰청 PDF 10일치·TOPIS 돌발·서울시 보도자료·기사) + 파서 규정을 올려 케이스 초안 30개를 뽑고, 원문 대조로 기대값 확정. 초안은 `data/recorded/syntitan/`, 확정본은 `data/raw/notices/cases_v1.jsonl`
- 케이스 형식: `{notice_id, source, text, event_date, published_at, source_url, type(정상|놓치기쉬움|거절), expected{window, kind, scope, segments[{from,to,via,road,direction,lanes}], points, reject_reason}}`. **좌표 없음**
- 배분: 정상 15 / 놓치기 쉬움 10 / 거절 5
- Claude: `scripts/check_cases.py` — 위 스키마 검증(필수 필드, type 3종·배분, segments 필드, 거절이면 reject_reason). 위반은 고치지 않고 목록으로
- DONE 조건: jsonl이 들어오고 스키마 검증 통과. **지금은 건너뛰고 PC-0 → T1.1** (2026-11-07 태우)

### T0.7 실제 API 응답 기록
- status: DONE
- depends: T0.1
- 산출: `scripts/record_api.py --api bus|incident|rtd|kakao` → `data/recorded/<api>/<ts>.json`. 카카오는 `숭례문`·`덕수궁` 키워드 1회씩
- 테스트: 기록 파일을 열어 확인한 필드 존재. 버스·돌발은 P6용이라 기록만(각 1회)

### PC-0 (태우)
- [ ] MANIFEST 항목을 전부 열어 본다. 출처 URL 클릭
- [ ] 횡단보도 파일에서 광화문 근처 5행을 직접 읽는다
- [ ] 코스 폴리라인을 folium으로 그려 세종대로를 지나는지 본다
- [ ] `sentences.jsonl` 20문장을 읽고 통제 문장 비율을 적는다
- [ ] 오늘의 집회 담당자 1명, 매일 저장 확인

---

## P1 — PedGraph · RoadGraph · CrosswalkIndex ★

### T1.1 PedGraph ★
- status: DONE
- depends: PC-0
- 산출: `naru_be/models/domain/ped_graph.py` — 도보 네트워크 → NetworkX. `edge.kind ∈ {sidewalk, crosswalk, underpass, overpass, stairs, elevator, station}`, `edge.crosswalk_id`
- 테스트(실데이터): 종로구·중구 그래프 노드·엣지 > 0, 최대 연결 성분 ≥ 80%, crosswalk 엣지 > 100
- 주의: 링크 유형코드 → kind 매핑은 코드표 파일을 열어 만든다

### T1.2 CrosswalkIndex — from_point · from_line · from_segment ★
- status: DONE
- depends: T1.1, T0.3
- 산출: `naru_be/models/domain/crosswalk_index.py`(STRtree, EPSG:5179), `naru_be/models/domain/road_graph.py`(표준노드링크 NetworkX, `shortest_path(points, road=None) -> LineString`), `naru_be/config.py` 상수: 점 반경 30m, 선 버퍼 15m, 등급별 버퍼 대로 25/로 15/길 8m
- 테스트(실데이터): (a) 코스 폴리라인 세종대로 구간 → 교차로명에 '세종대로' 포함 관리번호 ≥ 1 (b) `from_point(광화문광장 좌표, 30)` ≠ ∅ (c) `from_segment(숭례문 → 시청교차로, road=세종대로)` 결과에 세종대로 횡단보도가 있고 종로 횡단보도는 없다 — 좌표는 데이터에서 뽑고 주석
- 쪼개기: 200줄 넘으면 T1.2a(point·line) / T1.2b(RoadGraph·segment)

### T1.3 횡단보도 ↔ 교차로 매핑 ★
- status: DONE
- depends: T1.2
- 산출: `naru_be/models/domain/intersection_map.py` — 교차로명 → 관리번호 → 횡단보도 ID (정확 일치만. AI 리졸버가 같은 파일을 읽는다 — 공유 데이터, 코드는 각자)
- 테스트: 데이터에 있는 교차로명 하나 → 횡단보도 ≥ 2

### PC-1 (태우) — 통과 2026-11-07 ("다음 좋네", scripts/pc1_map.py)
- [x] 그래프를 folium으로 그려 광화문 일대 횡단보도 엣지 확인
- [x] `from_segment` 결과 선과 버퍼, 걸린 횡단보도를 같은 지도에

---

## P2 — 계약 테스트 · 상태기계 · 저장소 ★

### T2.1 naru_contracts 테스트로 고정 ★
- status: DONE
- depends: PC-1
- 산출: `packages/contracts/tests/test_interface_examples.py` — INTERFACE.md의 json 블록을 전부 뽑아 `model_validate`, `extra=forbid`, review 규칙(confidence<0.7), geometry 4종 왕복. `scripts/export_schema.py` + `make schema`
- 주의: 코드는 이미 있다. 이 Task는 읽기 + 테스트. 문서와 코드가 다르면 **문서를 고치지 말고** 태우에게

### T2.2 CourseIngestor (AI) ★
- status: DONE
- depends: T2.1
- 산출: `naru_ai/ingest/course.py` — GPX + 시각표 → `list[ClosureCandidate]`(geometry=line 구간별, status_hint=scheduled, confidence 0.9, evidence timetable)
- 테스트(실데이터): 후보 수 == 시각표 구간 수, window 일치. `scripts/record_candidates.py --source course` → `data/recorded/candidates/course/<ts>.json`

### T2.3 ClosureEngine ★
- status: DONE
- depends: T2.1
- 산출: `naru_be/models/domain/closure_engine.py` — `apply(candidate, crosswalk_ids) -> list[ClosureState]`, 전이는 ARCHITECTURE 표. 임계값 config
- 테스트(실데이터): T2.2 recorded 후보 → scheduled; 시각표 시작 시각 경과 → confirmed(코스는 시각표가 실측 증거); window 종료+30분 → released. BE 테스트는 naru_ai를 import하지 않는다

### T2.4 ClosureRepository (MySQL) ★
- status: DONE
- depends: T2.3
- 산출: `naru_be/db.py`, `models/entities/closure_state.py`, `models/repositories/closure_repository.py`, Alembic 1개
- 테스트: 실제 MySQL `naru_test`, TRUNCATE. upsert 후 `active_at(t, bbox)`가 T2.3 결과를 돌려준다. KST 입력 → UTC 저장 → KST 반환

### PC-2 (태우) — 통과 2026-11-07 ("다음", scripts/pc2_map.py)
- [x] 시각표의 통제 전·중·후 3시각에 폐쇄 횡단보도를 지도에

---

## P3 — 라우팅 · API ★ (Model → View → Controller 순서)

### T3.1 TimeDependentRouter ★
- status: DONE
- depends: PC-2
- 산출: `naru_be/models/domain/routers.py` — A*, 비용 = 거리 + 수직이동 패널티, confirmed 간선 제외, scheduled ×3, 간선 도착 시각으로 상태 판정
- 테스트(실데이터): 교보빌딩 앞 → 덕수궁 대한문, (a) 통제 없는 시각 경로 < 1.5km (b) 통제 중 `avoided`에 폐쇄 횡단보도, `legs.kind`에 underpass/overpass

### T3.2 BaselineRouter · RoutePlanner ★
- status: DONE
- depends: T3.1, T2.4
- 산출: `BaselineRouter`(같은 그래프, 통제 미적용), `route_planner.py` — `plan(query) -> RouteResult`(frozen dataclass)
- 테스트: baseline은 통제 전 경로와 동일, avoided에 Repository의 confirmed가 있다. Flask import 없음

### T3.3 View ★
- status: DONE
- depends: T3.2
- 산출: `views/{route_view, closure_view, error_view}.py`
- 테스트: 실제 RouteResult → render → `RouteResponse.model_validate` 통과, `+09:00`. `views-no-db` KEPT

### T3.4 Controller · app factory · candidate_controller ★
- status: DONE
- depends: T3.3
- 산출: `app.py`(`create_app`), `controllers/{_deps, route_controller, closure_controller, candidate_controller}.py`, `models/domain/candidate_intake.py`(batch_id 멱등, geometry kind별 CrosswalkIndex 분기)
- 테스트: `test_client()`로 실제 그래프·실제 폐쇄 호출 → contracts 검증. 오프셋 없는 `depart_at` → 400. recorded course batch POST → 202, 재전송 → 변화 없음, 토큰 없음 → 401
- 추가: `scripts/record_naru_api.py` → `data/recorded/naru_api/` (FE 테스트 입력)
- 쪼개기: T3.4a(route·closures) / T3.4b(candidates)

### PC-3 (태우) — 통과 2026-11-07 ("다음", data/recorded/naru_api/route_0745·route_1330)
- [x] 로컬 API 띄우고 curl로 `/route` 통제 전·후 두 응답을 지도에 — 이 그림이 포스터에 들어간다

---

## P4 — 공지 파서 (Claude API) ★ (AI 레인 — P1~P3과 병행 가능, 담당이 다르면)

### T4.1 AnthropicClient · recorder · 프롬프트 v1 ★
- status: DONE
- depends: T0.5, T2.1
- 산출: `naru_ai/llm/client.py`(tool use, `input_schema`·`tool_choice` — 쓰는 SDK 문서를 열어 파라미터명 확인·주석), `naru_ai/llm/recorder.py`, `llm/prompts/notice_v1.md`(few-shot 8문장은 `sentences.jsonl`의 id로. **`prompts/notice_v1.md`는 규칙서 `docs/data/notice_parser_rules_v2.md` §1~§5·§9에서 생성하고, 출력은 §9.1의 `items[] / impact / impact_reason / toward / approx` 스키마**. 기대값은 `data/raw/notices/cases_v1.jsonl`(T0.6) 기준), `scripts/record_llm.py`(`make record-llm`)
- 실데이터: live 3문장 → recorded. 비용 예상을 시작 메모에
- 테스트(재생): 응답이 `spans`·`segments` 스키마 통과. recorded `model`·`prompt_version` ≠ 설정 → fail

### T4.2 NoticeParser · Resolver · CandidateBuilder ★
- status: DONE
- depends: T4.1, T1.3, T0.7
- 산출: `notice/parser.py`(호출·재생 → 정렬기 start/end → segments 검증), `notice/gazetteer.py`·`notice/resolver.py`(교차로·도로명·카카오 기록), `notice/candidates.py`(segment 양 끝 풀림 → `SegmentGeom`, 아니면 `PointGeom`; confidence 규칙: 출처 종류 + 시간 명시 여부)
- 테스트(실데이터): recorded 응답 1건 → 후보 ≥ 1, `SegmentGeom.from_.lng`가 카카오 기록 좌표와 일치, 못 푼 정규형은 후보 없음(추측 좌표 0). `scripts/record_candidates.py --source notice`
- 쪼개기: T4.2a(parser) / T4.2b(resolver) / T4.2c(builder)

### T4.3 평가 — 규칙 기준선 vs Claude ★
- status: DONE
- depends: T4.2, T0.6
- 산출: `notice/rule_baseline.py`(지명사전·별칭 일치 + 시간 정규식), `notice/eval.py` — 입력 둘로 나눠 평가: **정확도** = `data/raw/notices/cases_v1.jsonl`(실제 공지 34건, T0.6) · **견고성** = `data/recorded/syntitan/agent_questions.csv`(합성 163건). 통과 기준은 규칙서 §7·§9.3(window 분 단위·impact·items 수·segments 순서·toward·approx ±10분), 정규형 F1·구간 F1·횡단보도 Jaccard, type별(정상/놓치기쉬움/거절) 정확도, 케이스 단위 부트스트랩 CI, `make record-llm`으로 val 문장 전부 기록, `docs/eval/notice_<date>.md` 결과 표
- 테스트: 정답을 예측으로 넣으면 F1 = 1.0. 정렬기 왕복
- **이 표가 보고서 2.3 "AI가 필요한가"의 숫자다.** 임계값(review 0.7 등)은 결과 보고 태우가 정한다

### T4.4 IngestWorker · CandidatePublisher ★
- status: DONE
- depends: T4.2, T3.4
- 산출: `worker.py`(스케줄 공지 5분·코스 1회, `--once` 플래그로 시연용 1회 실행), `publish.py`(httpx POST, 3회 재시도)
- 테스트: e2e — `make dev` + `python -m naru_ai.worker --once` → BE `/closures`에 공지 후보 반영 확인

### PC-4 (태우) — 통과 2026-11-08 ("다음". 임계값 review 0.7·confirmed 0.8·모델 haiku-5-5/notice_v2 유지, Sonnet 비교·ADR-007 추가는 보류)
- [x] 평가 표(규칙 vs Haiku vs Sonnet)를 읽고 review 임계값·모델을 정한다 → ADR-007에 추가
- [x] 기록된 집회 공지 1건이 지도에 segment 선 + 횡단보도로 나오는 걸 본다 (API: /closures 광화문 15:30 → 37개)

---

## P5 — FE · 배포 ★ (CONVENTIONS §5)

### T5.0 Next.js 스캐폴드 ★
- status: DONE
- depends: T3.4
- 산출: `packages/fe` (App Router, React 19, TS strict, pnpm, eslint+prettier, vitest, Playwright), `next.config.ts` rewrites(`/api/:path*` → `NARU_API_ORIGIN`, `/internal/*` 제외), `app/{layout,page,providers}.tsx`, `make schema` → `src/types/contracts.d.ts`, `make check`에 `pnpm check` 연결
- 테스트: `pnpm check` 초록, `contracts.d.ts`에 `ClosureCandidate`·`RouteResponse`, `make dev`로 rewrites 확인

### T5.1 MapView + 통제 레이어 + 시간 슬라이더 ★
- status: DONE
- depends: T5.0
- 산출: `components/NaruApp.tsx`, `map/MapView.tsx`(maplibre `useRef`, VWorld 타일), `state/{Time,Closure}Provider.tsx`, `map/layers/closureLayer.ts`(confirmed 빨강 ×, scheduled 노랑, zone 보라 빗금, 지하보도 입구 파랑), `components/TimeSlider.tsx`, `i18n/ko.ts` — 화면 구성은 `docs/mockups/01_home.html`(CONVENTIONS §5.9)
- 테스트: recorded `/closures` → closureLayer feature 수·색 일치. reducer 단독. TimeSlider는 closures state 변경에 재렌더 안 됨

### T5.2 길찾기 — RouteProvider + 경로 레이어 + 카드 ★
- status: DONE
- depends: T5.1
- 산출: `state/RouteProvider.tsx`, `map/layers/routeLayer.ts`(route 파란 실선, underpass 구간 남색, baseline 회색 점선), `components/{RouteCard,LegList,EvidencePopover}.tsx` — `docs/mockups/02_route.html`·`03_closure.html`의 카드·탭·바텀시트 구조 그대로(CONVENTIONS §5.9): 가장 빠른 길 / 원래 길(막힘·해제 시각) / 근거·확신도
- 테스트: recorded 통제 중 `/route` → 카드 숫자·LegList 라벨이 응답과 일치

### T5.3 배포 · e2e · 시연 영상 ★
- status: DONE
- depends: T5.2, T4.4
- 산출: Flask + AI 워커 `--once`(홈서버, 기록 재생) + Next.js 배포(Vercel 또는 홈서버) → **배포 링크**. Playwright e2e: 교보빌딩 앞 → 대한문, 통제 중 시각 선택 → 우회 경로·지하보도 레그. 시연 영상 스크립트 `harness/plans/active/demo_script.md`
- 산출(고지, 태우 2026-11-08): 지도 attribution(VWorld 키 전까지 OSM "© OpenStreetMap contributors") + `/licenses` 페이지 — maplibre-gl(BSD-3-Clause, LICENSE.txt 의 MapLibre·Mapbox 저작권 고지 전문) 등 오픈소스 고지
- 🧑 태우: 영상 촬영, 포스터 A0, 보고서 결과 칸 채우기(T4.3 표, 사용성 테스트)

### T5.4 통제 불러오기 ★ (태우 2026-11-08)
- status: DONE
- depends: T5.3
- 산출: BE `GET /closures/events`(ADR-010, INTERFACE v0.8 §3.1 — DB 통제를 (사유, 창) 사건으로 묶어 창·횡단보도 수·범위), FE 하단 시트 "통제 불러오기"(날짜별 목록 → 누르면 그 시작 시각·그 범위로, 지금 통제가 없으면 빈 칸에 안내 버튼), 슬라이더 "지금", 시트 제목 날짜("3월 15일 통제"). 공개 반영은 태우(tmux `make serve` 재시작)
- 테스트: naru_test 코스 상태로 사건 API, recorded `closure_events.json` → 날짜 묶음·렌더, e2e 홈(지금, 통제 0) → 불러오기 → 3/15 → 길찾기 지하보도 우회 → 지금

> T5.5~T5.10·T6.1·T6.4~T6.8(ADR-013 버스 T6.2·T6.3 이 끼어 한 번 더 밀림) — 태우가 naru.antaewoo.com 을 실제로 눌러 보고 실서버 API 를 직접 불러서 나온 문제(2026-11-08). 결정 A–E 는 ADR-011. 순서대로 Task 하나씩 → 보고(iPhone 13 크기 스크린샷 1장) → "다음". 붙여 준 번호 T5.4~T5.9 는 한 칸씩 밀었다(T5.4 는 통제 불러오기, 태우 결정)

### T5.5 라우터 정확성 ★ (최우선)
- status: DONE
- depends: T5.4
- 산출: 결정 A — scheduled 통제는 횡단보도에 닿는 시각이 공지 창 안일 때만 횡단보도당 +300초 페널티(상수, 하드 차단 아님), 창 밖은 보통 간선이고 "예정 ×3"은 없앤다. confirmed 는 지금처럼 차단. avoided[] 의 status 로 FE 가 confirmed "통제 중" / scheduled "공지상 통제 시간 · 현장 확인 전"을 나눈다. 상태기계는 그대로, 라우터 비용만. 그래프 밖 좌표: 그래프에 붙일 때 거리 상한 150 m(상수), 넘으면 `out_of_coverage`(지금은 먼 노드에 붙여 엉뚱한 경로)
- 테스트: 회귀 3개로 고정 — ① from=37.5133,127.0980 to=37.5145,127.1035 depart_at=2026-03-15T10:00+09:00 → OUT_OF_COVERAGE(지금 16.9 km·14,118초) ② 11/7 15:00 세종대로 건너기 37.56368,126.97230 → 37.56368,126.98193 → 우회 생김, avoided 에 scheduled ③ 3/15 07:45 광화문 37.57148,126.97475 → 37.57148,126.97982 → 지금처럼 광화문 지하보도

### T5.6 하단 시트 + 지도 맞춤 ★
- status: DONE
- depends: T5.5
- 산출: 손잡이를 pointer 이벤트로 드래그(touch-action: none, user-select: none — 지금은 끌면 글자만 선택된다). 단계 3개: 접힘(약 96px) / 절반 / 전체, 놓으면 가까운 단계로. 손잡이 탭은 접힘↔절반. 경로를 찾으면 시트를 접힘으로 내리고 경로 전체에 fitBounds(padding 위 = 검색창, 아래 = 시트 높이 — 지금은 지도가 140px 띠로 줄고 경로가 화면 밖). 이벤트를 누르면 그 이벤트 횡단보도 전체에 fitBounds(지금은 서울 전체로 줌아웃되고 지점이 시트 뒤에 가려짐). 모바일에서 하단 푸터 숨김(지도 attribution 에 고지 링크가 이미 있음), 지도 로딩 중 회색 대신 로딩 표시

### T5.7 내 위치 ★
- status: DONE
- depends: T5.6
- 산출: maplibre GeolocateControl + 출발 기본값 "내 위치"(거부·실패 시 지도 탭). 출발·도착 칸 옆 "내 위치" 버튼. 커버리지 밖이면 안내

### T5.8 주소·검색 ★ (결정 B)
- status: DONE
- depends: T5.7
- 산출: 지도 탭으로 고른 점은 `/geocode/reverse` 로 도로명 주소 표시, 좌표는 화면에 안 보이게, 실패 시 "선택한 위치". 출발·도착 칸을 진짜 입력칸으로 — 2글자 이상, 300ms 디바운스로 `/geocode/search`, 결과에서 고르면 칸에 들어감. 맨 위 검색창 결과마다 "출발" "도착" 버튼
- 테스트: `data/recorded/kakao/` 재생

### T5.9 통제 목록 ★
- status: DONE
- depends: T5.8
- 산출: 제목은 원문 대신 파서 결과로 — "시의회~숭례문오거리 집회 → 광화문·고용노동청 행진", 둘째 줄 "5만 명 · 태평로". 원문은 상세의 "공지 원문 보기". 이벤트 횡단보도 수는 화면 영역 말고 이벤트 전체 기준(지금은 지도를 옮기면 31곳→20곳). "오늘 통제"는 오늘일 때만, 아니면 "3월 15일 통제". "지금" 배지는 실제 오늘·현재 시각일 때만. 다가오는 것 먼저, 지난 건 "지난 통제" 묶음. 목록 위에 data_as_of "TOPIS 13:25 · 경찰청 11/8 공지 기준", 30분 넘게 안 바뀌었으면 회색 경고(결정 C)

### T5.10 경로 상세 ★
- status: DONE
- depends: T5.9
- 산출: legs 횡단보도에 이름 — 횡단보도 데이터 열을 열어 보고 교차로·위치명이 있으면 그걸로, 없으면 도로명. 있는 열만 쓴다. 경로가 하나면 위쪽 "11분 가장 빠른 길" 탭 줄 숨김

### T5.11 원래 길 보기 ★ (태우 2026-11-08)
- status: DONE
- depends: T5.8 (태우 "15분 1.0km 카드 아직 안 눌린다" — T5.8 고침과 함께 지금)
- 산출: 통제로 원래 길을 피했을 때 "원래 길" 카드도 누를 수 있게 — 누르면 원래 길을 고른 상태: 지도에 원래 길 실선(가장 빠른 길은 흐리게), 원래 길이 지나는 통제 횡단보도(avoided 의 crosswalk_id ↔ 같은 시각 /closures 점)를 크게 강조 — 통제 중 빨강, 공지상 통제 시간 주황. 가장 빠른 길 카드를 누르면 돌아온다. 계약은 그대로(태우 결정 "계약 그대로, FE만") — 막힌 구간을 선으로 칠하지는 않는다
- 테스트: recorded route_0745(통제 중 2곳)·route_1107_1500(공지상 1곳) 렌더, e2e iPhone 13

### T5.12 지도 출처 칸 줄이기 ★ (태우 2026-11-08)
- status: DONE
- depends: T5.10 (태우 "OSM 오픈소스 고지 숨기면 안 되나 — 사용에 불편" → 고쳐 (a))
- 산출: 지도 출처 칸은 "© OpenStreetMap contributors" 한 줄만. 숨기기·ⓘ 접기는 안 된다 — OSMF 타일 정책 §2 "Do not hide attribution beneath UI, behind toggles, or off-screen"(2026-11-08 원문 확인, OSM 타일을 쓰는 동안). "오픈소스·데이터 고지" 링크는 하단 시트 맨 아래 줄로(모바일, 펼쳤을 때만), 데스크톱은 푸터 그대로. P6 마감의 VWorld 타일로 바꾸면 그때 표기 조건을 다시 본다
- 테스트: e2e — 출처 칸 글자, 시트 링크 → /licenses, 접힘에선 링크 없음, 데스크톱 푸터 링크

### PC-5 (태우) — 통과 2026-11-08 ("PC 통과". 11/16 제출)
- [x] 배포 링크에서 라이브로 경로가 나온다 (외부 API 호출 없이)
- [x] 시연 영상, 포스터, 보고서, 레포 공개 확인
- [x] 사용성 테스트 5명 결과가 보고서 1.2·2.4에

---

## P6 — 운영 워커·실시간 신호 (태우 2026-11-08: 실서버 점검 뒤 당김)

> 순서(태우 2026-11-08): T6.1 → T6.2 → **T6.4 → T6.6**(11/13(금) 18:00 전 운영) → T6.3 → T6.5 → T6.7 → T6.8. 번호는 그대로 두고 블록만 이 순서로 놓았다

### T6.1 워커 상시 실행 + TOPIS 실시간 돌발
- status: DONE
- depends: T5.10
- 계기(실서버 확인): `/api/closures/events` 가 7건뿐(11/7 집회 2, 3/15 마라톤 5구간), 11/8 서울 전체 0건. `make serve` 의 워커가 `--once` 로 기록 5건만 재생(live 0)하고 끝난다
- 산출: `naru_ai.worker --loop` — 소스별 주기 실행, 한 소스 실패가 다른 소스를 안 막음, 연속 3회 실패면 ERROR 로그. batch_id 는 원문 해시(같은 내용이면 멱등). 첫 소스: OA-13315 5분마다 → 원문 기록(결정 E) → IncidentIngestor → POST /internal/candidates. 기존 notice 후보와 같은 링크·시간이면 confirmed 증거로 붙는지 확인. `deploy/naru-worker.service`(naru.service 와 같은 형식: User=antaewoo, WorkingDirectory, PATH 에 uv 경로, ExecStart=uv run python -m naru_ai.worker --loop, Restart=on-failure). 설치 명령은 보고에 적는다. `make serve` 에서는 워커를 안 띄운다(서비스 분리)
- 🧑 태우: 서비스 설치

### T6.2 버스 관측 수집 (ADR-013, 태우 2026-11-08)
- status: DONE
- depends: T6.1
- 계기: 버스 신호를 "2대 이탈 → 통제 중 / 정상 통과 → 해제" 이진 규칙에서 기존 통제의 확신도 보정으로 바꾼다(태우 제안, ADR-013 — T6.1 시작 때 커밋). 테스트는 통제일의 실제 버스 기록이 있어야 하는데 지금은 11/7 예시 노선 스냅샷 1장뿐이고 지난 날 위치는 못 받는다 → 수집부터 당겨 다음 통제일부터 기록
- 산출: 노선 마스터 — 정류소 순서는 열린데이터광장 OA-1095(`make fetch SRC=bus_routes`), 노선 경로는 노선정보 API getRoutePath(노선당 하루 한 번 `bus_routes/<날짜>/path_<노선>.json`(raw), 도로 그래프로 정류소 잇기 금지 — 태우 2026-11-08). 계약 `BusPosition`·`BusPositionBatch`(API 필드 그대로, 판단 없음) INTERFACE v0.13. AI `naru_ai/signal/bus_feed.py`·`bus_poller.py` — 1순위 공지 통제(시작 1시간 전 ~ 끝+30분, 통제 횡단보도 100 m 안 노선 3개, 60초, 쿼터 먼저), 2순위 TOPIS 집회·행사 돌발(기준 데이터 — 돌발마다 노선 1개, 120초, 하루 300·돌발 하나 30, 공지가 쓰고 남은 만큼), 원문은 `bus/notice/`·`bus/incident/`(recorded), 전체 하루 900. BE `POST /internal/bus-positions` → `BusIntake` → `bus_positions`(Alembic 0004, `bus_corrections` 는 T6.3)
- 테스트: 평일 실제 기록(Task live ≤10, 광화문 노선)으로 파싱·배치·적재
- 🧑 태우: 노선정보 API(data.go.kr 15000193) 활용신청 — 2026-11-08 getRoutePath 가 HTTP 401 "등록되지 않은 서비스키". 워커 재시작. 마라톤·M2 는 운영계정 상향

### T6.4 TOPIS 통제 공지 게시판
- status: DONE
- depends: T6.2 (태우 2026-11-08 — 11/13(금) 18:00 전 운영)
- 산출: https://topis.seoul.go.kr/notice/openNoticeList.do 를 10분마다(robots 허용 확인됨: /visit/, /map/openTotalMap.do 만 금지). 새 글만 → 원문 기록 → notice_v2 live 파싱(결정 D) → 후보 발행. 기존 N045·N046 문장이 이 게시판 형식이다 — 파싱 결과가 cases 와 같은 형식인지 확인
- 결과(2026-11-08): 원문은 게시판과 최신 글이 같은 열린데이터광장 NoticeList(OA-22861, 키) — 웹은 안 긁는다. 글 하나 = 문장 하나(`topis-<번호>-u<고친 시각>`), 한 번 10·하루 200 live. N045·N046 은 게시판이 아니라 돌발(AccInfo) 형식이었다

### T6.6 경찰청 PDF inbox
- status: DONE
- depends: T6.4 (태우 2026-11-08 — 11/13(금) 18:00 전 운영)
- 산출: smpa 는 robots.txt 가 막혀 있어 자동 수집 안 한다. `data/raw/notices/smpa/inbox/` 에 태우가 PDF 를 넣으면 워커가 새 파일을 감지 → 표 추출 → notice_v2 live 파싱 → 후보 발행 → 처리한 파일은 `data/raw/notices/smpa/<날짜>.pdf` 로 옮기고 MANIFEST 갱신
- 결과(2026-11-09): inbox → 행마다 notice_v2(TOPIS 와 같은 상한) → 후보 → `smpa/<집회 날짜>.pdf` 로 옮기고 `smpa/inbox_manifest.jsonl`(git 밖) 한 줄. 행 ID 에 기준 작성 버전, 후보 ID 는 버전 없이. 같은 파일은 `inbox/duplicate/`, 표가 아니면 `inbox/failed/` — 지우지 않는다

### T6.3 버스 확신도 보정 (ADR-013)
- status: 보류
- 보류(태우 2026-11-09): ADR-013 보류 — 11/9 실측(docs/eval/bus_20261109.md: 1개 차로 행진 시간 안에 버스가 구간을 124회 경로대로 지나감, 무정차 0, 경로 60 m 이탈 0). 엔진·라우터의 버스 경로 삭제('통제 중' 근거 = 시간표 + TOPIS 돌발), `bus_corrections` 안 만듦, 보정 순수 함수 뺌(`RoutePath` 만 남김), 버스 폴러는 전면 통제·마라톤 기록만(`NARU_BUS_RECORD_ONLY=1`). 다음은 T6.8
- depends: T6.6 (태우 2026-11-08 순서: T6.4 → T6.6 → T6.3)
- 산출: BE `bus_correction.py` — 통제 구간(같은 후보의 횡단보도 묶음)마다 최근 20분 관측으로 항목(서로 다른 2대 이상이 15분 안에 피해 감 +0.20·구간 정류소를 2대 이상 건너뜀 +0.10·통과 시간이 평소 2배 초과 2대 이상 +0.10·1대만 피해 감 +0.05·2대 이상 정상 통과 −0.30) → 합 [−0.30, +0.25] → 최종 clamp(공지 + 보정, 0, 0.95). 보정은 시각의 함수(at 기준, 저장값 = base_confidence), bus_skip 은 20분 안에서만 확인 근거, 정상 통과 −0.30 이 20분 간격으로 2번이면 끝 시각 전 해제(bus_return), impact unknown 승격 후보는 지점 30 m 안 노선에서 2대 이탈일 때만 0.65 위로. /closures `confidence` 는 보정 후, `base_confidence` 추가, EvidenceKind `bus`, INTERFACE v0.14. `/route` 는 depart_at 보정으로(0.7 이상·창 안이면 +300초, 0.8 이상 + bus_skip·시작 뒤면 제외, 0.7 아래·해제면 보통). FE 통제 근거 "버스 2대가 16:02·16:06에 세종대로 구간을 피해 감 +0.20 → 확신도 0.95". README 확신도 절. 규칙서(파서 확신도)는 그대로(태우 결정). 이탈 60 m·보정값은 2순위 돌발 기록(`bus/incident/`, 실제로 막힌 구간의 버스 움직임 = 정답)으로 실측 맞춤. 노선 경로는 getRoutePath(도로 그래프 잇기 금지). `bus_corrections` 표(Alembic)
- 테스트: 순수 함수(합·clamp·20분 창·상한·해제 순서)는 실데이터 상수로, 감지 부품은 평일 기록으로, 통제일 통합은 그날 기록으로 — 없으면 "실측 대기"로 보고하고 멈춘다

### T6.5 추가 소스 확인 (구현 말고 보고만)
- status: DONE
- depends: T6.3
- 산출: 각각 한 번만 호출해서 응답 구조·서울 도심 집회 포함 여부·좌표 유무·라이선스를 표로 보고. 쓸지는 태우가 정한다 — TOPIS 통제지도 https://topis.seoul.go.kr/map/openControlMap.do 가 내부적으로 부르는 AJAX 엔드포인트와 응답(좌표가 있는지), 서울 실시간 도시데이터 OA-21285 의 사고통제현황(OA-13315 와 중복인지), 경찰청_교통돌발정보서비스(data.go.kr 15088841 — 서울 도심 집회가 나오는지, 고속도로·국도뿐인지)
- 결과(2026-11-09): TOPIS 교통통제 지도 내부 AJAX(목록·통제 도로·링크 꼭짓점)가 예정 통제를 시작 전에, 행진 경로를 링크 순서로 준다(11/9 행진 1109233 — 통제 도로 19개, 세종대로사거리→광화문 포함). 공개 API 아님 — 쓸지는 태우(쓰면 ADR). OA-21285 사고통제현황은 OA-13315 를 장소 하나로 자른 것, 15088841 은 고속도로·국도 + 별도 키·IP

### T6.7 커버리지 확장 판단 (보고)
- status: DONE
- depends: T6.5
- 산출: 서울 전체 도보망+노드링크 그래프의 적재 시간·메모리·/route 응답 시간을 실측해서 보고(홈서버 32GB). 적재 60초·4GB 이내면 전체로, 넘으면 도심+마라톤 코스 주변 버퍼 — 숫자 보고 태우가 정한다. 마라톤 15구간 중 5구간만 들어간 것도 이것 때문인지 확인
- 결과(2026-11-09): 서울 전체(중랑구 빼고 24개 구) 적재 13초·최대 1.5 GB(워커당), 마라톤 16구간 전부 횡단보도. 태우 결정 "서울 전체로 간다" → T6.9

### T6.9 서울 전체 범위 (태우 2026-11-09 — 오늘 통제일, 국회대로·강남대로 집회가 버스 1순위에 들어가야)
- status: DONE
- depends: T6.7
- 산출: ① OA-23081 좌표가 빈 행은 로더에서 건너뛰고 `skipped N rows (missing coords)` WARNING(06-0000023497 실제 행으로 테스트) → 25개 구 전부. ② 테스트 갱신 — OUT_OF_COVERAGE 회귀는 서울 밖(경기 성남 37.3947,127.1112 → 37.3960,127.1150), 잠실 요청은 정상 경로 테스트(길이 600 m 근처인지), 코스 183곳·돌발 16곳 같은 기대값은 데이터를 다시 열어. ③ /route 응답 시간을 서울 전체로 다시(회귀 경로들 p50/p95) — p95 > 1초면 A*(직선거리 휴리스틱). ④ 버스 폴링(하루 900): 1순위 = 확신도 0.45~0.8 공지 통제(그 안에서 신고 인원 많은 순·시작 가까운 순), 0.85 이상은 남는 쿼터로만, TOPIS 돌발 기준 데이터(하루 300)는 그대로. ⑤ 통제 불러오기: 날짜별 묶음, 오늘·다가오는 것만 펼침·지난 건 접힘, 위에 구 필터 칩(지도 화면 안의 구 먼저). ⑥ 범위 문구: 화면 coverage, README "종로구와 중구(광화문 일대)만" → "서울 전체", ARCHITECTURE 에 그래프 크기·적재 시간·메모리(워커당). 배포 끝나면 naru-worker 재시작 명령을 보고에
- 🧑 태우: 오늘 경찰청 PDF 를 inbox 에. 16:00 뒤 버스 기록(bus/notice·incident)을 열어 이탈·무정차·정상 통과 확인 → 찍혔으면 T6.3 실측 대기 풀기

### T6.8 마감
- status: DONE
- depends: T6.9
- 산출: VWorld 키 넣으면 타일 교체(그 전까진 OSM). docker-compose MySQL 포트 127.0.0.1:3307:3306. 2026 JTBC 서울마라톤(11/1) 교통통제 안내(news.seoul.go.kr)로 코스 시각표 추가 가능한지 보고 — 3/15 보다 최근이라 시연용

### P6 이후 (해커톤 이후, M2)
버스 운영계정 상향(🧑 태우, 마라톤·M2 전). 버스 확신도 보정(ADR-013)은 보류 — 2027년 3월 서울마라톤에서 버스 정류소 건너뜀으로 구간별 실제 통제·해제 시각을 확인한다(폴러 기록 + `RoutePath`). (IncidentIngestor 는 T6.1 로 당김)

## P7 — 실시간 통제 지도 · PWA 알림 (태우 2026-11-09, ADR-014)
> 계획 `harness/plans/active/P7_plan.md`(정할 것 15개는 추천안 그대로 — 태우 "다음" 2026-11-09 17:05). A(T7.1~T7.6)는 11/16 최종 제출 전, B(T7.7~T7.10)는 그다음. Task 마다 보고에 실제 앱 화면 iPhone 13 스크린샷 1장. 알림 발송은 태우 PC Chrome·폰 실제 구독으로 확인(가짜 엔드포인트 없음)

### T7.1 BE 사건 API v2 — id·상태·시간 창·ETag
- status: DONE
- depends: T6.9
- 산출: `GET /closures/events?at=&from=&to=(&bbox=)` — 사건 `id`(sha1(reason·시작·끝) 12자), `status`(at 기준 가장 심한), `confidence`(최대), 기본 창(진행 중 + 내일 24:00 KST), 300건 상한(`truncated`), ETag/304. 파라미터 없으면 지금처럼. 계약 v0.14(`area`·`centroid` 는 T7.2 까지 null)

### T7.2 BE 통제 구역 — 사건 area·centroid
- status: DONE
- depends: T7.1
- 산출: 접수 때 후보 모양(구간 경로 + 등급 버퍼, 선 15 m, 점 30 m)을 사건 단위 union → 5 m 단순화 → `area`·`centroid`, 표 `closure_events`(Alembic 0005)

### T7.3 TOPIS 통제지도 예정 통제 소스 (T6.5)
- status: DOING
- depends: T7.1
- 산출: 목록·통제 도로 AJAX 10분(ADR-011 E) → 예정 통제 후보(링크 순서 경로, 꼭짓점 OA-13311, 후보 ID = 돌발과 같은 acc_id, 예정 근거는 공지처럼 0.85, 전체 통제는 버스 기록 대상)

### T7.4 FE 실시간 지도 — 줌 3단계·칩 필터·60초 갱신
- status: TODO
- depends: T7.2
- 산출: 앱 열면 서울 전체 사건 — 클러스터(< 12)·구역(12~15)·횡단보도(≥ 15), 상태 5종, 칩 = 필터, 60초 ETag, data_as_of. "통제 불러오기"·빈 상태 삭제. 성능 측정 보고

### T7.5 FE 시트 — 지금 서울 통제·사건 카드
- status: TODO
- depends: T7.4
- 산출: "지금 서울 통제"(통제 중 → 1시간 안 → 오늘 → 내일, 구 칩 유지), 사건 카드(원인·제목·시각·상태·남은 시간·출처·확신도 3단계·횡단보도 수·버튼 셋), 클러스터 목록, `?event=<id>`

### T7.6 날짜 선택·3/15 회귀·이 구역 피해서 길찾기
- status: TODO
- depends: T7.5
- 산출: 슬라이더 날짜 선택, `?t=` 3/15 07:45 공유 링크 회귀 e2e, `/route?avoid=<id>`(그 사건 무조건 막음, 계약 v0.14)
- PC-7A (T7.6 뒤): 태우가 운영 화면으로 실시간 지도 확인 — "PC 통과"면 B

### T7.7 PWA 기반 — manifest·서비스워커·iOS 안내·권한 버튼
- status: TODO
- depends: T7.5
- 산출: `app/manifest.ts`, `public/sw.js`(push → 항상 showNotification, 클릭 → `/?event=`), iOS 16.4+ 홈 화면 안내, 권한은 버튼으로만. Provider 추가 안 함

### T7.8 BE 구독·관심 지역 API
- status: TODO
- depends: T7.7
- 산출: `GET /push/vapid-public-key`, `POST·DELETE /push/subscribe`, `GET·POST·DELETE /watch-areas`(saved 300·500·1000 m, last_seen 150 m 격자·3시간), 표 셋(0006). 🧑 태우: VAPID 키(.env). 구독 테스트 입력 = 태우 실제 구독을 가린 기록(`{D}/recorded/push/`)

### T7.9 매칭·발송
- status: TODO
- depends: T7.2, T7.8
- 산출: created·confirmed → blocks·≥ 0.7 → STRtree → (구독, 사건, 종류) 한 번 → 22~07 created 는 07시 → pywebpush(410·404 끔). 워커 `push` 60초 → `POST /internal/push/dispatch`

### T7.10 알림 → 카드, ☆ 이 근처 알림 받기, 관심 지역 관리
- status: TODO
- depends: T7.9
- 산출: 알림 클릭 → 사건 카드, 카드 ☆(중심 반경 500 m), 관심 지역 목록·삭제, last_seen. 운영에서 태우 실제 구독으로 끝에서 끝
- PC-7B (T7.10 뒤): 태우 PC Chrome·폰에 실제 통제 알림이 오고 눌러서 카드

## P8 — 현장 실증 (2027-03) (P7 에서 번호만 옮김, 태우 2026-11-09)
현장 데이터 규칙(`data/raw/field/<YYYYMMDD>/`: smpa.pdf, topis_notices.json, track.gpx, photos/<HHMMSS>_*.jpg, notes.md + 같은 시각 recorded)은 v0.4와 같다. 예측 통제 vs 관측 대조 → 보고서.

## 보류 (ADR 필요)
- 로컬 모델 사후학습 전환 — naru-reader 실측 후 ADR-007 개정
- 관계 추출(segment) 정확도가 낮으면 segment 끄고 point만 — T4.3 결과 후
- 밀집도 데이터 연동 — 계약 후
