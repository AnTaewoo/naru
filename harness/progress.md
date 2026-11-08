# progress — 세션 로그

새 항목은 맨 아래에 붙인다. 지우거나 고치지 않는다. 세션 시작 때 마지막 항목부터 읽는다. Task당 하나 ("다음" 받았을 때).

```
## YYYY-MM-DD · T?.? DONE
- 한 것: (보고의 "한 것" 한 줄)
- 정한 것:
- 막힌 것 / 태우 대기:
- 커밋: <code hash> / <harness hash>
```

---

## (시작 전)
- 한 것: 하네스 v1 설치 (Claude API 확정, INTERFACE v0.5 segment, contracts 코드, 목업 3장). 브랜치 develop
- 다음: 태우가 "다음" 또는 "T0.1 시작" → T0.1

## 2026-11-07 · T0.1 DONE
- 한 것: 하네스 v1을 git에 등록(.claude·harness), `uv sync`로 .venv·uv.lock 재생성(HEAD와 동일), `make check`·`make layers` 6 kept 초록, MySQL(호스트 3307) `+00:00`·utf8mb4·naru_test 확인, naru_contracts를 INTERFACE v0.5와 대조해 읽음
- 정한 것: 하네스 커밋에 docs/ 제외(guard가 혼합 커밋을 막음), 목업 636줄은 가져온 문서라 커밋 하나, Gate 시연 6개 생략(요청 없음), MySQL 호스트 포트 3307 유지(3306은 로컬 서비스), v1 한 줄 docstring 4개는 E501 때문에 HEAD 복원
- 막힌 것 / 태우 대기: ADR-006 버전 표는 태우가 직접 채움(값은 보고에 보냄, .venv 설치본과 일치 확인). `reader/` untracked 그대로
- 커밋: f3881f6, 58f3d57 / 658109f(하네스 v1), 이 항목의 커밋

## 2026-11-07 · T0.2 DONE
- 한 것: `scripts/fetch_seoul_spatial.py`(`make fetch SRC=seoul_spatial`) — 종로·중구 도보망 + 서울 전체 지하도·육교·엘리베이터·리프트·대로변 횡단보도(Open API 78회, 페이지 원문 저장) + 교차로·횡단보도 xlsx·유형코드표(파일). 실데이터 테스트 4개, MANIFEST 항목
- 정한 것: 리프트·대로변 횡단보도도 같이 받음, OA-22906은 안 받음. xlsx는 `OA-23081.xlsx`로 저장(원본명은 _meta·MANIFEST). openpyxl을 BE 의존성에. 횡단보도 xlsx는 **EPSG:5186**이라 테스트는 5186 변환으로 검증 — ROADMAP T0.2의 "WGS84" 문구는 API 데이터에만 해당(문구 수정 여부 태우 미답, 그대로 둠)
- 막힌 것 / 태우 대기: 첫 실행 때 httpx INFO 로그가 인증키를 터미널에 찍음(파일에는 없음, 스크립트 수정함) — 키 재발급 권고. T1.2는 5186→5179 변환 필요
- 커밋: 182b101, 56062f1, c225182 / 이 항목의 커밋

## 2026-11-07 · T0.3 DONE
- 한 것: `scripts/fetch_nodelink.py`(`make fetch SRC=nodelink`) — 태우가 수동으로 받아 푼 전국 표준노드링크 shp(노드 118만·링크 156만, ITRF2000 중부 TM=5186)에서 서울(ID 앞2자리 10·11·12)만 node/link gpkg로 추출(46,085/63,383). 테스트 3개, MANIFEST 원본·추출본
- 정한 것: 종로·중·영등포만이 아니라 서울 전체 추출(경계 링크 보존, 작음). 다운로드는 스크립트가 안 함(로그인 필요). 좌표계 .prj 그대로, BE가 5179 변환. MULTILINK·TURNINFO 미추출. ID 앞4자리=자치구(1000 종로, 1010 중구, 1180 영등포) 확인
- 막힌 것 / 태우 대기: 없음. 출처 URL(data.go.kr 15025526) 태우 확인함
- 커밋: 3c37cfb, fc0f8f3 / 이 항목의 커밋

