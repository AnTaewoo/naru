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

## 2026-11-08 · T5.1 DONE
- 한 것: FE 홈 — TimeProvider(t·하루 범위·?t=·하이드레이션 ready)·ClosureProvider(t·bbox → /api/closures, 디바운스·Abort), closureLayer·zoneLayer(상태색 점 + ×/! 아이콘, 예정 구역 빗금), MapView(maplibre useRef, 워커 setWorkerUrl, OSM 타일·출처), ClosureTimeline·TimeSlider·LayerChips·ClosureSheet, ko 라벨. 고쳐(태우): ADR-009 `legs[].coord_range`(INTERFACE v0.7, contracts 검증기, BE `_build`, recorded 재기록) + routeLayer 남색 터널·입구 마커, 겹친 횡단보도 합침(07:45 79건 = 64곳, 확인 45·예정 19). vitest 29 · e2e 4(실제 Flask + next start + Chrome)
- 정한 것: 터널 남색(시안 02), 접근 구간은 sidewalk 레그, 육교 포함, 입구는 들어가는 쪽만, 출처는 오른쪽 위에 펼침, 겹친 횡단보도는 무거운 상태·늦은 해제. VWorld 키 전까지 OSM, 고지 페이지는 T5.3(태우)
- 막힌 것 / 태우 대기: VWorld 키(.env.local, 태우) — 레이어 이름·축 순서는 키 받은 뒤 확인. ARCHITECTURE 4·38행이 "INTERFACE v0.5"(지금 v0.7)
- 커밋: 4902574 … 2e2f7d1 (20개), 1616eac / 이 항목의 커밋

## 2026-11-08 · T5.2 DONE
- 한 것: 길찾기 — RouteProvider(4/4: 길찾기 켜기·지도 두 번 눌러 출발/도착·바꾸기·다시 고르기, `?from=&to=`, t·출발·도착이 바뀌면 /api/route + Abort), routeLayer 경로 파란 실선·원래 길 회색 점선·화면 맞춤 범위, MapView 출발·도착 핀(DOM 마커)·새 출발·도착에만 화면 맞춤, RoutePanel(시안 01 검색창 자리 길찾기 바 → 시안 02 rpanel), RouteCard(가장 빠른 길 12분·840m·07:57 / 원래 길 11분·지금 못 감·08:30 해제, 안내 문장, 출발 시각 슬라이더), LegList, EvidencePopover(해제 시각·근거·확신도). vitest 48 · e2e 7(실제 Flask + next start + Chrome, 출처 가림 검사 포함)
- 정한 것: 장소 검색 없음(계약 밖) → 지도 고르기 + URL. 탭은 가장 빠른 길만(계단 없는 길·기다렸다 출발은 ADR 필요). 슬라이더를 경로 시트에. 확신도는 같은 시각 /closures 값. 1 km 아래는 m. 지도 컨트롤은 떠 있는 UI 아래. 시안 02 지도 말풍선·안내 시작 버튼은 뺌
- 막힌 것 / 태우 대기: 없음
- 커밋: 9cf567e … 1b6b179 (15개) / 이 항목의 커밋

## 2026-11-08 · T5.3 DONE
- 한 것: 배포 https://naru.antaewoo.com (태우: DNS·nginx 서버 블록·인증서에 naru 추가·tmux `make serve`). `make serve`(MySQL·마이그레이션 → Next 빌드 dist → gunicorn 127.0.0.1:5050 → 워커 --once 기록 재생 → Next standalone 127.0.0.1:3050), `/licenses`(런타임 의존성 라이선스 전문·지도·데이터 출처), 지도 출처 칸·푸터 링크, 시연 e2e(13:35 → 슬라이더 07:45 지하보도 우회), 시연 대본. e2e 10개를 공개 주소에서 통과
- 정한 것: 홈서버(nginx 는 3050 만, Flask·/internal 비공개), dev 와 serve 를 한 체크아웃에서(포트·dist 분리), standalone server.js, 화면 맞춤 위쪽 여백 = 실제 지도 컨트롤 아래 끝, 시연 시작 13:35
- 막힌 것 / 태우 대기: 없음. 첫 화면("지금")엔 통제 0건 → T5.4 통제 불러오기 (태우 결정: 불러오기, 첫 화면은 안내 버튼만, 반영은 태우)
- 커밋: 985b14b … 4ad74f6, 646ebec / 하네스 2629456, acb6218 / 이 항목의 커밋

## 2026-11-08 · T5.4 DONE
- 한 것: 통제 불러오기 — BE `GET /closures/events`(ADR-010, INTERFACE v0.8 §3.1: DB 통제를 (reason, window) 사건으로, 서로 다른 횡단보도 수·bbox·approx, 시작 늦은 순), FE 하단 시트 "통제 불러오기"(KST 날짜별 목록 → 시작 시각·지도 맞춤), 빈 칸·길찾기 안내 버튼, 슬라이더 "지금", 시트 제목 날짜. recorded `closure_events.json`(사건 7). e2e 12개 공개 주소 통과(태우 make serve 재시작 뒤)
- 정한 것: 사건 키 (사유, 창) — 11/7 시의회 행진 4구간 = 한 줄 31곳. 길찾기에선 지도를 안 옮긴다. 목록은 마운트 때 한 번. ADR-010 상태 "승인"(계획 승인)
- 막힌 것 / 태우 대기: 없음. 태우 실서버 점검 → T5.5~T5.10·T6.1~T6.6 추가(ADR-011)
- 커밋: d479767 … b44af19 (13개) / 하네스 3bfad22 / 이 항목의 커밋

## 2026-11-08 · T5.5 DONE
- 한 것: 라우터 정확성(ADR-011 A) — 예정은 횡단보도에 닿는 시각이 공지 창 안일 때만 횡단보도당 +300초(×3 폐지), 창 밖 보통, confirmed 차단. 보행망 붙임 150 m 넘으면 422 `out_of_coverage`. FE 피한 통제 "통제 중" / "공지상 통제 시간 · 현장 확인 전", 범위 밖 안내, 통제 근거 말투("이렇게 판단했어요" 뺌, "해제 예정"·"서울경찰청 집회 공지", 띄어쓰기). 회귀 3개(① 잠실 → out_of_coverage ② 11/7 15:00 세종대로 → 시청 지하보도 우회·예정 1곳 ③ 3/15 07:45 광화문 그대로) 공개 주소 확인, e2e 14
- 정한 것: 페널티는 닿는 시각 판정, 300초 × 1.2 m/s = 360 m. 0.7 미만 예정 무시 그대로. 60분 지평 조회는 남김(걷는 도중 시작하는 통제). 04:30 경로는 원래 길로, 06:30 은 다른 횡단보도로(기록·테스트 갱신). 붙여 준 번호 한 칸씩(T5.5~T5.10). 스크린샷은 JPEG 로 줄여 completed 에 둔다
- 막힌 것 / 태우 대기: 통제 근거 말투 수정(17441bb)은 `sudo systemctl restart naru` 뒤 공개 반영
- 커밋: 19f595d(하네스) 5469575 0cf05d0 d579fff 2a126d0 b235793 c99b4af 3e5bfae daa5404 17441bb / 이 항목의 커밋

## 2026-11-08 · T5.6 DONE
- 한 것: 공용 BottomSheet — 손잡이 pointer 드래그(touch-action·user-select none), 접힘 96px / 절반 50% / 전체(화면 − 위 UI: 홈 112·길찾기 176), 놓으면 가까운 단계, 탭은 접힘↔절반. 길찾기는 새 출발·도착 경로에 접힘 + 경로 전체 맞춤, 통제 불러오기는 접힘 + 그 통제 범위 맞춤(서울 전체 줌아웃·시트 뒤 가림 해결), 모바일 푸터 숨김, 지도 로딩 표시. e2e 17(iPhone 13 시트 3개 포함)
- 정한 것: 전체를 88% 로 두면 손잡이가 출발·도착 패널 밑에 깔려 못 접음 → 위 UI 아래까지. 시각만 바뀌면 안 접음. 목록·경로 상세·근거는 전체로. 맞춤 아래 여백 = 접힌 시트 + 24px. 모바일 기준 640px, 푸터 e2e 는 데스크톱 폭
- 막힌 것 / 태우 대기: 공개 반영은 `sudo systemctl restart naru`
- 커밋: 18b8658 b9b3b5c 075a0f5 134a09a 89aa35a / 이 항목의 커밋

