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

### nodelink (전국 원본, 수동 다운로드)
- 폴더: `data/raw/nodelink_20261014/` (820 MB — `MOCT_NODE.shp/.dbf/.shx/.prj`, `MOCT_LINK.*`, `MULTILINK.dbf`, `TURNINFO.dbf`, `내역서.csv`)
- 출처: 공공데이터포털 `국토교통부_표준노드링크` https://www.data.go.kr/data/15025526/fileData.do (기관 자체 다운로드 → 국가교통정보센터 https://www.its.go.kr/nodelink/nodelinkRef)
- 수집일: 2026-11-07 (태우가 로그인 뒤 zip을 받아 풀어 둠. 폴더명 20261014 = 배포본 날짜, 파일 수정시각 2026-10-13 08:44). `내역서.csv`는 이번 배포에서 추가된 노선 8건(김해·대구·충주·천안·영천·세종·대구 톨게이트)
- 라이선스: 이용허락범위 제한 없음 (포털 표기)
- 건수(원본, pyogrio `read_info`): 노드 1,184,340 / 링크 1,564,022 / MULTILINK 19,576
- 좌표계(.prj): `ITRF2000_Central_Belt_60` — TM, 중앙경선 127, 원점위도 38, FE 200000, FN 600000, GRS80. EPSG:5186과 변환 결과가 수치상 동일(최대 차 0.0°). dbf 인코딩 cp949
- sha256 (전체는 `nodelink_seoul_20261014/_meta.json` `source_sha256`): `MOCT_NODE.shp` `b2bb99ec…e4c9`, `MOCT_NODE.dbf` `cb3123c3…1de`, `MOCT_LINK.shp` `d9758a1e…e478`, `MOCT_LINK.dbf` `327fada1…28b1`
- 컬럼(실제): 노드 `NODE_ID, NODE_TYPE, NODE_NAME, TURN_P, UPDATEDATE, REMARK, HIST_TYPE, HISTREMARK` · 링크 `LINK_ID, F_NODE, T_NODE, LANES, ROAD_RANK, ROAD_TYPE, ROAD_NO, ROAD_NAME, ROAD_USE, MULTI_LINK, CONNECT, MAX_SPD, REST_VEH, REST_W, REST_H, C-ITS, LENGTH, UPDATEDATE, REMARK, HIST_TYPE, HISTREMARK`
- ID 체계(확인): 10자리. 앞 4자리 = 시군구(서울은 행정코드 순 1000 종로구, 1010 중구, 1020 용산구 … 1180 영등포구 … 1240/1249 강동구). 16xx 인천, 2xxx 경기. 확인 방법: 서울 bbox 안 노드를 prefix별로 중심 좌표·노드명(경복궁, 서울역, 당산역·여의도동)으로 대조

### nodelink_seoul (위 원본에서 추출, `make fetch SRC=nodelink`)
- 폴더: `data/raw/nodelink_seoul_20261014/` — `node.gpkg`(6.7 MB), `link.gpkg`(17.3 MB), `_meta.json`
- 스크립트: `scripts/fetch_nodelink.py` — OGR where `NODE_ID LIKE '10%' OR '11%' OR '12%'`(링크도 같음)로 읽어 GPKG로 저장. 좌표계는 .prj 그대로. 원본 수정 없음
- 건수: 노드 46,085 / 링크 63,383 (종로구 1,348/1,944 · 중구 1,212/1,696 · 영등포구 2,640/3,796). F·T 노드가 서울 밖인 링크 291
- 범위(WGS84): 126.7674~127.1829, 37.4305~37.6937 — 전부 서울 bbox 안 (스크립트가 검사)
- 확인: `ROAD_NAME == '세종대로'` 링크 59개(원본 전국에서도 59) — 광화문~서울역 126.9726~126.9773 / 37.5566~37.5753. 노드 `1000018200` = '경복궁'
- sha256: `node.gpkg` `4d2d3306…5b20`, `link.gpkg` `25f4adf5…7817` (GPKG는 쓸 때마다 타임스탬프가 들어가 재생성하면 값이 바뀐다)

