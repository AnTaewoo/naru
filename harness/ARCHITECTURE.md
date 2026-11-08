# ARCHITECTURE.md — Naru v0.5

그림: `docs/architecture.png`. 이 문서는 그 그림의 텍스트판이고, 둘이 다르면 이 문서가 맞다.
스택: ADR-006 (Next.js · Flask MVC · MySQL · Context Provider) + ADR-007 (공지 파서 = Claude API). 규약: `docs/CONVENTIONS.md`. 계약: `docs/INTERFACE.md` v0.5.

## 원칙
1. 통제 위치는 **지오메트리**(코스 폴리라인·돌발 링크·리졸버가 찾은 좌표)에서 온다. **센서**(버스 위치)는 위치를 만들지 않고 기존 통제의 확신도만 고친다 (ADR-013).
2. LLM(Claude API)은 공지 문장에서 **표현과 구간만** 뽑는다 — spans(TIME·ROAD·INTERSECTION·POI·ADDRESS)와 segments(from/to/via/road/window). 좌표는 지명사전(리졸버)이 찾고, 구간의 선은 BE가 도로 그래프로 만든다. 모델이 만든 좌표는 계약(`PlacePoint`)에 들어올 수 없다.
3. 모든 폐쇄는 `scheduled → confirmed → released` 상태기계를 거치고, 모든 전이에 evidence가 남는다.
4. 사용자 요청 경로(`/route`, `/closures`)에는 외부 API 호출이 없다.
5. 공간 연산은 Python(Shapely·NetworkX)에서. MySQL은 결과 저장소.
6. **프로세스는 셋**: AI 워커(`naru_ai.worker`), BE(Flask), FE(Next.js). 서로 import하지 않고 HTTP와 `naru_contracts`로만 만난다.

## 프로세스와 통신
```
 [AI 워커]  naru_ai.worker ──POST /internal/candidates (X-Naru-Internal-Token)──▶ [BE] Flask :5000
                                                                                     ▲
 [FE] Next.js :3000 ── 브라우저는 /api/* 만 호출 ── next.config rewrites ─────────────┘
```

## 레인과 클래스

### 입력 소스 (전부 공개)
| 소스 | 형태 | 라이선스·한도 | 쓰는 곳 |
|---|---|---|---|
| 주최측 코스 GPX + 구간별 통제 시각표 | 파일 | 공지 | CourseIngestor |
| 서울경찰청 '오늘의 집회' | PDF 표 (일시·장소·행진경로) | 로그인, 매일 수동 | NoticeParser 입력 + 평가 정답 |
| TOPIS 공지 · 서울시 보도자료 · 언론 보도 | 텍스트 | TOPIS 2유형(비상업) | NoticeParser |
| 서울시 교차로·횡단보도 위치, 도로명코드, 카카오 Local API | 정규형 → 좌표 | 공공누리 · 카카오 100,000/일 | Resolver(지명사전) |
| TOPIS 실시간 돌발정보 | 링크 ID | 1유형 | IncidentIngestor |
| 서울시 버스위치정보 · 노선 경로·정류소 마스터 | vehId·gpsX/gpsY·sectOrd·stopFlag·dataTm | 개발 1,000/일(일 상한 900) → 운영 상향 | BusPoller(AI) → BE BusCorrection (ADR-013) |
| 서울 실시간 도시데이터 · S-DoT | 장소 121곳 5분 · 센서 10분 | 공개 | CongestionWatcher |
| 서울시 도보 네트워크·횡단보도·지하도·육교·역 | 노드·링크 | 1유형 | PedGraph, CrosswalkIndex |
| TMAP 보행자 API | 경로 | 1,000/일 무료 | 그래프 QA 샘플링만 |
| LLM | **Claude API** `claude-haiku-5-5` (tool use 구조화 출력, temperature 0, 응답 기록·재생) | 월 $1 미만 (공지 50건/일) | NoticeParser |

