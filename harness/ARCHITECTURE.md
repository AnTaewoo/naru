# ARCHITECTURE.md — Naru v0.5

그림: `docs/architecture.png`. 이 문서는 그 그림의 텍스트판이고, 둘이 다르면 이 문서가 맞다.
스택: ADR-006 (Next.js · Flask MVC · MySQL · Context Provider) + ADR-007 (공지 파서 = Claude API). 규약: `docs/CONVENTIONS.md`. 계약: `docs/INTERFACE.md` v0.5.

## 원칙
1. 통제 위치는 **지오메트리**(코스 폴리라인·돌발 링크·리졸버가 찾은 좌표)와 **센서**(버스 이탈)에서 온다.
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
| 서울시 버스위치정보 · 노선 정류장 마스터 | sectionId·posX/posY·dataTm | 개발 1,000/일 → 운영 상향 | BusDeviationDetector, RouteSectionIndex |
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
| `RouteSectionIndex` | `sections(route_id) -> list[Section]` | 노선 → 정상 section 시퀀스 |
| `BusDeviationDetector` | `poll() -> list[ClosureCandidate]` | 건너뜀·폴리라인 이탈. 같은 section 2대↑ → confirmed, 복귀 → released |
| `CongestionWatcher` | `watch(zone) -> CongestionSpike \| None` | confidence 승격만 (보류, ADR-002) |
| `IngestWorker` | `run_forever()` | 스케줄: 공지 5분 · 돌발 1분 · 혼잡 5분 · 버스 통제창 ±30분 15초 / 밖 5분. 일 호출 예산 |
| `CandidatePublisher` | `publish(batch: CandidateBatch) -> None` | httpx → `POST /internal/candidates` |

### BE — `packages/be` (`naru_be`) · Flask MVC
의존: **controllers → views → models** (아래로만, `.importlinter`가 강제).

**Controller** — HTTP 입구. 검증 → Model → View, 3줄.
| 클래스/모듈 | 엔드포인트 | 부르는 Model | 넘기는 View |
|---|---|---|---|
| `route_controller` | `GET /route` | `RoutePlanner.plan(query)` | `route_view.render` |
| `closure_controller` | `GET /closures` | `ClosureRepository.active_at(t, bbox)` | `closure_view.render` |
| `candidate_controller` | `POST /internal/candidates` | `CandidateIntake.accept(batch)` | 202 + 처리 건수 |

**Model** — 데이터와 도메인 로직. Flask를 모른다.
| 클래스 | 시그니처 | 역할 |
|---|---|---|
| `CrosswalkIndex` | `from_point(pt, radius_m=30)` · `from_line(line, buffer_m)` · `from_segment(seg)` → `set[str]` | geometry → crosswalk_ids. STRtree, EPSG:5179. **`from_segment`**: `RoadGraph.shortest_path(from, via, to, road)` → LineString → 버퍼(`road_class`: 대로 25 / 로 15 / 길 8 m) → `from_line` |
| `RoadGraph` | `shortest_path(points, road=None) -> LineString` | 표준노드링크(또는 도보망) NetworkX. road가 있으면 그 도로명 링크만 |
| `ClosureEngine` | `apply(candidate, crosswalk_ids) -> list[ClosureState]` · `transition(prev, evidence)` | 상태기계 |
| `CandidateIntake` | `accept(batch) -> IntakeResult` | 후보 → CrosswalkIndex → ClosureEngine → Repository |
| `ClosureStateEntity` | SQLAlchemy ORM, 테이블 `closure_states` | crosswalk_id, status, confidence, window_start/end(UTC), evidence(JSON), lng/lat |
| `ClosureRepository` | `upsert(state)` · `active_at(t, bbox) -> list[ClosureState]` | DB 접근은 여기만 |
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
④ 버스 위치 ─→ BusDeviationDetector (+RouteSectionIndex) ─┤                         │
⑤ 장소 혼잡 ─→ CongestionWatcher ─────────────────────────┘          ⑥ POST /internal/candidates
                                                                                    ▼
                         [C] candidate_controller → [M] CandidateIntake → CrosswalkIndex(from_point / from_line / from_segment+RoadGraph) → ClosureEngine → ClosureRepository(MySQL)

           [C] route_controller → [M] RoutePlanner(Repository + TimeDependentRouter + BaselineRouter over PedGraph) → [V] route_view   ⑦
           [C] closure_controller → [M] ClosureRepository.active_at → [V] closure_view                                             ⑧
                                                                                    ▼
                 Next.js /api/* rewrites → NaruApiClient → Time/Closure/Route Provider → MapView · LegList
```

## ClosureState 상태기계
| status (코드값) | 라벨 | 생성 조건 | Router | FE |
|---|---|---|---|---|
| `scheduled` (conf ≥ 0.7) | 예정 | 코스 시각표, 돌발 예고 | 비용 ×3 | 노랑 점, 경로 2개 보여주고 선택 |
| `scheduled` (conf < 0.7) | 예정 | 〃 | 무시 | 노랑 점만 |
| `confirmed` (conf ≥ 0.8) | 확인 | 버스 이탈 ≥2대, 돌발 발생, 코스 시각표 시작 | 제외 | 빨강 점, 자동 우회 |
| `released` | 해제 | 버스 복귀, 시각표 종료+30분 | 정상 | 회색 점, 30분 후 제거 |
| `zone_scheduled` | 예정 구역 | 지역명만 있는 공지 (ZoneMatcher), `impact: unknown` 후보가 도로 30 m 규칙으로 승격되지 않은 경우 (ADR-008) | 무시 | 보라 빗금만 |

전이: `scheduled → confirmed → released`. `zone_scheduled`는 라우팅과 무관. 혼잡 급등은 `scheduled`의 confidence만 올린다. 전이 로직은 Model(`ClosureEngine`)에만 있다. 임계값은 `naru_be/config.py`.

## 보류 중인 결정 (ADR 필요)
- 로컬 모델 사후학습으로 전환 — 해커톤 이후, `naru-reader` 실측 결과로 ADR-007 개정
- 관계 추출 정확도(구간 F1)가 낮으면 segment를 끄고 point만 — T4.3 평가 후
- 밀집도 데이터(KT·서울시 계약) 연동 — 계약 후