## 2026-11-08 · T5.7 DONE
- 한 것: 내 위치 — 길찾기를 켜면 출발 기본값 "내 위치"(권한 대답 없음·거부·실패·보행망 밖이면 칸은 비우고 시트 안내, 지도 누르기는 언제나 먹음), 출발·도착 칸 옆 내 위치 버튼, 지도 오른쪽 위 GeolocateControl(파란 점, 밖이면 6초 안내), maplibre 컨트롤 한국어. 범위는 `/closures/events` 의 `coverage`(INTERFACE v0.10, ADR-011 C 의 앞부분 — 보행망 노드 bbox). e2e 23(내 위치 6 포함)
- 정한 것: 범위 밖 위치는 칸에 안 넣음, 범위를 아직 모르면 넣고 BE 판정. 자동 찾기는 길찾기를 켤 때만(주소창에 출발이 있으면 안 함). 받으면 지도를 그 점으로. 위치 옵션 정확도 우선·15초·1분 재사용. e2e 의 권한 거부는 DevTools Protocol `Browser.setPermission`(세션을 닫으면 풀려서 테스트 끝까지 연다)
- 막힌 것 / 태우 대기: 공개 반영은 `sudo systemctl restart naru`. 작업 중 `git pull --rebase --autostash origin main` 으로 develop 커밋 해시가 전부 바뀜(내용 같음) — 앞 항목들의 커밋 해시는 rebase 전 값. e2e 라이선스 테스트 1회 실패(링크를 지도 래퍼가 가림, 재실행 5회 통과, trace 는 지워짐)
- 커밋: c7e7b74 e2fdac2 29541d9 0615a70 54177a2 d1e715f cb85ffd 4fca075 832eeff / 이 항목의 커밋

## 2026-11-08 · T5.8 DONE
- 한 것: 주소·검색(결정 B) — BE 가 카카오 로컬을 대신 부르는 `GET /geocode/search`(near 반경 5 km 정확도 순, 10개)·`GET /geocode/reverse`(도로명에서 시·도 뺀 label, 없으면 지번) INTERFACE v0.11 §7, 오류 `geocode_unavailable` 503. 키는 서버 `KAKAO_REST_KEY`(SecretStr), `NARU_GEOCODE_SOURCE=live|recorded`. FE 홈 검색창(결과마다 출발·도착), 출발·도착 칸을 누르면 검색 입력칸(2글자·300ms, 입력 중 지도 누르기는 그 칸), 칸 이름은 장소 이름·주소 — 좌표는 화면에서 없앰, 실패 시 "선택한 위치". 새로 정한 점이 화면 밖이면 지도 이동. 태우 피드백: 통제 근거의 원본 출처 줄(공지 게시 시각·"서울경찰청 집회 공지"·[공지]/[시각표])을 전부 뺌(두 번 잘못 읽음 — 처음엔 배지만 뺐다). e2e 29
- 정한 것: 거리순(sort=distance)은 건물 안 가게가 앞서('교보빌딩' 1위 세차장) 반경 5 km 정확도 순으로, near 는 소수 2자리(약 1 km). 카카오 live 10회(상한) — 처음 거리순 키워드 3건은 안 씀(삭제는 태우 판단). e2e 의 BE 는 기록 재생이라 지오코딩 503 은 공용 ownErrors 가 뺀다(계약상 503 은 geocode_unavailable 뿐). 공개 프록시 호출 상한은 없음
- 막힌 것 / 태우 대기: 공개 반영 `sudo systemctl restart naru`(이때부터 서버가 카카오 live). 홈 통제 목록의 "시각표 · 확신"도 출처 — T5.9 에서 뺀다
- 커밋: 19e73bb 8196306 9c6a281 a91a964 2a849f3 be05cc9 9cb4c25 559dd5c c2d188d 85b91fe 8ef37a9 49e6eb0 d6196ec cc9d0ae 068e2d2 834a264 5533b61 0f90238 9afee4f 199ad99 / 이 항목의 커밋

## 2026-11-08 · T5.11 DONE (태우 요청으로 T5.8 고침과 함께 당김)
- 한 것: 원래 길 보기 — 피한 통제가 있으면 경로 카드 전체가 버튼, 원래 길 카드를 누르면 고른 테두리(막힘 빨강·공지상 주황)·시트 접힘·지도는 원래 길 실선·가장 빠른 길 흐리게·원래 길이 지나는 통제 횡단보도에 원(통제 중 빨강·공지상 주황), 가장 빠른 길로 돌아오기. 계약 그대로(태우 선택) — 위치는 avoided id 로 같은 시각 /closures 점에서. e2e 2(07:45·11/7 15:00)
- 정한 것: 원래 길과 가장 빠른 길이 거의 겹치면(07:45) 선으로는 안 갈려서 원으로 막힌 곳을 보인다. 고른 길이 바뀌면 그 길에 맞춘다
- 커밋: 0c26ceb c7f6dbc 5fba6ee 7cd0b80 190d328 (하네스 6a0b943 3ceb367) / 이 항목의 커밋

## 2026-11-08 · T5.9 DONE
- 한 것: 통제 목록(ADR-012 승인 — 태우 조건: summary 는 구조화 칸만·파서 정규 이름 그대로·Claude 스키마 그대로, 문장·숫자 표기는 FE ko.ts). 후보 summary(구간 from/to/via·지점 이름·reported_people·roads) → BE closure_states 열 4개(Alembic 0003) → 사건 type·source·summary·notice, 응답 data_as_of(INTERFACE v0.12). FE 제목 "시의회~숭례문오거리 집회 → 광화문·고용노동청 행진" / "5만 명 · 태평로"(두 줄까지), 횡단보도 수는 사건 전체(지도를 옮겨도 31곳, 겹친 피처 38 → 31), 출처 줄(시각표·확신)·타임라인 툴팁 원문 제거, 원문은 "공지 원문 보기"에서만, 목록 위 기준 시각 + 실시간 돌발 회색 경고(30분), "지금" 배지는 실제 지금(±5분)일 때만, 통제 불러오기 다가오는 것 먼저·"지난 통제". e2e 31
- 정한 것: 제목 규칙(첫 구간 끝에서 갈라지면 "A~B 집회 → C·D 행진"), 인원 "5만 명"/"5,000명", data_as_of 는 출처별 게시·시각표·수신 시각(키 topis_notice=topis, topis_incident=incident), 코스 후보도 새 batch_id 로 재기록(같은 batch_id 는 멱등이라 메타가 안 채워짐), 11/7 15:00 /closures 기록 추가
- 막힌 것 / 태우 대기: 공개 반영 `sudo systemctl restart naru`. 개발 DB(공개 서비스와 같음)에 Alembic 0003 적용됨(열 추가만). 작업 중 `git pull --rebase --autostash origin develop` 으로 T5.8 고침·T5.11·하네스 커밋 해시가 바뀜(내용 같음) — 앞 항목들의 해시는 rebase 전 값
- 커밋: 9e5445c b586d12 27718a9 377e52b f497fca e733c03 9a38f75 0b88f05 b7ac2e1 c39cc2b 84729f9 424552b e452b97 af9af62 af873c4 54d00f3 5d02767 / 이 항목의 커밋