## 2026-11-07 · T0.4 DONE
- 한 것: `scripts/fetch_course.py`(`make fetch SRC=course`) — 서울시 '내 손안에 서울' 기사(2026-03-12) 표에서 2026 서울마라톤(3.15) 구간별 통제·해제 시각표 16행 파싱, 포스터 코스 설명 순서를 nodelink_seoul 교차로 노드 17구간으로 옮겨 도로명 제한 최단경로로 GPX 디지타이즈(42.534 km, +0.8%, 폴백 0). 테스트 2개(AI 레인), MANIFEST
- 정한 것: 공식 GPX 없음(누리집은 2027 대회로 전환) → 디지타이즈. 청계천로 왕복은 같은 차로 링크 왕복(무방향). 도착점은 '종합운동장역' 노드. 첫 시도 36.6 km는 청계천로 서쪽 끝(청계광장, 포스터 '시청삼거리') 왕복 누락 — 코스 지도 km 표지로 찾아 수정
- 막힌 것 / 태우 대기: 없음
- 커밋: d5d7a1f, 7a97d09 / 이 항목의 커밋

## 2026-11-07 · T0.5 DONE
- 한 것: `naru_ai/notice/source.py`(SmpaPdfSource·TopisNoticeSource·NoticeSentence), `scripts/build_notices.py` — 서울경찰청 PDF 3일치 표 13행 + TOPIS 공지(NoticeList xml, 최신 300건 중 통제안내·버스안내 258건) 2,797줄 → `sentences.jsonl` 2,810행. 테스트 4개
- 정한 것: smpa text = 표 한 행을 셀 순서로 공백 연결(fields에 구조). TOPIS 본문은 블록 태그에서만 줄 나눔. TOPIS 원문은 recorded, 문장 jsonl은 raw(.gitignore, MANIFEST sha256) — 태우 지시로 git 제외. SMPA_BOARD_URL=nd54882(기록용, 자동 수집 안 함, 태우 확인). PDF 원본 파일명 유지. 보도 문장 import는 태우 지시로 건너뜀
- 막힌 것 / 태우 대기: 없음. T0.6(라벨)은 팀 작업 대기
- 커밋: 10489d4, debe772, 9f17921 / 이 항목의 커밋

## 2026-11-07 · T0.7 DONE
- 한 것: `scripts/record_api.py`(`make record API=incident|links|rtd|bus|kakao`) — TOPIS 돌발(코드표 2 + 실시간 53건, 집회및행사 15), 돌발 링크 4개 LinkInfo·LinkVerInfo, 도시데이터 광화문·덕수궁, 카카오 숭례문·덕수궁, 버스 100100118 12대. 호출 17회. 재생 테스트 6개, MANIFEST
- 정한 것: grs80tm은 EPSG:5181. TOPIS 링크 ID는 표준노드링크와 같은 체계지만 4개 중 2개만 존재 → 좌표는 LinkVerInfo. 카카오는 `kakao/keyword/<sha1>.json`(스킬 §4.3). 응답 본문의 키도 가림(카카오 401이 키를 되돌려 줬음, 태우가 파일 삭제)
- 막힌 것 / 태우 대기: 없음 (카카오 앱 로컬 API 활성화·DATA_GO_KR_KEY는 태우가 해결)
- 커밋: d16deeb, 7fdb8b8, 1354724, ae02fb8 / 이 항목의 커밋

## 2026-11-07 · T1.1 DONE
- 한 것: `naru_be/models/domain/ped_graph.py` PedGraph(도보망 종로·중구 + 지하도·육교 오버레이 → NetworkX, kind 7종, 관리번호 부착), `naru_be/config.py` Settings. 노드 15,183·간선 19,067·최대 성분 98%·crosswalk 1,346·관리번호 1,138/1,211 부착. 테스트 3개
- 정한 것: 횡단보도 = 양끝 CRSWK 노드 링크 ∪ 대로변 오버레이 + 관리번호 점이 얹힌 ≤60 m sidewalk 승격(링크 CRSWK 플래그는 횡단보도 아님). crosswalk_ids 튜플. 지하도는 별도 망 → 출입구를 30 m 안 도보망 노드에 stairs/elevator로 연결. 엘리베이터·리프트 오버레이 미사용. 타입 스텁 3개 추가
- 막힌 것 / 태우 대기: T0.2 결함 발견·고침 — SGG_NM 필터 페이지 겹침(유일 64~74%) → 서울 전체 492페이지 재수집(316ac4f). PC-0 체크리스트는 T0.7 보고에 — 태우 "PC-0 통과" 대기
- 커밋: 316ac4f, 82feeb0, f02a27d, 84a027b / 이 항목의 커밋

