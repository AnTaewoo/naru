# ROADMAP.md — Naru v1

진행 상태의 진실. Task `status`는 `TODO → DOING → DONE`. Claude가 시작할 때 `DOING`, 태우가 "다음"이라고 하면 `DONE`. ★ 경로에서 depends가 끝난 첫 TODO가 다음 Task다.
**PC(Prototype Check)** 는 태우가 직접 눈으로 확인하는 관문이다. "PC 통과"라고 해야 다음 Plan으로 간다.
한 번에 Task 하나. 절차는 `.claude/skills/task-cycle/SKILL.md`. 🧑는 사람이 하는 Task(Claude는 체크리스트까지만).

## 마일스톤
| | 날짜 | 내용 | 경로 |
|---|---|---|---|
| **M1 데모** | **2026-11-16** 최종 제출 (배포 링크·시연 영상·보고서·포스터), 11-21 본행사 | 광화문 일대, 기록된 공지 1세트(마라톤 코스 + 집회 공지) + 실시간 경로 계산 | P0 → P1 → P2 → P3 → P4 → P5 |
| M2 현장 실증 | 2027-03 서울국제마라톤 | 예측 통제 vs 현장 관측 | P6 → P7 |

**★ 11/16 경로**에 없는 Task는 하지 않는다. 11/16 전까지의 순서: P0(2일) → P1(2일) → P2(1일) → P3(2일) → P4(2일, P1~P3과 병행 가능 — AI 레인) → P5(3일).
LLM은 ADR-007로 확정(Claude API). 로컬 사후학습·버스 우회 감지·현장 데이터는 해커톤 이후(P6·P7).

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
- status: DOING
- depends: T5.1
- 산출: `state/RouteProvider.tsx`, `map/layers/routeLayer.ts`(route 파란 실선, underpass 구간 남색, baseline 회색 점선), `components/{RouteCard,LegList,EvidencePopover}.tsx` — `docs/mockups/02_route.html`·`03_closure.html`의 카드·탭·바텀시트 구조 그대로(CONVENTIONS §5.9): 가장 빠른 길 / 원래 길(막힘·해제 시각) / 근거·확신도
- 테스트: recorded 통제 중 `/route` → 카드 숫자·LegList 라벨이 응답과 일치

### T5.3 배포 · e2e · 시연 영상 ★
- status: TODO
- depends: T5.2, T4.4
- 산출: Flask + AI 워커 `--once`(홈서버, 기록 재생) + Next.js 배포(Vercel 또는 홈서버) → **배포 링크**. Playwright e2e: 교보빌딩 앞 → 대한문, 통제 중 시각 선택 → 우회 경로·지하보도 레그. 시연 영상 스크립트 `harness/plans/active/demo_script.md`
- 산출(고지, 태우 2026-11-08): 지도 attribution(VWorld 키 전까지 OSM "© OpenStreetMap contributors") + `/licenses` 페이지 — maplibre-gl(BSD-3-Clause, LICENSE.txt 의 MapLibre·Mapbox 저작권 고지 전문) 등 오픈소스 고지
- 🧑 태우: 영상 촬영, 포스터 A0, 보고서 결과 칸 채우기(T4.3 표, 사용성 테스트)

### PC-5 (태우) — 11/16 제출
- [ ] 배포 링크에서 라이브로 경로가 나온다 (외부 API 호출 없이)
- [ ] 시연 영상, 포스터, 보고서, 레포 공개 확인
- [ ] 사용성 테스트 5명 결과가 보고서 1.2·2.4에

---

## P6 — 실시간 신호 (해커톤 이후, M2)
T6.1 RouteSectionIndex · T6.2 BusDeviationDetector(집회 당일 기록 필요, 없으면 fail) · T6.3 IncidentIngestor · T6.4 버스 폴링 스케줄·운영계정. 내용은 v0.4 P4 그대로.

## P7 — 현장 실증 (2027-03)
현장 데이터 규칙(`data/raw/field/<YYYYMMDD>/`: smpa.pdf, topis_notices.json, track.gpx, photos/<HHMMSS>_*.jpg, notes.md + 같은 시각 recorded)은 v0.4와 같다. 예측 통제 vs 관측 대조 → 보고서.

## 보류 (ADR 필요)
- 로컬 모델 사후학습 전환 — naru-reader 실측 후 ADR-007 개정
- 관계 추출(segment) 정확도가 낮으면 segment 끄고 point만 — T4.3 결과 후
- 밀집도 데이터 연동 — 계약 후