## 2026-11-08 · T5.10 DONE · PC-5 통과
- 한 것: 경로 상세 — 횡단보도 레그 이름: OA-23081 교차로명(위치명 열은 없다), 관리번호 없는 간선은 20 m 안 표준노드링크 도로명, 이어진 횡단보도 간선을 합친 레그는 처음 만나는 교차로명이 도로명보다 먼저(07:45 "청계광장", 04:30 "세종대로사거리"·"청계광장", 11/7 15:00 "덕수궁앞"). INTERFACE §2 legs.name 뜻 보충(스키마 그대로). 경로 종류가 하나라 출발·도착 패널의 탭 줄 숨김 → 패널 108px, 시트 '전체' 552px, 지도 컨트롤 116px. e2e 32
- 정한 것: 관리번호 없는 횡단보도 간선(501개 — 시작 메모의 527 은 추정, 실측으로 고침)은 `crosswalk_road_name_m`(20 m) 안 가까운 도로명, 없으면 이름 없음. 합친 레그 이름은 교차로명 우선
- 막힌 것 / 태우 대기: 공개 반영 `sudo systemctl restart naru`(T5.6~T5.12 함께). PC-5 는 태우 "PC 통과"(체크리스트 셋은 태우 확인). 태우 커밋 4a7f848(README·그림)에 T5.10 메모·스크린샷이 함께 들어가 있어 completed/ 로 옮기기만 했다
- 커밋: c0b787d cd015b8 2b13ab0 74e35ad / 이 항목의 커밋

## 2026-11-08 · T5.12 DONE (태우 "OSM 오픈소스 고지 숨기면 안 되나 — 사용에 불편" → 고쳐 (a))
- 한 것: 지도 출처 칸을 "© OpenStreetMap contributors" 한 줄로(폭 252 → 173 px, iPhone 13), "오픈소스·데이터 고지" 링크는 공용 하단 시트 맨 아래 줄(펼쳤을 때만, 641px↑ 숨김 — 데스크톱은 푸터). e2e 32(고지 2개 새로)
- 정한 것: OSM 타일을 쓰는 동안 숨기기·ⓘ 접기는 안 함 — OSMF 타일 정책 §2 "Do not hide attribution beneath UI, behind toggles, or off-screen"(2026-11-08 원문 확인). 출처 칸 위치는 오른쪽 위 그대로(아래는 시트가 덮는다). fork 2개(OSM 고지·크롤링 점검)는 읽기만 했고, 크롤링 점검이 짚은 ADR-011 E 범위는 태우 결정 "웹 페이지 수집에만" → ADR-013(T6.1 시작 때)
- 막힌 것 / 태우 대기: 공개 반영 `sudo systemctl restart naru`(T5.6~T5.12 함께)
- 커밋: 7294110 617c011 (하네스 a02b0d2 9ed8c0f) / 이 항목의 커밋

## 2026-11-08 · T6.1 DONE
- 한 것: 워커 `--loop`(코스 1회·공지 5분·돌발 5분, `tick(now)`, 소스 격리·연속 3회 실패 ERROR). TOPIS 실시간 돌발(OA-13315) → 원문 기록 → 집회(10B02)만 TOPIS 링크 선 후보(확신도 0.9·topis_incident) → POST. BE 가 같은 횡단보도·겹치는 시각의 공지 후보 전체에 돌발 근거(어느 쪽이 먼저 와도), 돌발 배치 받은 시각 = data_as_of(빈 배치·재전송 포함). deploy/naru-worker.service, make serve 에서 워커 뺌. ADR-013(승인) 커밋 — 버스 확신도 보정, ADR-011 E 범위는 웹 페이지만. 실데이터: 기록 AccInfo 11/7 15:40 → 후보 9·횡단보도 16, r04 숭례문 쪽 16곳에 근거(0.75 라 예정 그대로)
- 정한 것: 유형은 집회만(11/7 범위 안 집회 8·차 없는 거리 2·축제 1·버스 무정차 2·시설물보수 3 — 나머지는 README impact 상 none), "(인도)" 보도 집회 뺌, 같은 링크·시각은 한 후보, 선 버퍼 15 m(방향별 링크 4곳), "같은 링크" = 같은 횡단보도 + 겹치는 시각, 원문은 바뀔 때만 새 파일, `--once` 는 코스·공지 그대로, alembic fileConfig 가 기존 로거를 끄지 않게
- 막힌 것 / 태우 대기: 🧑 `sudo cp deploy/naru-worker.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart naru && sudo systemctl enable --now naru-worker`. 확인 적재로 개발 DB(공개와 같음)에 11/7 돌발 사건 5개·r04 근거가 들어갔다 — 재시작 전 공개 BE 는 돌발 기준 시각을 11/7 15:40 으로 보인다. 돌발이 예상 종료 전에 사라지는 경우·acc_road_code 009/010 뜻은 미확인. live 7회(링크 6·AccInfo 1)
- 커밋: 9da0968 071e8b4 67127c7 48c0477 6c88255 fb6621f 1493451 2be5444 84176a4 (하네스 b7b875d 11df7d6 f5cd1ae) / 이 항목의 커밋

## 2026-11-08 · T6.2 DONE
- 한 것: 버스 관측 수집 — 노선 마스터 OA-1095(`make fetch SRC=bus_routes`, 41,688행·718노선, WGS84), 계약 `BusPosition`·`BusPositionBatch`(INTERFACE §1.2 v0.13, getBusPosByRtid 필드 그대로), 워커 bus 소스: 1순위 공지 통제(시작 1시간 전 ~ 끝+30분, 횡단보도 100 m 안 노선 3개, 60초, 쿼터 먼저) · 2순위 TOPIS 집회·행사 돌발(기준 데이터, 노선 1개, 120초, 하루 300·돌발 하나 30), 원문 `bus/notice`·`bus/incident`, 전체 하루 900(그날 기록 파일 수로 셈), 부른 노선은 getRoutePath 하루 한 번(`bus_routes/<날짜>/`, raw). BE `POST /internal/bus-positions` → `bus_positions`(Alembic 0004, 같은 노선·차량·시각은 한 번). 실데이터: 11/7 15:30 공지 창 노선 6개 → 위치 75개, 2순위 대상 13·노선 12(공지와 안 겹침)
- 정한 것: 노선 고르기는 정류소(NODE_ID) 수 순, N·새벽 노선 뺌, 돌발 하나 30회(약 1시간), 나누기 전 기록 9개는 옮기지 않고 재생 때 같이, `bus_corrections` 는 T6.3, 노선 경로 키 `DATA_GO_KR_ROUTE_KEY`(없으면 `DATA_GO_KR_KEY`). 태우 결정(고침): 2순위 돌발·기록 폴더·getRoutePath(도로 그래프 잇기 금지)·순서 T6.4 → T6.6 → T6.3
- 막힌 것 / 태우 대기: getRoutePath 는 처음 HTTP 401 "등록되지 않은 서비스키" → 태우 활용신청·확인("잘 나옴"). 🧑 `sudo systemctl restart naru`(Alembic 0004) · 워커 단위 다시 설치·재시작. 2순위 위치 수집은 실측 대기(첫 기록은 운영 워커가). live 10(버스 8·getRoutePath 2)
- 커밋: b6dbc94 5ea323c c536bab 62876d4 65de6b3 0b81b35 36296c5 6be502f 35f4420 06408f7 d96f92e 40e0d9b 1aff44a e79961c (하네스 f989672 576c267) / 이 항목의 커밋