## 2026-11-07 · T1.2 DONE
- 한 것: `road_graph.py` RoadGraph(link.gpkg를 sqlite로 → NetworkX 46,273/63,341, shortest_path(points, road): 도로명 링크 strict → 끊기면 x4 패널티 폴백), `crosswalk_index.py` CrosswalkIndex(OA-23081 1,211점 STRtree, from_point 30 m·from_line 15 m·from_segment 등급별 버퍼). 테스트 6개 — (a)(b)(c) 전부 실데이터 좌표
- 정한 것: "그 도로명 링크만"은 우선 시도 후 폴백(세종대로가 노드링크에서 5조각). road 지정 시 끝점은 그 도로 노드에. road_class 없으면 접미사 → 없으면 15 m. 도로 그래프 무방향. BE 런타임에 geopandas 안 씀(gpkg sqlite 직접)
- 막힌 것 / 태우 대기: ARCHITECTURE 문구("그 도로명 링크만") 한 줄 보정 여부
- 커밋: 60fa6e0, 8b2d0d0, 163b684 / 이 항목의 커밋

## 2026-11-07 · T1.3 DONE · PC-1 통과
- 한 것: `intersection_map.py` IntersectionMap(교차로명 → 교차로관리번호 → 횡단보도관리번호, 정확 일치만. 종로·중구 409 교차로, 1:1 유일), `scripts/pc1_map.py` folium 지도(kind별 간선·관리번호 점·from_segment 경로·버퍼). 테스트 3개. PC-1은 태우가 지도 보고 "다음 좋네"
- 정한 것: 교차로 좌표 = 소속 횡단보도 평균. 괄호 변형('(연등)')은 다른 교차로. 별칭은 T4.2 리졸버 몫
- 막힌 것 / 태우 대기: 없음
- 커밋: d5545fe, 0fd4f25, 177340f / 이 항목의 커밋

## 2026-11-07 · T2.1 DONE
- 한 것: `packages/contracts/tests/test_interface_examples.py`(INTERFACE json 블록 6개·§4 enum 표 대조, extra=forbid, review 규칙, geometry 4종 왕복, 오프셋 필수) 12개, `scripts/export_schema.py` + `make schema` → `packages/fe/src/types/contracts.schema.json`·`contracts.d.ts`(인터페이스 28개, json-schema-to-typescript@15)
- 정한 것: 생성물 d.ts 커밋. §1.1 요청 예시는 자리표시자를 §1 후보로 치환해 검증
- 막힌 것 / 태우 대기: 문서≠코드 4건 보고 — §3 예시가 JSON 아님(검증 못 함), §1.1 요청 예시 자리표시자, CandidateBatch.producer 제한 없음, FeatureProperties.window가 dict. 결정 대기
- 커밋: 2df20d6, 9f28618 / 이 항목의 커밋

## 2026-11-07 · T2.2 DONE
- 한 것: `naru_ai/ingest/course.py` CourseIngestor(시각표 16구간 + 풀·10 km GPX 조각 → ClosureCandidate 16, line·scheduled·0.9·timetable evidence), `fetch_course.py`에 10 km 코스 디지타이즈(11.44 km, 반환점 가락시장역사거리), `scripts/record_candidates.py --source course` → recorded/candidates/course. 테스트 3개
- 정한 것: 11~15구간 매핑(11 풀코스 잠실역→동문, 12 송파대로 바깥, 13 안쪽, 14 동문→잠실역, 15 종합운동장교차로→동문 285 m). 웨이포인트는 GPX 순서대로 트랙에 붙임(왕복 구간). candidate_id course-20260315-segNN
- 막힌 것 / 태우 대기: 조각이 겹친 첫 기록(20261107T185022.json) 삭제 요청. b92c481은 빨간 테스트로 커밋됨(파이프 종료코드 미확인) → 22bc972로 고침. develop 46커밋 GitHub 푸시(태우 요청)
- 커밋: c3f7a14, 9e77011, b92c481, 22bc972 / 이 항목의 커밋

