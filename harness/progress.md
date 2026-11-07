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