## 2026-11-08 · T6.4 DONE (고침: 태우 "C①로 고치고 E도 고쳐, 그다음 다음")
- 한 것: TOPIS 통제·버스 공지 — 열린데이터광장 NoticeList(OA-22861, 게시판과 최신 글 같음) 10분마다 → 볼 글(통제안내·버스안내, 제목 날짜가 오늘 이후, 없으면 3일 안) → 글 하나 = 문장 하나(`topis-<번호>-u<고친 시각>`) → 기록 재생 또는 `--live` 로 notice_v2(한 번 10·하루 `NARU_LLM_DAILY_CAP` 200, 그날 기록 파일 수) → 후보(ID 는 버전 없이, batch_id 에 버전). 글 하나 실패는 그 글만, 프로세스 동안 다시 안 부름. 실데이터: 11/8 19:20 NoticeList 30행 + Claude 기록 28건 — 11/8 저녁 볼 글 6건은 후보 0(추측 좌표 0), 11/7 아침 6300 → 세종대로 7곳, 같은 날 돌발 근거로 12:00 통제 중(0.8). 고침: 구간 끝점은 AREA 라도 교차로 사전에 같은 이름이면 그 교차로(C①), '공지 원문 보기' 줄바꿈(E, iPhone 13 스크린샷)
- 정한 것: 원문은 API(웹 안 긁음), 글 단위(규칙서 §1.3), 볼 글 기준 `topis_feed.RECENT`, 하루 수는 기록 파일 시각(KST). 버그 고침 — 빌더 로그 extra `name`(LogRecord 예약어라 INFO 에서 KeyError, 운영 워커는 INFO). C① 은 지금 기록 33건에서 바뀌는 후보 0: AREA 끝점은 6262 광화문광장뿐인데 OA-23081 에 없고, 6288 서울광장은 구간 끝점이 아니라 지점이다 — 보고의 "범위 안 놓침을 다 잡는다"는 틀렸다
- 막힌 것 / 태우 대기: 🧑 `sudo cp deploy/naru-worker.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart naru-worker`(지금 워커는 18:56 T6.1 유닛 — 버스 live·TOPIS 안 돈다). 범위 안 놓침(서울광장 지점·광화문광장)을 잡을 방법은 태우 결정 대기. ADR-011 E 위반 1회(게시판 GET 2.7분 뒤 POST). 버스 e2e 2건이 운영 기록 폴더의 '가장 최근'을 재생. 펼친 원문이 길면 행의 점·배지가 가운데로 내려감. 기록 live: API 29(NoticeList 1·Claude 28, ≈ $0.017 / $50) + 웹 3
- 커밋: 7feec75 cdedc37 0bc2627 bf5fffc 39a8b3c ff4e7bb 6d5e7f8 1ec8a59 / 이 항목의 커밋

## 2026-11-09 · T6.6 DONE
- 한 것: 경찰청 '오늘의 주요집회' PDF inbox — 태우가 `smpa/inbox/` 에 넣으면 워커 smpa 소스(1분)가 표(SmpaPdfSource) → 행마다 notice_v2(기록 재생, 없으면 `--live`, TOPIS 와 같은 상한) → 후보 → BE, 남은 행 없이 보낸 뒤 `smpa/<집회 날짜>.pdf` 로 옮기고 `inbox_manifest.jsonl` 한 줄. 행 ID 에 기준 작성 버전(`-u<기준 작성>`), 후보 ID 는 버전 없이. 같은 파일은 `inbox/duplicate/`, 표가 아니면 `inbox/failed/`(지우지 않음). 실데이터: 실제 PDF 3개를 임시 inbox 로 복사 → 후보 10·11/7 횡단보도 38(r01 13·r04 24·r05 1), 옮긴 뒤 다시 돌려도 같은 배치
- 정한 것: PDF 별 처리 기록은 git 밖 jsonl(MANIFEST.md 엔 방식만), 옮긴 PDF 는 그날까지 다시 보냄, T0.5 테스트는 세 파일로 고정, 파싱은 TOPIS 와 한 코드(`_parse_notices`·`parse_failed`), 루프 테스트는 빈 임시 inbox
- 막힌 것 / 태우 대기: 🧑 새 유닛 설치·재시작(11/8 20:10 재시작은 옛 유닛 — TOPIS·PDF·버스 live 가 안 돈다). failed 경로는 그런 실제 PDF 가 없어 테스트 못 함. `build_notices.py` 를 다시 돌리면 옮긴 PDF 도 문장이 되고 같은 날짜가 둘이면 멈춘다. 기록 live: Claude 13(≈ $0.006, 누적 ≈ $0.023 / $50)
- 커밋: 1b0e96d a79f2fb f64351e d3ba13e 6d8bb36 / 이 항목의 커밋

## 2026-11-09 · T6.5 DONE (태우 "T6.5 먼저" — T6.3 실측 대기 보류)
- 한 것: 추가 소스 3개를 한 번씩 — TOPIS 교통통제 지도 내부 AJAX(목록 `selectAccAllListASC.do`·통제 도로 `selectAccLinkList.do`·링크 꼭짓점 `selectVmsLinkList.do`), OA-21285 사고통제현황, data.go.kr 15088841 — 응답 구조·도심 집회·좌표·라이선스 표. TOPIS 통제지도는 예정 통제를 시작 전에 주고(같은 때 OA-13315 에 없음) 행진 경로를 링크 순서로 준다 — 11/9 11:00~15:30 행진 1109233 이 통제 도로 19개(세종대로사거리→광화문 포함), 나루는 지금 이 행진을 의사당역 점 하나로만 가짐. OA-21285 는 OA-13315 를 장소 하나로 자른 것(11/7 7건 중 6건 같음, ID·링크 없음). 15088841 은 고속도로·국도 + 별도 키·IP 인증
- 정한 것: TOPIS 는 사이트를 같은 곳으로 보고 10분 간격(08:27·08:37·08:47), 원문은 recorded(topis_web 등)·MANIFEST, OA-21285 는 11/7 기록 + 11/9 1회, 15088841 은 포털 설명으로, 통제 도로는 오늘 행진 하나만. 1108643 을 "OA-13315 에 없다"고 쓴 건 시작 전 기록과 견준 탓 — 고침
- 막힌 것 / 태우 대기: TOPIS 통제지도를 쓸지(쓰면 ADR + 새 Task). 외부 8회(유료 0)
- 커밋: 954d45e 9927d77 (하네스 472ddaa) / 이 항목의 커밋

## 2026-11-09 · T6.7 DONE (태우 "서울 전체로 간다" → T6.9)
- 한 것: 범위별 실측(새 프로세스, naru_test) — 지금(종로·중구) 적재 4.2초·최대 400 MB·보행망 15,183 노드·횡단보도 1,211·마라톤 5/16 구간, 서울(중랑구 빼고 24개 구) 13.0초·1.5 GB·208,409 노드·20,908·16/16(470곳). /route: 회귀 4~30 ms, 잠실역→광화문 14.9 km 282~294 ms. 운영은 워커 2개라 서울 전체면 약 3 GB
- 정한 것: 중랑구 한 행(06-0000023497) 빈 좌표로 25개 구는 BE 가 죽어 24개 구로 쟀다
- 막힌 것 / 태우 대기: 없음 — 결정 받음(T6.9). 그 사이 워커 고침 둘(dea3aa0 버스 대상 수 로그, 822bc88 SIGTERM exit 0)
- 커밋: 코드 없음(측정만) / 이 항목의 커밋

## 2026-11-09 · T6.9 DONE (태우 "다음")
- 한 것: 서비스 범위 서울 25개 구 — OA-23081 빈 좌표 1행(중랑구 06-0000023497)은 건너뛰고 WARNING, 보행 노드 217,782·횡단보도 21,775·적재 12.9초·워커당 RSS 1.5 GB(ARCHITECTURE 한 줄), /route 회귀 p95 5.1 ms(14.9 km 307 ms) → A* 안 바꿈. 범위가 바뀌면 같은 후보도 새 배치(batch_id 에 BE 범위), 버스 1순위 확신도 0.45~0.8(신고 인원·시작 가까운 순, 0.8 초과는 남는 쿼터), inbox 중복은 manifest 만. 사건 districts(INTERFACE v0.13 보충) → 통제 불러오기 구 칩(화면과 겹치는 사건의 구 먼저)·오늘·다가오는 것만 펼침. 범위 문구 서울(화면 셋·README). 운영 워커가 11:04 부터 쌓은 기록에 테스트 5개가 깨져 버스 재생 기한·e2e 빈 inbox 로 고정
- 정한 것: 잠실은 600 m 가 아니라 1,113 m(마라톤 날 1,228 m, 직선 504 m) — 데이터 값으로 고정. 구 칩은 사건 bbox 로(FE 에 구 경계 없음). 오늘 시작한 통제는 끝나도 오늘 묶음. districts 는 구 칩 지시를 계약 추가 승인으로 봄
- 막힌 것 / 태우 대기: 국회대로 공지(11/9 r02 국회의사당역 2出 → 사랑채, 관할 영등포·마포·서대문·종로)는 1순위 아님 — 사랑채가 <여의도> 힌트에 버려지고 출발점 30 m 안 횡단보도 없음. TOPIS 돌발 1109233 이 횡단보도 6곳 통제 중 + 2순위 버스로 대신. (라)2순위 상한 올림·(다)'등' 힌트를 관할 구로·(가)100 m·(나)TOPIS 통제지도 결정 대기. 강남대로는 받아 둔 PDF 기준 16:05~17:00 교대역 7出(14:00 아님), 오늘 PDF inbox 대기. 12:00 태우 재시작 — 워커가 BE 보다 먼저 떠 첫 회차 실패(5분 뒤 재시도). 16:07 버스 기록 분석 예약(세션 안)
- 커밋: f5600d4 4d8ff2c fbfe9c7 8131f51 99eacf2 5b04f91 4ddc757 ef55993 62a3d1c (하네스 a7b6932 0863bc6) / 이 항목의 커밋