## 2026-11-07 · T2.3 DONE · ADR-008 승인 반영
- 한 것: `closure_engine.py` ClosureEngine(apply/status_at/effective_window/bump_confidence/release_by_evidence — scheduled→confirmed(실측 증거+시작)→released(종료+30분), end 없으면 +6h, 전이마다 evidence). 테스트 6개. ADR-008 승인 반영: INTERFACE v0.6(impact 필수·toward·approx), naru_contracts+테스트 13개, contracts.d.ts 재생성, CourseIngestor impact=blocks, 엔진 unknown→zone_scheduled, config 상수 2개, course 후보 재기록
- 정한 것: confirmed 조건 = confidence ≥ 0.8 + 실측 증거(timetable·topis_incident·bus_skip) + start 경과. 공지만으론 시간이 지나도 scheduled. review_required 후보도 상태는 만듦(라우터가 제외). reason = evidence detail 구간명
- 막힌 것 / 태우 대기: 규칙서 파일을 `notice_parser_rules_v2.md`로 개명(원래 naru_parser_spec_v2.md). T0.6의 "30개"는 34건과 다름(미수정). recorded/candidates/course 옛 파일 2개 삭제 요청. 해제 공지(none/released) 전달은 후속 ADR
- 커밋: 227a6ec, c8a6b5f, 42399e8, 4265ffb + ADR-008 반영 4개 / 이 항목의 커밋

## 2026-11-07 · T2.4 DONE · PC-2 통과
- 한 것: `db.py`, `entities/closure_state.py`(closure_states: UTC DATETIME, DECIMAL 좌표, JSON evidence, impact·approx, 유일키 candidate_id+crosswalk_id), Alembic 0001, `ClosureRepository`(upsert_many ON DUPLICATE KEY, active_at(t, bbox) window+30분·bbox, KST↔UTC). 실제 MySQL naru_test 테스트 2개. `scripts/pc2_map.py`(3시각 지도) — 태우 "다음"
- 정한 것: upsert 키 (candidate_id, crosswalk_id). active_at은 저장된 status 그대로(시각별 재계산은 라우터·컨트롤러). 테스트 정리는 DELETE
- 막힌 것 / 태우 대기: 없음
- 커밋: 55dc207, 60747dd, d866624 / 이 항목의 커밋

## 2026-11-07 · T3.1 DONE
- 한 것: `models/domain/routers.py` TimeDependentRouter(heapq A*, 비용 = 거리 + 계단 25 m·엘리베이터 40 m, 간선 도착 시각(출발 + 거리/1.2 m/s)으로 상태 재판정 → confirmed 제외·scheduled x3·confidence<0.7 무시, avoided = 기준 경로의 막힌 횡단보도), `types.py`(Path·RouteLeg·AvoidedCrosswalk), PedGraph.nearest_node·간선 이름, ClosureEngine.status_of_state, 라우터 설정 3개. 실데이터 테스트 3개(교보빌딩→대한문: 13:30 808 m 기준, 07:45 지하보도 840 m + avoided confirmed 2, 04:30 scheduled). 카카오 교보빌딩 1회 기록
- 정한 것: 도착 시각 판정은 라벨 하나짜리 A*(엄밀한 시간의존 최단경로 아님, 도보 10분엔 충분). 저장 status 대신 status_of_state로 매번 재판정. 접근 구간(출발·도착 ↔ 최근접 노드)은 직선으로 거리·좌표에 포함
- 막힌 것 / 태우 대기: 카카오 '교보빌딩' 1순위가 서초 교보타워(3순위가 광화문) — T4.2 리졸버가 범위 힌트로 골라야 함(MANIFEST 기록)
- 커밋: 383e569, 6634752, 1adcecf / 이 항목의 커밋

