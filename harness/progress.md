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