## 2026-11-09 · T6.3 보류 (태우 "버스 확신도 보정은 뺀다" — ADR-013 보류)
- 한 것: 16:07 버스 기록 분석 → 1개 차로 행진 셋(국회대로·강남대로·하나증권) 시간 안에 버스가 통제 구간을 124회 경로대로 지나감(하나증권 끝난 뒤 40회 포함 164회), 정차 찍힌 통과 137, 정류소 순번 끊김 0, 경로 60 m 이탈 0(관측 9,429건, 최대 32.7 m) → ADR-013 보류. 엔진의 버스 근거 경로 삭제('통제 중' = 시간표 + TOPIS 돌발), bus_correction → bus_route(RoutePath 만), 폴러는 전면 통제(lanes.scope full·one_side_full)·마라톤만 기록(NARU_BUS_RECORD_ONLY=1, 2순위 돌발 뺌), 평가 docs/eval/bus_20261109.md + scripts/eval_bus_20261109.py
- 정한 것: 계약 enum(bus_skip·bus_return)은 남김(값만, 상태 안 바꿈), 전면 통제는 워커가 파싱 결과로 (발췌, 시작)을 폴러에 넘김(계약 안 바꿈), 마라톤 기록은 bus/marathon/
- 막힌 것 / 태우 대기: 처음 보고한 "152회"는 합계 실수 — 164(통제 시간 안 124)로 고침. 태우 README 커밋 둘(1963386·51e93cf)에 작업 중 코드가 섞여 들어감. docs/eval/ 는 hook 의 .md 허용 위치 밖(태우 지정 경로라 그대로)
- 커밋: 1963386 51e93cf(섞임) ec77bcb f7405d6 9c06b4b / 이 항목의 커밋

## 2026-11-09 · T6.8 DONE (태우 "다음") · P7 승인
- 한 것: VWorld 는 키 대기(운영은 OSM 타일 12건, 전환 코드는 T5.1), MySQL 127.0.0.1:3307(compose, 다음 naru 재시작 때 적용), JTBC 서울마라톤 11/1 — 서울시 공지는 창만, 대회 누리집 `DATA` 에 풀 14·10K 8구간 시각·교차로 99행(저작권 All rights reserved) → 시각표 만들 수 있음(새 Task 제안)
- 정한 것: P7 계획(실시간 통제 지도·PWA 알림)·ADR-014 는 태우 "다음"을 추천안 전부 승인으로 받음 — 기존 P7 현장 실증은 P8, TOPIS 통제지도는 T7.3
- 막힌 것 / 태우 대기: marathon.jtbc.com 은 robots 뒤 9분 39초에 받아 10분 규칙에 21초 모자람(MANIFEST). VWorld 키
- 커밋: 97b78fa 3bb71d1 (하네스 a308709) / 이 항목의 커밋

## 2026-11-09 · T7.1 DONE (태우 "다음")
- 한 것: `GET /closures/events?at=&from=&to=` — 사건 id(sha1 reason·시작·끝 UTC 12자)·status(at 기준 가장 심한)·confidence(최대), 시간 창(시작 ≤ to, 끝(없으면 시작+6시간)+30분 ≥ from, 기본 at ~ 다음 날 24:00 KST), 300건 상한(truncated), ETag(본문 sha1)/304·no-cache. 계약 v0.14(area·centroid 칸, T7.2 까지 null), ADR-014 승인
- 정한 것: 겹침 유예 30분은 엔진 해제 유예와 같게, 상한은 심한 상태·시작 가까운 순, FE 기록(naru_api v2)은 T7.2 뒤로
- 막힌 것 / 태우 대기: 배포 때 BE 재시작 바로 뒤 워커 재시작(같은 계약을 읽는다)
- 커밋: 3824720 eeb2fde dd1dfeb dcf0e7a 209c0cf / 이 항목의 커밋

## 2026-11-09 · T7.2 DONE (태우 "순서대로 ㄱㄱ")
- 한 것: 접수 때 후보가 횡단보도를 고른 모양(점 30 m·선 15 m·구간 도로 경로 + 등급 버퍼, 경로 한 번 계산)을 사건 단위 union → 2 m 단순화 + 2 m 여유 → area·centroid, 표 closure_events(0005), 사건 API 가 id 로. 워커 배치 id 에 접수 판(t7.2) — 운영 기존 배치도 다시 접수돼 구역이 생긴다. FE 기록 셋(scripts/record_live_events.py: 11/7 15:30·11/9 13:30·3/15 07:45)
- 정한 것: 5 m 로 깎기만 하면 11/9 국회대로 횡단보도 둘이 0.6·1.1 m 밖 → 2 m + 여유, 중심이 밖이면 대표점, 한 사건 = 한 배치, 표 칸은 구역에 필요한 것만
- 막힌 것 / 태우 대기: 옛 배치(워커가 더 안 받는 11/7 돌발 등)의 사건은 운영에서 area null — FE(T7.4)가 다룬다
- 커밋: 0345515 44661eb b94ea6c 313c580 / 이 항목의 커밋

## 2026-11-09 · T7.3 DONE (태우 "다음")
- 한 것: TOPIS 교통통제 지도 목록(selectAccAllListASC)·통제 도로(selectAccLinkList) AJAX 를 10분에 요청 하나씩 번갈아(ADR-011 E) → 예정(N) 집회(10B02)를 후보로 — 경로 = 통제 도로 링크를 노드 이름으로 이은 선(꼭짓점 OA-13311 17개 기록), 통제 도로를 아직 못 받으면 대표 링크·그 이름. 확신도 0.85·공지 근거, 시작해 OA-13315 돌발이 오면 T6.1 연결로 통제 중. 전체 통제(accRoadYn)는 버스 기록 대상. 11/9 국회대로 행진: 경찰청 공지로 0곳 → 10:30 예정 75곳(9,489 m, 영등포·마포·서대문·종로) → 12:00 통제 중, 광화문 칩 "예정 29"
- 정한 것: 출처 topis·후보 ID topismap-<acc>-<k>(계획의 incident 재사용 대신 — 같은 ID 면 시작 때 경로가 돌발 링크 하나로 줄어든다, ADR-014 B 보충), 대상은 예정 집회만(통제 중·행사·공사는 OA-13315), 배치 id 에서 받은 시각 뺌, 통제 도로 없을 땐 대표 링크 이름
- 막힌 것 / 태우 대기: 시작 뒤 돌발 사건(링크 하나)이 따로 하나 더 보임·국회대로 제목이 경유지 9곳으로 김 → T7.5 카드에서. topis_map.py 커밋 316줄(200줄 규칙 넘음). 18:14 운영 재시작 실패(첫 시도 Next 빌드 ENOENT, 재시도는 5050·3050 사용 중 → kill 0 정상 종료로 멈춤) — 18:45 확인, 태우에게 알림(`sudo systemctl restart naru`)
- 커밋: a10d52a d2bc05c b7a11e3 66b0d40 900c56b / 이 항목의 커밋

