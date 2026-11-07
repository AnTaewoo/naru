# data/MANIFEST.md — 실데이터 대장

규칙: `.claude/skills/real-data-testing/SKILL.md` §2. 여기 없는 데이터는 테스트에 쓸 수 없다.
`data/raw/`, `data/recorded/`는 gitignore. 이 파일만 커밋한다. 항목은 P0 Task에서 채운다.

## raw

### seoul_spatial
- 폴더: `data/raw/seoul_spatial_20261107/` (31 MB — API 응답 페이지 원문 `<start>-<end>.json` + 파일 2개 + `_meta.json`)
- 출처: 서울 열린데이터광장 Open API `http://openapi.seoul.go.kr:8088/<키>/json/<서비스>/<start>/<end>/` (한 번에 최대 1,000건, 이용안내)
- 수집일: 2026-11-07  스크립트: `scripts/fetch_seoul_spatial.py` (`make fetch SRC=seoul_spatial`), API 78회. 재실행하면 있는 페이지는 건너뛴다
- 라이선스: 공공누리 1유형 (출처표시)
- 좌표계: API의 `NODE_WKT`·`LNKG_WKT`는 WGS84 (확인: 종로·중구 데이터가 126.9~127.1 / 37.45~37.70 안 — `packages/be/tests/test_seoul_spatial_data.py`)

| 폴더 | 서비스 · 데이터셋 | 건수 (2026-11-07, `list_total_count`) | 비고 |
|---|---|---|---|
| `TbTraficWlkNet_jongno/` | `TbTraficWlkNet` SGG_NM=종로구 — OA-21208 서울시 자치구별 도보 네트워크 공간정보 (갱신 2026-11-07, 매일) | 19,266 (NODE 9,055 / LINK 10,211 / CRSWK=1 링크 963) | 20 페이지 |
| `TbTraficWlkNet_junggu/` | 〃 SGG_NM=중구 | 13,622 (NODE 6,272 / LINK 7,350 / CRSWK=1 링크 1,056) | 14 페이지 |
| `tbTraficUndpass/` | OA-21213 서울시 지하철역 연계 지하도 공간정보 (서울 전체) | 6,563 (종로 366 / 중구 469) | `SBWY_STN_NM`·`LIFT`·`ELVT` 포함 |
| `tbTraficBrdge/` | OA-21210 서울시 육교 공간정보 (전체) | 2,967 (종로 106 / 중구 115) | |
| `tbTraficElvtr/` | OA-21212 서울시 지하철역 엘리베이터 위치정보 (전체) | 552 (종로 16 / 중구 30) | NODE만 |
| `tbTraficEntrcLft/` | OA-21211 서울시 지하철 출입구 리프트 위치정보 (전체) | 83 (종로 16 / 중구 6) | NODE만 |
| `tbTraficCrsng/` | OA-21209 서울시 대로변 횡단보도 위치정보 (전체) | 31,080 (종로 1,080 / 중구 1,098) | 32 페이지 |

- 컬럼(실제, API row에서 복사): `NODE_TYPE, NODE_WKT, NODE_ID, NODE_TYPE_CD, LNKG_WKT, LNKG_ID, LNKG_TYPE_CD, BGNG_LNKG_ID, END_LNKG_ID, LNKG_LEN, SGG_CD, SGG_NM, EMD_CD, EMD_NM`
  - 도보망(`TbTraficWlkNet`)에만: `EXPN_CAR_RD, SBWY_NTW, BRG, TNL, OVRP, CRSWK, PARK, BLDG, WORK_DTTM` (플래그는 "0"/"1"/"" 문자열)
  - 지하도에만: `SBWY_STN_CD, SBWY_STN_NM, LIFT, ELVT` · 엘리베이터·리프트(NODE만): `SBWY_STN_CD, SBWY_STN_NM`
  - NODE 행은 `LNKG_*`가 빈 값/0, LINK 행은 `NODE_*`가 빈 값/0. `NODE_ID`·`LNKG_ID`는 float로 온다 (예: 149760.0)
