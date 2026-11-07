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