## 2026-11-09 · T7.4 DONE (태우 "다음")
- 한 것: 앱을 열면 그 시각 서울 사건(/closures/events?at=t) — 줌 12 아래 사건 중심 클러스터(개수·가장 심한 종류 색, 숫자는 캔버스), 12~15 BE 구역, 15 부터 횡단보도(/closures 는 14 이상·길찾기만). 상태 5종(통제 중 빨강·1시간 안 진한 주황·예정 주황·예정 구역 보라·0.7 미만 회색 점선), 칩 = 사건 수 + 필터, 60초 If-None-Match(no-store, 304 면 그대로, 숨은 탭 쉼), 지금 모드(5분마다 t = 지금), 첫 화면은 사건 bbox 합집합(없으면 coverage), 카메라 #map=. 시트 목록·시간표 = 사건(해제·0.7 미만 빼고), 통제 불러오기(ClosureEvents)·빈 상태 버튼 삭제. 기록: 사건 v2 다시(경찰청 PDF·TOPIS 지도 — r05 0.65), 운영 11/7(구역 없는 옛 돌발 5). 성능: 사건 18.0·9.0·22.7 KB(gzip 4.0·2.6·5.7), 응답 23~35 ms, 칩 0.21초, 첫 맞춤 0.92초 안(SwiftShader), 서울 화면 /closures 0(전엔 264 KB)
- 정한 것: 1시간 안 = 시작 ≤ at+60분(이미 시작했는데 근거 없는 예정 포함), 0.7 미만은 지도에만, 해제는 안 그림, 칩 다 끄면 없음, 구역 없는 옛 사건은 bbox 가운데 점, 클러스터 누르면 풀리는 줌. 태우 "다음" 때 함께: deploy/naru.service Restart=always, e2e 범위 밖 = 경기 성남(잠실은 T6.9 부터 안), CONVENTIONS §5.4·§5.6(guard 로 하네스 커밋과 따로)·ARCHITECTURE FE 표(이 커밋)
- 막힌 것 / 태우 대기: 🧑 `sudo cp deploy/naru.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart naru`(T7.4 FE 도 함께 공개). e2e 11/7 15:00 경로 둘은 데이터 의존(11/7 돌발이 있으면 원래 길 '지금 못 감') — T7.3 데이터로는 통과. README '통제 불러오기' 줄은 기능이 없어짐(태우 문구). 300건 렌더는 실데이터가 16건까지라 못 잼
- 커밋: 691b26c 9bce18a 35af0ae 81602fd 6a0999e 9106aa2 f09be00 708bc34 fb0a09b f5cbc88 4f01a52 16f7a43 600b7de 13f72cb c832773 48b790e 7b75ee6 (하네스 3dd0aaf) / 이 항목의 커밋

## 2026-11-10 · T7.5 DONE (태우 실사용 고침 셋 — "지금 하는 Task 끝나면 이걸 먼저")
- 한 것: 시트 "지금 서울 통제"(LiveSheet) — 통제 중 → 1시간 안 → 오늘 → 내일 묶음, 구 칩, 행 = 버튼(오른쪽 남은 시간), 사건 카드(EventCard: 상태·원인 배지, 짧은 제목 + 지나는 곳 전부, 큰 남은 시간, 출처(TOPIS 통제지도 포함)·확신도 3단계·막히는 횡단보도·근거 원문). 지도 구역·점 → 카드(겹치면 묶음 목록), 클러스터 → 확대 + 묶음 목록, 고른 사건 굵은 윤곽·지도 맞춤, ?event=<id>. T7.4 마무리(태우 "다음" 때): deploy/naru.service Restart=always, e2e 범위 밖 = 경기 성남, CONVENTIONS §5.4·§5.6. 기록: 사건 v2 에 11/8 20:00('내일')
- 정한 것: TOPIS 지도 사건·돌발 사건은 안 묶음(응답에 통제 번호가 없다 — 묶으려면 BE 계약), 시작했는데 근거 없는 예정은 '확인 전', 카드 버튼은 근거 보기만(피해서 길찾기 T7.6, ☆ T7.10), 지도에서 고른 묶음엔 0.7 미만도, 길찾기 중엔 사건 안 열림, 긴 경로 제목은 처음·끝만(경유 3곳부터)
- 막힌 것 / 태우 대기: EventCard 첫 커밋이 lint 실패인 채 들어가(make check | tail && commit) push 전 되돌려 둘로 다시. 3ad9c69 는 교체라 +243/−245. README '통제 불러오기' 줄(태우 문구). 태우 11/10 실사용 셋 → T7.11~13(T7.6 앞), 운영 데이터 보충 승인
- 커밋: 1ce2ef7 b721f3f a92b241 adc764e ae25c98 2dec608 ddd02a2 3ad9c69 7512cff 8c5ca01 36262b3 (T7.4 마무리 c832773 48b790e 7b75ee6, 하네스 f132fda) / 이 항목의 커밋

## 2026-11-10 · T7.11 DONE (태우 "다음")
- 한 것: 슬라이더 날짜 칸 → 달력(그날 같은 시각, TimeProvider setDay, 24:00 이면 23:59), 시트 맨 아래 "예시로 보기" 셋(2026 서울마라톤 3/15 07:45 광화문 · 광화문 집회·행진 11/7 15:00 세종대로 · 국회대로 행진 11/9 12:00 — 그 시각 + 지도를 사건 v2 기록 bbox 에, 줌 12 이상), ClosureProvider frame. 공유 링크 회귀 그대로. **운영 데이터 보충(태우 승인)**: 워커 발행 경로로 돌발 11/7 15:40(처음엔 salt 없이 보내 중복 → 워커 _publish 로 다시 incident-b6487d088607, 후보 9·횡단보도 26)·TOPIS 통제지도 11/9 08:37(topismap-1510805dccc4, 후보 2·80)·돌발 11/9 14:55(incident-17a8e4380375, 후보 3·11). 운영 11/7 15:00 사건 8(구역 없음 5) → 10(0), 11/9 12:00 사건 5(지도 행진 없음) → 7(지도 행진 75곳 통제 중)
- 정한 것: 예시는 카드 없이 지도만 맞춤(태우 문구 그대로), 예시 줌 12 이상(9.5 km 행진을 다 담으면 11.6 이라 구역이 안 그려짐), 날짜를 바꿔도 시각 유지
- 막힌 것 / 태우 대기: 절반 시트에선 목록이 시트 밖(제목·기준 시각·시간표·슬라이더·구 칩이 다 씀, 달력으로 더) — T7.12·T7.13 에서. 🧑 `sudo systemctl restart naru`(T7.5·T7.11 공개)
- 커밋: b3a91b0 58fff40 f05d58d 414871f 74d3b6b (하네스 f7968e5) / 이 항목의 커밋