### contracts — `packages/contracts` (`naru_contracts`)
`ClosureCandidate`, `CandidateBatch`, `ClosureState`, `Evidence`, `Window`, `NoticeRef`, `PlacePoint`, `Geometry` = `PointGeom | LineGeom | SegmentGeom | ZoneGeom`(kind로 구분), `RouteQuery`, `RouteResponse`, `ClosuresQuery`, `ErrorBody`, enums. INTERFACE.md v0.5의 코드판 — **코드가 이미 있다** (`packages/contracts/naru_contracts/`). AI·BE 공용, FE 타입은 여기서 생성.

### AI — `packages/ai` (`naru_ai`) · 독립 워커
| 클래스 | 시그니처 | 역할 |
|---|---|---|
| `CourseIngestor` | `ingest(gpx, timetable) -> list[ClosureCandidate]` | 마라톤 메인 경로. 폴리라인 그대로 |
| `NoticeSource` | `sentences() -> list[NoticeSentence]` | smpa PDF 표·TOPIS 공지·보도 → 문장 레코드(text, context, published_at, source_url) |
| `NoticeParser` | `parse(sentence) -> ParsedNotice` | **Claude API** tool use. 출력 `spans[{text, tag, canonical}]` + `segments[{road, from, to, via, window, kind, scope}]`. 응답은 `data/recorded/llm/`에 기록, 있으면 재생. 정렬기가 start/end를 찾고 못 찾으면 버린다 |
| `AnthropicClient` | `complete_tool(system, messages, input_schema) -> dict` | 유일한 LLM 클라이언트. temperature 0. 가짜 구현 금지 |
| `Resolver` | `resolve(tag, canonical) -> PlacePoint \| None` | 지명사전: 교차로(서울시 데이터) · 도로명(도로명코드) · POI/주소(카카오 기록). 못 찾으면 None |
| `CandidateBuilder` | `build(parsed) -> list[ClosureCandidate]` | segments → `SegmentGeom`(양 끝 풀린 것만), 나머지 spans → `PointGeom`. confidence는 출처·시간 명시 여부 규칙 |
| `ZoneMatcher` | `match(zone_name) -> ZoneGeom` | 지역명(여의도·광화문 일대) → 폴리곤. v1 |
| `IncidentIngestor` | `pull() -> list[ClosureCandidate]` | TOPIS 돌발 → link_ids |
| `BusPoller` | `poll() -> BusPositionBatch` | 통제 창(시작 1시간 전 ~ 끝+30분) 노선 최대 3개를 60초마다 → 원문 기록 → `POST /internal/bus-positions`. 판단 없음, 후보를 만들지 않는다 (ADR-013, T6.2) |
| `CongestionWatcher` | `watch(zone) -> CongestionSpike \| None` | confidence 승격만 (보류, ADR-002) |
| `IngestWorker` | `run_forever()` (`--loop`) | 스케줄: 코스 1회 · 공지 5분 · 돌발(OA-13315) 5분 · 공지 게시판 10분(T6.4) · 버스 60초(통제 창만, T6.2) · 혼잡 보류. 소스마다 격리, 연속 3회 실패면 ERROR. 일 상한 LLM 200·버스 900. 웹 페이지는 같은 곳 10분 이상, 키로 쓰는 공개 API 는 그 한도 (ADR-011 E·ADR-013 H) |
| `CandidatePublisher` | `publish(batch: CandidateBatch) -> None` | httpx → `POST /internal/candidates` |

### BE — `packages/be` (`naru_be`) · Flask MVC
의존: **controllers → views → models** (아래로만, `.importlinter`가 강제).

**Controller** — HTTP 입구. 검증 → Model → View, 3줄.
| 클래스/모듈 | 엔드포인트 | 부르는 Model | 넘기는 View |
|---|---|---|---|
| `route_controller` | `GET /route` | `RoutePlanner.plan(query)` | `route_view.render` |
| `closure_controller` | `GET /closures` | `ClosureRepository.active_horizon(t, bbox)` → `ClosureEngine.restate(states, t)` | `closure_view.render` |
| `candidate_controller` | `POST /internal/candidates` | `CandidateIntake.accept(batch)` | 202 + 처리 건수 |
| `bus_controller` | `POST /internal/bus-positions` | `BusIntake.accept(batch)` | 202 (ADR-013, T6.2) |