## 2026-11-07 · T3.2 DONE
- 한 것: `routers.py` 공통 `_AStarRouter` + `BaselineRouter.route(src, dst)`(통제 미적용, route_free 대체), `route_planner.py` RoutePlanner.plan(RouteQuery) → RouteResult(path·baseline·depart_at·computed_at) — lat,lng 파싱(parse_latlng), bbox(+1 km)·출발+60분 지평으로 `ClosureRepository.active_between` 조회 → 두 라우터. `errors.py`(NaruError → InvalidQueryError 400·NoRouteError 422, INTERFACE §6 코드). 실제 MySQL 테스트 4개(통제 후 path==baseline 808 m, 통제 중 저장소 confirmed가 avoided에, 지평 조회로 출발 뒤 시작하는 통제 회피 846 m, invalid_query·Flask 미import)
- 정한 것: 조회 지평 60분(route_horizon_min) — active_at만 쓰면 걷는 동안 시작하는 통제를 놓침. Repository에 active_between 추가(ARCHITECTURE 표엔 active_at만). 좌표 파싱 실패는 Model이 InvalidQueryError(field). computed_at은 UTC(View가 +09:00)
- 막힌 것 / 태우 대기: 없음
- 커밋: 5034842, 0d29bda, 198516a / 이 항목의 커밋

## 2026-11-07 · T3.3 DONE
- 한 것: `views/route_view.py`(RouteResult → RouteResponse → jsonify), `closure_view.py`(ClosureState → GeoJSON Point Feature), `error_view.py`(NaruError·ValidationError → ErrorBody + HTTP, render_code), `views/_time.py`(+09:00 변환), `types.KST`. 테스트 3개(라우터 실제 결과 → contracts model_validate, until 08:08+09:00, 183 Feature, 오류 코드·필드) + conftest `course_world` 세션 픽스처
- 정한 것: 예정-구역 Polygon Feature는 ZoneMatcher(v1) 폴리곤이 생기면(실데이터 없이 분기 안 만듦). 뷰 테스트는 맨 Flask() 앱 컨텍스트. 한글 이스케이프(ensure_ascii)는 T3.4 create_app에서 끔. 404·401·500은 app factory가 render_code로
- 막힌 것 / 태우 대기: 없음
- 커밋: 5d69f69, c4d60a9 / 이 항목의 커밋

## 2026-11-07 · T3.4 DONE · PC-3 통과
- 한 것: `app.py` create_app(실데이터 Model 싱글턴·Blueprint·§6 에러 핸들러·ensure_ascii=False), `controllers/{_deps, route, closure, candidate}` 3줄 핸들러(토큰은 /internal before_request), `candidate_intake.py`(batch_id 멱등 — candidate_batches/Alembic 0002, kind별 CrosswalkIndex, unknown 30 m 승격, zone 로그만), `parsing.py`, `log.py`, `RoadGraph.nearest_link_distance_m`, `ClosureEngine.restate`, `candidate_view`, `scripts/record_naru_api.py` → recorded/naru_api 10건. 테스트 6개(실제 앱 인프로세스 + naru_test). `make dev` = flask run
- 정한 것: 적재가 창 뒤여도 status_of_state 가 창으로 재판정(실측 bus_return 해제만 고정). **/closures 도 /route 와 같은 +60분 지평(태우 "+60분으로 하자")** → `ClosureRepository.active_horizon`, ARCHITECTURE 표·INTERFACE §3 보강. 405·415 → not_found·invalid_query. zone 후보는 ZoneMatcher v1 뒤, unknown 승격은 함수 단위 검증(실제 unknown 후보는 T4)
- 막힌 것 / 태우 대기: 없음
- 커밋: a7ea670 3211a25 ee79e6a e236c5f 29b9ed4 65d1d3c 25bdfa4 40973d8 + MANIFEST 재기록 / 이 항목의 커밋