## 2026-11-10 · T7.12 DONE (태우 "다음")
- 한 것: 시트 세 묶음 — 지금(지금이 아니면 "이 시각": 통제 중 + 1시간 안, 비면 "지금(이 시각) 서울에 걸린 통제가 없어요")·다가오는 통제(KST 날짜별 오늘·내일·"11월 9일 (월)")·지난 통제(끝 늦은 순 5 + "더 보기 (N)"). 목록 = t 앞뒤 365일 넓은 창(catalog — 지도 사건과 따로 60초 ETag, 받기 전엔 지도 사건). 다가오는·지난 행 → 그 시작 시각(지금 모드 끔) + 카드 + 지도 맞춤(catalog 에서도 찾음). 지금이 아니면 시트 맨 위 "M월 D일 HH:MM 기준 · 지금으로 돌아가기"(제목 자리, 카드 위에도), 시트 슬라이더 '지금으로' 숨김, 구 칩은 목록 안. 행 배지: 지난 = 날짜, 다른 날 예정 = '예정'. 태우 11/10 "문장도 삭제" → 시트의 데이터 기준 시각 줄·경고 삭제(T7.13 에서 당김). 기록: 넓은 창 11/7 15:30·11/8 12:00(scripts/record_live_events.py). **develop push(태우 11/10)**: e97d6c3(태우 README 커밋)의 demo.gif 100.9 MB → 166fd63 의 388 KB 로 기록 정리(166fd63 빠짐, 뒤 커밋 해시가 바뀜 — 하네스 f8b2ddc 가 progress·plans 해시를 새 것으로)
- 정한 것: 넓은 창 ±365일(300 상한), 기준 줄이 제목 자리(절반 시트 목록 iPhone 13: 4 → 37 → 줄 삭제 75 px), 지금 판정 = 지금 모드이거나 ±5분, 더 보기는 시각을 옮겨도 펼친 채. demo.gif 커밋은 통째로 지우지 않고 gif 만 바꿈(README·hero_route.png 가 같이 들어 있어서)
- 막힌 것 / 태우 대기: 멈춤 경고는 T7.13 까지 없음. e2e 8 workers 에선 07:45 경로 카드가 5초를 넘길 때가 있다(혼자·4 workers 통과, /route 10 ms), 11/7 15:00 경로 둘은 데이터 의존 그대로. progress 의 T5.x 해시 54개는 이번 전부터 develop 에 없는 해시. 🧑 `sudo systemctl restart naru`(T7.12 공개)
- 커밋: d500df6 3d691c4 e35bb19 989a515 42a6bba 8e4bdfa 756fbd5 d066f71 ade02d4 5147e87 (하네스 fc35d7b · f8b2ddc) / 이 항목의 커밋

## 2026-11-10 · T7.13 DONE (태우 "다음")
- 한 것: TOPIS 돌발 배치를 30분 넘게 못 받으면 시트 부제 아래 "통제 정보가 N분째 갱신되지 않았어요"(평소·받은 적 없음은 아무것도 없음, 1분마다 다시 봄 — 멈추면 사건 응답이 304 라 안 그려져서), /licenses 맨 아래 "데이터 기준 시각"(예전 시트 문구 dataAsOfKo 그대로, client 컴포넌트 DataAsOf — 'use client' 경계 셋: CLAUDE.md §3-4·CONVENTIONS §5.3). 시트의 기준 시각 줄 삭제는 T7.12 에서
- 정한 것: 경고는 실제 멈춘 시간(N분째·시간째·일째), 자리는 예전 기준 시각 줄 자리(부제 아래), 카드엔 없음, /licenses 섹션은 맨 아래(태우 "페이지 아래에")
- 막힌 것 / 태우 대기: 경고가 뜬 화면은 실데이터로 30분 기다려야 해 못 찍음(운영 기록 렌더 테스트로 확인). INTERFACE §3.1 data_as_of 끝의 FE 설명("목록 위에 기준 시각 … 회색 경고")이 이제 다름 — 고칠지, ARCHITECTURE FE 표 'use client' 경계에 DataAsOf 를 더할지 태우 답 대기. T7.13 커밋은 아직 push 안 함. 🧑 `sudo systemctl restart naru`(T7.12·T7.13 공개)
- 커밋: 4e9ac09 05e57e0 9af59a1 (하네스 9e5ac07 · cc5276c) / 이 항목의 커밋

## 2026-11-10 · T7.6 DONE (태우 "다음")
- 한 것: 이 구역 피해서 길찾기 — 계약 v0.14 보충 `GET /route?avoid=<사건 id,…>`(ADR-014 A 그대로, 10개까지·없는 id 무시·응답 스키마 그대로), BE 사건 id → 상태(closure_states 묶음에서 계산 — 구역 없는 옛 사건도) → A* 가 그 횡단보도를 시각·확신도와 상관없이 뺌, avoided 에 그 시각 실제 상태. FE 사건 카드 "이 구역 피해서 길찾기"(목업 03 주 버튼) → 길찾기 + avoid, 시트 맨 위 "피하는 구역 · 제목 [빼기]", 원래 길 카드 "피한 구역 N곳"(보낸 사건의 reason·끝으로 알아봄), ?avoid= 공유 링크. 3/15 07:45 공유 링크 회귀 e2e(%2B·날짜 칸). 태우 11/10 중간: 해제 예정 뒤 30분(BE released_grace — 아직 막힘)을 "해제됨" 대신 "정리 중"(카드 "08:38까지 정리 중" + 까닭 한 줄, 배지·통제 근거 "정리 중 · 08:38까지", 길찾기 "09:00까지 정리 중"). 기록: route_avoid_0430·1330·route_0835(scripts/record_live_events.py)
- 정한 것: 피한 구역 판별은 계약을 늘리지 않고 FE 가(해제·예정 구역 상태는 avoid 로만 오니 그대로), 없는 id 는 400 대신 무시, 카드 버튼은 해제 사건에도, 정리 시간 30분은 FE 상수 RELEASE_GRACE_MS(BE released_grace_min 과 같이)
- 막힌 것 / 태우 대기: T7.13·T7.6 커밋 push 할지, INTERFACE §3.1 FE 설명 줄·ARCHITECTURE DataAsOf 줄(T7.13 질문) 대기. 임시 BE(5060)를 avoid 코드로 다시 띄움. 🧑 `sudo systemctl restart naru`(T7.12·T7.13·T7.6 공개)
- 커밋: d66fefc 5b03a84 9ab2c80 512f872 a1995d6 ffd6f02 af4013f 555387a 82c5584 (하네스 3b82834 · a59f82d) / 이 항목의 커밋

## 2026-11-10 · T7.14 DONE (태우 "다 확인완료. 커밋해서 푸쉬하고, T7.13은 너 fe설명줄을 고쳐")
- 한 것: 테스터 피드백 셋 — ① 장소 검색: 결과 줄마다 지도 가운데부터 거리, 줄을 누르면 flyTo(줌 17, 위 검색창·아래 시트 여백)·이름 핀·장소 카드([출발][도착][☆ 저장 — 이 기기 localStorage, 빈 검색칸에 저장한 장소]), 칸 검색도 지도 이동, 핀은 카드 닫기·지도 누르기·다른 검색으로 사라짐 ② 예시 칩 한 줄을 시트 맨 위(제목 아래, 접어도 보임 — iPhone 13 96px 안) + 지금 통제 없을 때 빈 안내 밑 큰 버튼, 누르면 그 시각·구역·사건 카드(맨 아래 예시 칸 뺌) ③ 통제 근거 확신도 0.90 → 카드와 같은 말(높음·보통·낮음, 단계 판정은 eventKinds.confidenceLevel 하나 — isLow 도), 숫자는 맨 아래 작은 회색. 태우 답 "T7.13 fe 설명 줄을 고쳐" → INTERFACE §3.1 data_as_of FE 설명(기준 시각은 /licenses, 시트는 TOPIS 30분 멈춤 경고만). make check 가 운영 워커의 빈 TOPIS 응답 기록(11/10 15:24, 200·빈 본문)으로 막혀 평가용 TopisNoticeSource 가 빈 본문을 건너뛰게(운영 워커 쪽은 소스 실패로 잡힘 — 그대로)
- 정한 것: 거리는 표시용이라 FE(geo.distanceM — BE distance_m 은 계약 변경), 홈 결과 줄의 [출발][도착]은 장소 카드로, 지도를 누르면(빈 곳·사건) 장소 닫힘, 예시 칩을 누르면 카드 맞춤(국회대로 행진은 줌 12 아래 윤곽)
- 막힌 것 / 태우 대기: 태우가 정할 것 — 공지만 있는 통제의 "확신도 높음"(≥0.8, 예: 11/7 r01 '확인 전' 카드에 확신도 높음)·카드 "막히는 횡단보도 N곳" 단정, "확인 전"(카드·목록) ↔ "공지상 통제 시간 · 현장 확인 전"(통제 근거·길찾기, INTERFACE §5) 통일. 교보빌딩 정문 앞(11/8 r03 unknown 0.45)은 리졸버가 '교보빌딩'(카카오 기록: 교보타워 강남·교보빌딩 안양)을 종로에서 못 찾아 후보가 안 됨 — AI 레인. ARCHITECTURE DataAsOf 줄은 답 없음. PC-7A: 태우 "다 확인완료" — B(T7.7)는 "다음"에. 🧑 `sudo systemctl restart naru`(T7.12~T7.14 공개)
- 커밋: 9c6cc38 261ba95 d352760 8078ae6 f8b1926 0f28b1a a4bef32 1f75b3b 24a3c0f 5f13124 (하네스 3ccdf53) / 이 항목의 커밋