**Model** — 데이터와 도메인 로직. Flask를 모른다.
| 클래스 | 시그니처 | 역할 |
|---|---|---|
| `CrosswalkIndex` | `from_point(pt, radius_m=30)` · `from_line(line, buffer_m)` · `from_segment(seg)` → `set[str]` | geometry → crosswalk_ids. STRtree, EPSG:5179. **`from_segment`**: `RoadGraph.shortest_path(from, via, to, road)` → LineString → 버퍼(`road_class`: 대로 25 / 로 15 / 길 8 m) → `from_line` |
| `RoadGraph` | `shortest_path(points, road=None) -> LineString` | 표준노드링크(또는 도보망) NetworkX. road가 있으면 그 도로명 링크만 |
| `ClosureEngine` | `apply(candidate, crosswalk_ids) -> list[ClosureState]` · `transition(prev, evidence)` | 상태기계 |
| `CandidateIntake` | `accept(batch) -> IntakeResult` | 후보 → CrosswalkIndex → ClosureEngine → Repository |
| `BusIntake` | `accept(batch) -> int` | 버스 위치 적재(`bus_positions`) → 영향 받는 후보의 보정 계열(`bus_corrections`) 다시 계산 (ADR-013, T6.2·T6.3) |
| `BusCorrection` | `correction(candidate_id, at) -> Correction` | 최근 20분 관측 → 항목 합 [−0.30, +0.25] → clamp(base + 합, 0, 0.95), bus_skip 은 20분 안에서만, 정상 통과 2번(20분 간격)이면 해제. 읽을 때 적용 (ADR-013, T6.3) |
| `ClosureStateEntity` | SQLAlchemy ORM, 테이블 `closure_states` | crosswalk_id, status, confidence, window_start/end(UTC), evidence(JSON), lng/lat |
| `ClosureRepository` | `upsert(state)` · `active_at(t, bbox)` · `active_horizon(t, bbox)`(t~t+60분 안 시작 포함, `/route`·`/closures` 공통) `-> list[ClosureState]` | DB 접근은 여기만 |
| `PedGraph` | `edge.kind ∈ {sidewalk, crosswalk, underpass, overpass, stairs, elevator, station}` | NetworkX 인메모리 |
| `TimeDependentRouter` | `route(src, dst, t, closures) -> Path` | A*. cost = dist + vertical + degraded. closed(t) → 제외 |
| `BaselineRouter` | `route(src, dst) -> Path` | 같은 PedGraph, closures 미적용 |
| `RoutePlanner` | `plan(query: RouteQuery) -> RouteResult` | 활성 폐쇄 조회 → 두 라우터 → 도메인 결과 |

**View** — 응답 표현. DB를 모른다.
| 모듈 | 입력 → 출력 |
|---|---|
| `route_view` | `RouteResult` → `RouteResponse`(contracts) → JSON (INTERFACE §2) |
| `closure_view` | `list[ClosureState]` + zones → GeoJSON FeatureCollection (INTERFACE §3) |
| `error_view` | 도메인 예외·검증 오류 → `ErrorBody` (INTERFACE §6) |

### FE — `packages/fe` · Next.js App Router
| 파일 | 종류 | 역할 |
|---|---|---|
| `next.config.ts` | 설정 | `rewrites`: `/api/:path*` → Flask |
| `app/layout.tsx` · `app/page.tsx` | Server | 뼈대·푸터, `<NaruApp />` 렌더만 |
| `app/providers.tsx` | **'use client'** | `ApiProvider > TimeProvider > ClosureProvider > RouteProvider` |
| `components/NaruApp.tsx` | **'use client'** | 화면 루트, `MapView`를 `dynamic(..., { ssr: false })` |
| `api/naruApiClient.ts` | client | `/api/route`, `/api/closures` — 네트워크 만지는 유일한 파일 |
| `state/*Provider.tsx` | client | 각각 StateCtx + DispatchCtx, `useReducer` |
| `map/MapView.tsx` | client | `useRef(maplibre.Map)`, `source.setData()` |
| `map/layers/{closure,route,zone}Layer.ts` | 순수 함수 | contracts → MapLibre source |
| `components/TimeSlider` · `LegList` · `EvidencePopover` · `Footer` | client | |