### course (2026 서울마라톤 코스·통제 시각표, `make fetch SRC=course`)
- 폴더: `data/raw/course/`  스크립트: `scripts/fetch_course.py`  수집일: 2026-11-07
- 대회: 2026 서울마라톤 (2026-03-15 일, 07:30 광화문광장 출발 → 잠실종합운동장 동문, 풀 42.195 km). 주최 서울특별시·동아일보사·대한육상연맹. 누리집 https://www.seoul-marathon.com (2027 대회로 바뀌어 코스도 "추후 공개 예정")
- 출처
  - 시각표·코스 설명: 서울시 '내 손안에 서울' 기사 https://mediahub.seoul.go.kr/archives/2017411 (발행 2026-03-12 16:07, 표 "2026 서울마라톤(3.15) 구간별 교통 통제·해제 시간") → `seoul_marathon_2026_mediahub.html` 원문 저장 (sha256 `11502edc…784b`)
  - 서울시 교통통제 안내 포스터 https://news.seoul.go.kr/culture/files/2026/03/69abc0050fb8b8.44799486.jpg (공지 https://news.seoul.go.kr/culture/archives/531848) → `seoul_marathon_2026_poster.jpg` (sha256 `ced16ad7…34b2`). 같은 표 + 코스 설명 문장 "이순신 동상 앞(출발)-남대문(좌)-을지로1가(우)-동대문역사문화공원-시청삼거리(우)-청계로-고산자교(U턴)-모전교(우)-종로구청입구사거리(우)-종로-동대문-신설동 오거리-천호대로-군자역(우)-어린이대공원역(우)-광나루길-성동교(좌)-서울숲-잠실대교-잠실역(우)-잠실새내역-잠실종합운동장(도착)"
  - 코스 지도(km 표지 대조용, 저장 안 함): 한국경제 2026-03-04 기사 "2026 서울마라톤 코스. 서울시 제공" https://www.hankyung.com/article/202603048128i
- 라이선스: 서울시 기사·포스터는 공공누리 제4유형 표기(출처표시·상업적 이용 금지·변경 금지). GPX는 표준노드링크(제한 없음) 위에 우리가 그린 파생물
- `seoul_marathon_2026_timetable.json` (sha256 `a637ea1d…9692`): `event{name,date,start,finish,start_time}` + `segments[16]` = 출발지 + 1~15구간. 행마다 `label, section, control_start, control_end`(ISO +09:00), `source_url, published_at, fetched_at`. 예: 1구간 "세종대로 사거리~숭례문 오거리" 07:20~08:08, 15구간 "종합운동장 동문 앞~종합운동장 사거리" 05:00~14:30. 11~14구간(송파역·석촌역·가락시장)은 10 km 코스 구간
- `seoul_marathon_2026.gpx` (sha256 `79bdd885…9850`, 점 870개, 웨이포인트 18개): **공식 GPX 없음 → 디지타이즈.** 포스터 코스 설명의 교차로 17개 구간을 `nodelink_seoul_20261014` 노드(NODE_NAME 또는 두 도로명 링크 공유 노드)로 잡고, 구간별 허용 도로명 링크만으로 무방향 최단경로를 이어 붙임. 길이 **42.534 km (공식 대비 +0.8%)**, 폴백 0. 코스 지도 km 표지(5·7.5·22.5·27.5·32.5·37.5·40)와 누적 거리가 맞는 것을 확인. 청계천로 왕복(청계6가→청계광장→고산자교→무교동)은 같은 차로 링크를 왕복으로 씀
- `seoul_marathon_2026_course_meta.json`: 구간별 노드·허용 도로·실제 지난 도로·길이·폴백 여부, 출처 URL
- 세종대로 통과: 1·2구간(출발~세종대로사거리~숭례문)이 세종대로. 테스트 `packages/ai/tests/test_course_data.py`

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