## 2026-11-10 · T7.15 DONE (태우 "이어서 ㄱㄱ")
- 한 것: 통제 제보(교수님 멘토링 T-A) — 계약 §8(`POST /crosswalks/nearest` 좌표는 본문만·저장 안 함, `POST /reports` 201/400/429 `too_many_reports`, `GET /reports/recent`), Alembic 0006 reports(기기는 sha256), ReportDesk(STRtree 최근접 100 m, 같은 기기·횡단보도 600초 간격), prediction.blocked_at(라우터 §5 판정 함수 하나 — 라우터도 같이 씀), 현장 체크리스트 CSV·GeoJSON·field 제보 비교(recall·precision → docs/eval), FE 지도 '제보' 버튼 → 교차로명 핀·카드([막혔어요][열렸어요], 기록만 안내, ?mode=field 배지), 통제 근거 "최근 1시간 제보 N건". 기록만 — 경로·확신도에 안 씀
- 정한 것: 100 m·600초는 가정값(config, 11/14 뒤 수정), 제보 위치는 maximumAge 0·정확도 1000 m 초과면 안 보냄, 제보 버튼은 홈에만, 체크리스트 CSV 는 엑셀용 utf-8-sig·사유 첫 줄, FE 기록은 naru_test 만 쓰는 record_live_events 에(record_naru_api 는 naru DB)
- 막힌 것 / 태우 대기: 🧑 11/13 전 `sudo systemctl restart naru`(0006 적용). ARCHITECTURE 에 ReportDesk·reports·prediction 줄(DataAsOf 질문과 같이). 막는 장치는 기기·횡단보도 10분 간격뿐(토큰 지우면 새 기기, ?mode=field 누구나). 커밋 20개 미푸시. e2e 11/7 15:00 둘은 데이터 의존 그대로
- 커밋: 148c41f d3d356e 9a21337 a13153c 73c4a16 8648805 f9d8ea6 c9a9c36 623d34f 8d13d50 79f5127 2605639 742bbc5 b145692 cf3c74d 47482b5 5ecbaab 8f09e9d 057c4ad 80ab834 / 이 항목의 커밋

## 2026-11-10 · T7.16 DONE (태우 "③ + ① 로 가고 다음")
- 한 것: 행진 확률 모델(ADR-015) — 방향을 아는 행진(공지 구간이 이어짐·TOPIS 사슬 하나, 시작·끝)만 접수 때 경로 선·길이·행렬·횡단보도별 s 를 사건 행 JSON `march`(0007)에, `p_at`(21 표본 ±20%, 선행 300 m, 창 안 하한 예정 0.2·통제 중 0.5, 창 밖 0) 하나를 라우터(비용 = P x 360 m, P ≥ 0.8 제외, scheduled·confirmed 모두)·`GET /closures/events/{id}/march` 1분 키프레임(표본 점·중심·반경·횡단보도 P, 대상 아니면 404 not_modeled)·현장 체크리스트/비교가 같이 씀. FE heatmap·중심 원·P 6단계 점, 키프레임 보간, 카드 "이 시각 막혀 있을 확률 N%"·재생(12초, 네트워크 없음). INTERFACE v0.15 §3.2·§5·§6
- 정한 것: 폭은 지난 도로명 등급 최빈(같으면 넓은 쪽, 없으면 '로'), 구간이 지점으로만 풀린 후보가 있으면 대상 아님, 응답에 crosswalk_points·step_s·window 추가, 카드 확률은 경로 위 최대 P, 재생은 ClosureProvider playMs, e2e 는 행진 404 를 정상 응답으로. 처음 ±50% 는 국회대로 9.5 km 에서 P 가 전부 하한으로 눌려 태우 "③ + ①" — ±20%·통제 중 하한 0.5(ADR 표에 근거)
- 막힌 것 / 태우 대기: 긴 행진(행렬 200 m)은 ±20% 로도 P 가 하한(통제 중 0.5)에 머문다 — 11/14 현장 검증 뒤 가정값 재조정. 키프레임 본문 2.3 MB(gzip 65 KB) — nginx gzip 확인. 🧑 `sudo systemctl restart naru`(0006·0007). 커밋 46개 미푸시
- 커밋: 148c41f 2273652 adb8fd9 8cf8820 113d776 928d111 31c5c89 3162fbc 93a405b f5d8acf e867515 b4bde82 de0b4c2 c0a60d5 ba69320 a4722d9 cefab1b de64086 b45ad84 6c1a95b 3668966 3c7509a e7c26f4 f84aeae 1be80e9 8fea88e 98c169d (하네스 fd6bc7b) / 이 항목의 커밋

## 2026-11-10 · T7.17 DONE (태우 "다음")
- 한 것: 공개 `GET /closures/feed?at=`(INTERFACE §3.3, 이력만) — 그 시각 걸린 통제를 GeoJSON 으로(횡단보도 Point: 관리번호·교차로명·상태·확신도·행진 P / 사건 구역 Polygon / 행진 경로 LineString, 사건 칸 공통), /closures·/closures/events·/route 와 같은 조회·판정 재사용, 분 단위 캐시 60초(ETag·304·public max-age)·IP 분당 60회(429 rate_limited, X-Forwarded-For 첫 값), CORS *. README '데이터 피드' 절
- 정한 것: 같은 사건·횡단보도는 하나(가장 심한 상태), 캐시·제한은 gunicorn 워커마다(메모리), at 없는 요청도 분으로 내려 캐시, attribution 여분 멤버(공공누리 1유형·추정값)
- 막힌 것 / 태우 대기: 🧑 `sudo systemctl restart naru`(0006·0007·피드). 커밋 55개 미푸시. 피드 e2e 없음(HTTP 테스트·임시 스택 curl)
- 커밋: 07b6f23 193a071 2555050 18deb44 97d4bc4 1d8e2df 316a241 (하네스 e7d640a) / 이 항목의 커밋

## 2026-11-10 · T7.7 DONE (태우 "다시 ㄱㄱ" = 이어서)
- 한 것: PWA 바탕(ADR-014 D) — `app/manifest.ts`(나루·standalone·테마, 아이콘 PNG 192/512/maskable 은 app/icon.svg 를 뜬 것), `public/sw.js`(알림만: push → showNotification, 클릭 → /?event=, 캐시 없음), `push/usePush` 훅(sw.js 등록, 권한은 버튼에서만, Provider 없음), 시트 맨 아래 '통제 알림' 칸(버튼 / 허용됨 — 관심 지역은 다음 업데이트 / 꺼짐 / iPhone 홈 화면 안내 / 미지원). make serve 가 public/ 을 standalone 에 복사. CONVENTIONS §5 PWA 줄
- 정한 것: fetch 핸들러 없음, iPhone 판정 = UA + 터치 있는 MacIntel, 홈 화면(standalone)이면 보통 흐름, 구독은 T7.8 뒤
- 막힌 것 / 태우 대기: 🧑 VAPID 키(.env NARU_VAPID_PRIVATE_KEY·NARU_VAPID_SUBJECT) — T7.8 운영 구독에 필요. 🧑 `sudo systemctl restart naru`. 커밋 60개 미푸시. 헤드리스는 권한 창이 안 떠 버튼→허용 흐름은 e2e 밖
- 커밋: 01454f6 7658ad7 7b2078b fe48c42 8aa1e0d (하네스 70f2c31) / 이 항목의 커밋