- 파일 1: `OA-23081.xlsx` — 서울시 교차로 및 횡단보도 시설·위치정보 (원본 파일명 `서울시 교차로 및 횡단보도 시설·위치정보_20260824.xlsx`, 갱신 2026-09-07, 원본 T-GIS)
  - 출처: https://data.seoul.go.kr/dataList/OA-23081/S/1/datasetView.do  라이선스: 공공누리 1유형
  - sha256: `1a5db9ea7a1cd58e2d7f2b4246baf099a3e4d5278f2867a1b87f3d50d21541be`  행 수: 21,776 (종로구 590, 중구 621, 25개 자치구)
  - 컬럼(실제): `연번, 자치구, 횡단보도관리번호, 교차로관리번호, 횡단보도종류, 보행등유무, 교차로명, X좌표, Y좌표`
  - **좌표계: EPSG:5186 (중부원점 TM). WGS84 아님.** 확인: 교차로명 '세종대로사거리' 8행(교차로관리번호 535)을 5186→4326 변환하면 (126.976, 37.570) 광화문 앞. 5181·5174·2097은 위도 38.47로 튄다. BE는 5186→5179로 변환해 쓴다
- 파일 2: `OA-21208_codes.xlsx` — `도보네트워크_링크노드유형코드.xlsx` (OA-21208 첨부, 수정일 2024-07-05). 시트 `링크유형코드`(LINK_CODE 4비트 보행자/차량/자전거/PM, `1000`=보행자), `노드유형코드`(0 일반, 1 지하철 출입구, 2 버스 정류장, 3 지하보도 출입구)
  - sha256: `c718a21352d91b2a9be50e8c52ed886d92a495adb14070995b487b0ca5ab4e4f`
- 안 받은 것: OA-22906 서울특별시 자치구 횡단보도 정보 (API `crossRoadNOWON`, 40,282행, 경위도·관리번호 있으나 교차로명 없음 — OA-23081로 충분)

## recorded

| api | 최초 기록 | 파일 수 | 비고 |
|---|---|---|---|
| | | | |

## field (현장 테스트 묶음)

| 날짜 | 장소 | 포함 | 비고 |
|---|---|---|---|
| | | | |

## 수집 예정 (ROADMAP 참조)

### 파서 학습·평가
- 서울경찰청 '오늘의 집회' PDF (일시·장소·행진경로·인원·관할서, 로그인 필요, 수동) — T0.5a **← 라벨 정답**
- 자유 텍스트 통제 공지 50건 (spatic.go.kr, X @poltraffic02, TOPIS 공지 API(2유형), 서울시 보도자료, 언론) — T0.5b
- (없는 것) AI Hub·서울시 AI 학습데이터에 교통 공지 데이터셋 없음. 경찰청 집회 신고 현황 공공데이터 없음. 서울시 집회 통계는 2015년 종료

### 광화문 공간 베이스 (1유형 또는 제한 없음)
- 자치구별 도보 네트워크 OA-21208, 교차로·횡단보도 OA-23081, 자치구 횡단보도 OA-22906 — T0.2
- 지하철역 연계 지하도·육교·출입구 리프트·엘리베이터 (OA-21230 연관데이터) — T0.2
- 국토부 표준노드링크(서울) — T0.3
- 서울교통공사 역내 최단경로이동·출입구 임시폐쇄·승강기 + 서울시설공단 지하도상가 운영시간 — T0.8
- 서울시 보도통계자료 (보도 폭·길이, 좌표 없음) — 보류, 폭 보강 필요해지면
- (보류) 3D: 국토지리정보원 3D 건물 모형은 제공 신청 필요, S-Map은 뷰어 전용. v0.2에선 안 씀

### 실시간 신호
- 서울시 버스위치정보 (data.go.kr 15000332), 서울 실시간 도시데이터, TOPIS 실시간 돌발정보 OA-13315 — T0.4
- S-DoT 유동인구 측정 정보 OA-22832 (센서 126개, 10분) — T0.7, 광화문 근처 센서 유무 확인 후 채택
- 집회 당일 버스 기록 1시간 — T4.2 전, field 묶음과 같은 날