## 흐름
```
① 코스 GPX·시각표 ─→ CourseIngestor ───────────────────────┐
② 공지 문장 ─→ NoticeParser(Claude API) ─→ Resolver(지명사전) ─→ CandidateBuilder ─┤
                 spans + segments        정규형 → PlacePoint     segment / point 후보
③ TOPIS 돌발 ─→ IncidentIngestor ────────────────────────┼→ ClosureCandidate → CandidatePublisher
                                                          │                         │
⑤ 장소 혼잡 ─→ CongestionWatcher ─────────────────────────┘          ⑥ POST /internal/candidates
                                                                                    ▼
                         [C] candidate_controller → [M] CandidateIntake → CrosswalkIndex(from_point / from_line / from_segment+RoadGraph) → ClosureEngine → ClosureRepository(MySQL)

           [C] route_controller → [M] RoutePlanner(Repository + TimeDependentRouter + BaselineRouter over PedGraph) → [V] route_view   ⑦
           [C] closure_controller → [M] ClosureRepository.active_horizon → ClosureEngine.restate → [V] closure_view              ⑧
                                                                                    ▼
                 Next.js /api/* rewrites → NaruApiClient → Time/Closure/Route Provider → MapView · LegList

④ 버스 위치 ─→ BusPoller ─→ POST /internal/bus-positions ─→ [C] bus_controller → [M] BusIntake(bus_positions) → BusCorrection
                 버스는 후보를 만들지 않는다. ⑦·⑧ 이 읽을 때 그 시각의 보정으로 확신도를 고친다 (ADR-013)
```

## ClosureState 상태기계
| status (코드값) | 라벨 | 생성 조건 | Router | FE |
|---|---|---|---|---|
| `scheduled` (conf ≥ 0.7) | 예정 | 코스 시각표, 돌발 예고, 공지 | 횡단보도에 닿는 시각이 공지 창 안이면 횡단보도당 +300초, 창 밖은 정상 (ADR-011 A) | 노랑 점, 피한 통제는 "공지상 통제 시간 · 현장 확인 전" |
| `scheduled` (conf < 0.7) | 예정 | 〃 | 무시 | 노랑 점만 |
| `confirmed` (conf ≥ 0.8) | 확인 | 돌발 발생, 코스 시각표 시작, 버스 2대 이탈(bus_skip — 보정 후 ≥ 0.8, 20분 안에서만, ADR-013) | 제외 | 빨강 점, 자동 우회 |
| `released` | 해제 | 시각표·공지 종료+30분, 버스 정상 통과 −0.30 이 20분 간격 2번(ADR-013) | 정상 | 회색 점, 30분 후 제거 |
| `zone_scheduled` | 예정 구역 | 지역명만 있는 공지 (ZoneMatcher), `impact: unknown` 후보가 도로 30 m 규칙으로 승격되지 않은 경우 (ADR-008) | 무시 | 보라 빗금만 |

전이: `scheduled → confirmed → released`. `zone_scheduled`는 라우팅과 무관. 혼잡 급등은 `scheduled`의 confidence만 올린다. 버스는 읽을 때 확신도를 보정한다(최근 20분, 합 [−0.30, +0.25], 최종 clamp 0~0.95 — 저장값은 base_confidence, ADR-013). 전이 로직은 Model(`ClosureEngine`)에만 있다. 임계값은 `naru_be/config.py`.

## 보류 중인 결정 (ADR 필요)
- 로컬 모델 사후학습으로 전환 — 해커톤 이후, `naru-reader` 실측 결과로 ADR-007 개정
- 관계 추출 정확도(구간 F1)가 낮으면 segment를 끄고 point만 — T4.3 평가 후
- 밀집도 데이터(KT·서울시 계약) 연동 — 계약 후