## 2026-11-07 · T4.1 DONE
- 한 것: `naru_ai/config.py` Settings, `llm/notice_schema.py`(규칙서 v2 §9.1 pydantic → strict JSON Schema), `llm/client.py` AnthropicClient.complete_tool(strict tool + tool_choice 강제, 캐시, refusal·max_tokens·상한 예외, anthropic 2.6.0 파라미터 확인), `llm/prompt.py`, `llm/recorder.py`(model·prompt_version 불일치 fail), `llm/prompts/notice_v1.md`(규칙서 §0~§5·§9 + few-shot 8), `scripts/record_llm.py`. live 3문장 기록(≈$0.003, 시스템 프롬프트 11,072 토큰 캐시), 재생 테스트 4개
- 정한 것: temperature 는 못 씀(Haiku 5.5 400, SDK 키 없음) → strict schema + 규칙 confidence (CLAUDE.md §3-8·CONVENTIONS §3.2 갱신, 태우). max_tokens 4096. number min/max 는 API 가 거부해 스키마에서 제거. 강제 tool 호출은 thinking 없음(T4.3 에서 auto 비교 가능). guard.py 에 prompts/ 허용(태우)
- 막힌 것 / 태우 대기: guard.py 변경·T4.1_stop.txt 는 태우가 커밋. TOPIS 문장은 줄 단위라 T4.2 에서 notice_id 로 묶어야 함
- 커밋: 17e1a44, 9f25116, f37b3a9, b968a75, cdd2479(하네스) / 이 항목의 커밋

## 2026-11-07 · T4.2 DONE
- 한 것: `notice/gazetteer.py`(OA-23081 교차로명 7,592 → 관리번호별 횡단보도 평균점, 접미사·변형, 중복 None; 노드링크 ROAD_NAME 2,972·road_class; 별칭 csv), `notice/resolver.py`(교차로 → 카카오 기록 재생: 서울 bbox·AREA 힌트·식당 등 카테고리 제외·방향어 뗀 재시도, None), `notice/parser.py`(재생 → 정렬기 → segment 양 끝 검증), `notice/candidates.py`(SegmentGeom/PointGeom, toward 0.65·unknown 0.65 상한, notice_ref·evidence), `record_api --queries`(카카오 9건 live), `record-candidates SOURCE=notice`(후보 3). 테스트 8개
- 정한 것: 교차로 사전이 카카오보다 먼저. 도로명 사전은 도로명코드 대신 노드링크 ROAD_NAME. 카카오 1순위에서 식당·카페 등 9개 카테고리 제외('사랑채' 사례). confidence 는 파서 값 + 상한만. '사랑채 동측 건너편'은 못 풀어 출발지 point 만(틀린 선보다 빠진 점)
- 막힌 것 / 태우 대기: '민주당사' 서울시당 vs 중앙당 선택은 T4.3 에서 확인. guard.py 변경은 태우 커밋
- 커밋: a4d252f, ac2b6b1, 0ff69d1, 342a4ac, 16228e7, 0adfbad / 이 항목의 커밋

## 2026-11-08 · T4.3 DONE
- 한 것: `notice/rule_baseline.py`(규칙 기준선), `notice/eval_cases.py`·`eval.py`·`eval_report.py`(item 짝 비교 impact·kind·segments·window·toward·points, road·impact_reason 참고, 거절은 blocks 없음, 부트스트랩 CI, markdown), `scripts/eval_notice.py` → `docs/eval/notice_20261108.md`, `record_llm.py`(cases·csv 입력, --ids all, --max-calls). live 197회(34 라벨 + 163 합성, ≈$0.09) 기록 후 재생. 결과: 전부 일치 Claude 18/34(53%, CI 38~71) vs 규칙 14/34(41%); 합성 스키마 통과 Claude 163/163, 규칙 161/163
- 정한 것: 두 숫자 따로(태우). Task당 10회 규칙은 평가 세트 1회 기록으로 넘김(--max-calls 명시). 합성 봉투 source news·published_at 고정. docs/eval 은 스크립트가 씀. 정규형 F1·Jaccard 는 라벨에 spans·좌표가 없어 제외
- 막힌 것 / 태우 대기: 라벨↔규칙서 불일치 10건 결정 — 지점 집회 impact(K-012~015·020 blocks vs §9.2-12 unknown), K-016 items 1 vs 2, K-026 잠수교 blocks vs §9.2-3 car_free, K-031 impact_reason construction(스키마 밖), K-033 none 에 segment 요구, K-027 라벨이 문장과 불일치. 진짜 모델 오류 5건(K-010·011·019·028·008/032)
- 커밋: 58850c5, 691385b, 77d42bf, 1d907a3, 2b62d92 / 이 항목의 커밋

## 2026-11-08 · T4.3 재평가 (라벨 교체 + 프롬프트 notice_v2, 태우 지시)
- 한 것: 태우가 cases_v1.jsonl·규칙서·prompts/notice_v2.md 교체 → impact_reason construction 추가, 기본 프롬프트 v2(v1 삭제), few-shot 11문장을 sentences.jsonl 에 추가(`scripts/append_fewshot_sentences.py`, N001…N100), 34 라벨 + 5 문장 live 39회 재기록(≈$0.01), 규칙 기준선도 재실행 → `docs/eval/notice_20261108_v2.md`. 전부 일치 Claude 23/34(68%, CI 53~82) vs 규칙 19/34(56%, CI 38~74). type 별 none 4/6 vs 0/6, unknown 5/5 vs 5/5, 정상 10/16 vs 10/16, 놓치기쉬움 3/6 vs 3/6
- 정한 것: 합성 163건은 v2 로 재기록 안 함(허용 34회 밖) → 표에서 Claude 견고성 행 생략, v1 표 참조. 워커 e2e 핀은 v2 값(공지 후보 7·횡단보도 37 — r04 를 v2 가 segment 3개로 냄)
- 막힌 것 / 태우 대기: ① `.env` NARU_PROMPT_VERSION 이 아직 notice_v1 (코드 기본값은 v2, 이번엔 환경변수로 덮어 실행) ② `docs/data/naru_parser_spec_v2.md` → `notice_parser_rules_v2.md` 덮어쓰기는 분류기가 막아 태우가 ③ few-shot news 2행(N099·N100) 출처 URL 미상 ④ guard.py 변경 커밋
- 커밋: 이 항목 직전 2개 / 이 항목의 커밋

## 2026-11-08 · T4.4 DONE
- 한 것: `naru_ai/publish.py` CandidatePublisher(httpx POST, 토큰, 5xx·연결 3회 재시도, 4xx 즉시 실패), `naru_ai/worker.py` IngestWorker(코스 1회 + 공지 재생 → 내용 해시 batch_id, `--once`/`--live`, run_forever 5분), `naru_ai/log.py`, Settings(NARU_BE_URL·NARU_INTERNAL_TOKEN). e2e `packages/be/tests/test_e2e_worker.py`(WSGITransport 로 실제 Flask + MySQL): 코스 16/183 + 공지 7/37(v2), /closures 광화문 12:30 13·15:30 37, 재실행 멱등, 401
- 정한 것: e2e 테스트만 naru_ai·naru_be 를 함께 import(패키지는 여전히 독립). 광화문 시연용으로 few-shot 문장 r01·r04 기록. 돌발·버스 스케줄은 P6. few-shot news 2행 URL 은 태우 확인값으로 채움
- 막힌 것 / 태우 대기: PC-4 — review 임계값·모델 결정(Sonnet 비교는 live 34회·≈$0.2 라 승인 필요), 지도 확인
- 커밋: 97360ce, bd483bf, 25fdb7e, 0969ad4, 616c041 + URL 보강·규칙서 커밋 / 이 항목의 커밋

## 2026-11-08 · T5.0 DONE
- 한 것: `packages/fe` — Next 15.5.29·React 19.3.1·TS 5.9 strict, pnpm 12(corepack 심, allowBuilds), eslint 9 flat + typescript-eslint strict, prettier, vitest 3 + jsdom 26, Playwright 1.56, rewrites `/api/:path*` → NARU_API_ORIGIN(internal 제외, 순수 함수 테스트), app/{layout,page}(server)·providers·NaruApp('use client' 둘)·ApiProvider·naruApiClient(URL·파싱, recorded 응답 테스트 8개)·Footer·CSS Modules, `make dev` = Flask + next, ADR-006 버전 표. `make dev` 로 :3000 경유 /api/closures 200·/api/route 839.6 m·internal 404 확인
- 정한 것: Node 18.20 → Next 16 불가, 15.5 고정(nvm 22 올리면 교체). BE 오리진 기본 127.0.0.1(Node 18 localhost=::1). maplibre 6.16(pnpm 공급망 정책). `@` 별칭 없음. output standalone
- 막힌 것 / 태우 대기: 없음 — 게이트 .next 제외는 태우가 a61c1d4 로 반영, 확인 완료
- 커밋: fcb9ec4, f480003, 9549bfc, a86bd36 / 이 항목의 커밋
