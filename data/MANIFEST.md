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
| `TbTraficWlkNet_seoul/` | `TbTraficWlkNet` 필터 없음 — OA-21208 서울시 자치구별 도보 네트워크 공간정보 (갱신 2026-11-07, 매일). **이걸 쓴다** | 491,082 (유일 ID 491,082 = 완전. 종로구 19,266 = NODE 8,552 / LINK 10,714, 중구 13,622) | 492 페이지, 492회 호출 (16:04~16:14) |
| `TbTraficWlkNet_jongno/` | `TbTraficWlkNet` SGG_NM=종로구 | 19,266행이지만 **페이지가 서로 겹쳐 유일 행 14,221(74%)뿐** — SGG_NM 필터 API의 결함(T1.1에서 발견). 원본은 두되 쓰지 않는다 | 20 페이지 |
| `TbTraficWlkNet_junggu/` | 〃 SGG_NM=중구 | 13,622행, 유일 8,748(64%). 같은 결함 | 14 페이지 |
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
- `seoul_marathon_2026_10km.gpx` (T2.2에서 추가, 점 154개): 10 km 코스 디지타이즈 — 종합운동장교차로 → 출발 종합운동장역(동문) → 올림픽로 → 잠실역사거리 → 송파대로 → 석촌역사거리 → 가락시장역사거리(U턴) → 되돌아 → 동문 도착. 첫 구간 285 m는 15구간 "동문 앞~종합운동장 사거리" 통제구간(코스 아님). 코스 길이 **11.44 km로 공식 10 km보다 14% 길다** — 반환점을 가락시장역 사거리로 잡았는데 지도 5 km 표지는 그보다 몇백 m 앞. 12·13구간(송파대로 왕복) 통제 선으로 쓰기엔 보수적(조금 넓음). 석촌역~가락시장역 2구간은 송파대로 링크가 끊겨 폴백
- `seoul_marathon_2026_course_meta.json`: 구간별 노드·허용 도로·실제 지난 도로·길이·폴백 여부, 출처 URL. `course_10km` 항목에 10 km 코스 같은 정보
- 세종대로 통과: 1·2구간(출발~세종대로사거리~숭례문)이 세종대로. 테스트 `packages/ai/tests/test_course_data.py`

### notices/smpa (서울경찰청 '오늘의 주요집회' PDF, 수동)
- 폴더: `data/raw/notices/smpa/` — `261107(토) 오늘의 주요집회.pdf`, `261108(일) …`, `261109(월) …` (각 1쪽, Hwp 2018 → Hancom PDF, 작성자 '정보상황실'). 태우가 2026-11-07 게시판(로그인)에서 받아 원본 파일명 그대로 둠
- 출처: 서울경찰청 '오늘의 집회' 게시판 https://www.smpa.go.kr/user/nd54882.do (로그인·robots로 막혀 자동 수집 안 함, 태우 수동). 문서 안 "(2026. 11. 6. 18:00 기준 작성)" → `published_at`, 제목 옆 날짜 → `event_date`
- sha256: 1107 `11d443cc…a82f`, 1108 `71aca42d…394f`, 1109 `4e5ff583…4abc`
- 표 머리글(실제): `집회 일시 | 집회 장소(행진로) | 신고인원 | 관할서 | 비고`. 행 수(눈으로 셈, 2026-11-07): 6 / 3 / 4 = 13
- 라이선스: 경찰청 공개 게시물 (별도 표기 없음). 문장 원문은 공개 정보
- inbox (T6.6, 운영): 태우가 받은 PDF 를 `data/raw/notices/smpa/inbox/` 에 넣으면 운영 워커가 1분 안에 읽어(표 = 위와 같은 SmpaPdfSource, 행마다 `smpa-<집회 날짜>-r<행>-u<기준 작성>`) 후보를 보내고 `data/raw/notices/smpa/<집회 날짜 YYYYMMDD>.pdf` 로 옮긴다(이름이 있으면 `-u<기준 작성>`·`-<sha256 앞 8>`, 내용은 그대로). 옮길 때마다 `data/raw/notices/smpa/inbox_manifest.jsonl` 에 한 줄 — 파일·넣은 이름·sha256·바이트·행 수·집회 날짜·기준 작성·넣은 시각(파일 시각)·옮긴 시각·파싱 실패 행·출처 URL·라이선스. 이 폴더의 PDF 별 출처 기록은 그 jsonl 이 맡는다(워커가 쓰니 git 밖, .gitignore). 똑같은 파일(sha256)은 `inbox/duplicate/`, 표가 아니면 `inbox/failed/` — 지우지 않는다

### recorded/topis_notice (TOPIS 공지 NoticeList)
- 파일: `data/recorded/topis_notice/20261107T153007.json` (818 KB, sha256 `4bee5a87…8ba6`) — `scripts/build_notices.py --topis` 1회 호출, 최신 300건
- 출처: 서울 열린데이터광장 OA-22861 서울 교통정보시스템(TOPIS) 공지사항 https://data.seoul.go.kr/dataList/OA-22861/S/1/datasetView.do — Open API `NoticeList`, **xml만** (json은 ERROR-301), 한 번에 1,000건. 라이선스 공공누리 2유형(출처표시·상업적 이용 금지)
- 필드(실제, xml 소문자): `bdwr_seq, bdwr_rtng_cd, bdwr_rtng_nm, bdwr_div_cd, bdwr_div_nm, bdwr_ttl_nm, bdwr_cts(HTML 이스케이프된 리치텍스트), update_date, create_date("2026-11-06 11:31:55"), url(https://topis.seoul.go.kr/notice/openNoticeView.do?blbdDivCd=02&bdwrSeq=…)`
- 300건 범위: create_date 2026-05-08 ~ 2026-11-06. 분류 통제안내 154 · 버스안내 104 · (그 외 정책·기상·기타 42는 문장으로 안 씀)
- 파일: `data/recorded/topis_notice/20261108T192013.json` (83,365 B, sha256 `78eb77cea8f658b8b966b7520db340c24890df15b7b75d7a1dd1cc5f9fdc18ce`) — 2026-11-08 19:20:13 KST, `scripts/build_notices.py` 의 `record_topis(…, 30)` 1회(T6.4 시작 때 게시판과 비교 — 최신 글 6301 로 같다). 30행: 통제안내 10 · 버스안내 18 · 기타안내 2, create_date 2026-10-26 ~ 2026-11-06. `sentences.jsonl` 은 다시 만들지 않았다(T0.5 줄 단위 문장은 그대로)
- 운영(T6.4): 워커 `NARU_TOPIS_SOURCE=live` 가 10분마다 최신 50건을 받아 내용이 바뀔 때만 `<ts>_NoticeList.json` 으로 더한다(같으면 마지막 기록을 가리킨다). 글 하나 = 파서 문장 하나(`topis-<번호>-u<고친 시각>`)

### notices/sentences.jsonl (T0.5 산출, `uv run python scripts/build_notices.py`)
- 파일: `data/raw/notices/sentences.jsonl` (1,923,366 B, 2,821행, sha256 `d69c8115fe9c3fc3dabb8cc63d0082285eedd5812f4563ed5ef37d9b42e2dbd5`; 2026-11-08 `scripts/append_fewshot_sentences.py` 로 프롬프트 v2 예시 원문 11행(N001·N006·N009·N011·N045·N049·N059·N067·N070·N099·N100, fields.fewshot) 추가. news 2행(N099·N100) 출처 URL 은 태우 확인 econovill 756361) + `sentences_meta.json`. git에 올리지 않는다(.gitignore `data/raw/notices/*.jsonl|*.json`) — raw 규칙. 다시 만들려면 PDF + recorded로 `uv run python scripts/build_notices.py`
- 레코드: `sentence_id, notice_id, text, context_prev, context_next, source_type(smpa|topis), source_url, published_at(+09:00), fetched_at, event_date, fields`
- smpa 13행: 표 행 하나 = 문장 하나. `text` = 셀을 왼쪽부터 공백으로 이은 원문(빈 비고 제외), 셀 안 줄바꿈만 공백. 예 `smpa-20261107-r01` "12:00~16:00 동화면세점 앞 → 종로1R → 동화면세점 앞 <세종대로 등> 50,000명 종로, 남대문". `fields`에 time/place/headcount/station/note/file
- topis 2,797행(공지 258건): 제목(l000) + 본문 줄(l001~). 본문은 블록 태그(p/br/div/li/tr)에서만 줄을 나누고 인라인 태그(span/b)는 지움 — 글자는 손대지 않음. `fetched_at` = 기록 파일 `called_at`. 예 `topis-6301-l005` "- 의사당대로 국회앞교차로 → 글래드호텔 앞 3개차로 통제"
- 안 한 것: 보도 문장(naru-reader 수집본 import) — 이 머신에 naru-reader 저장소가 없다

### bus_routes_20261108 (서울시 버스노선별 정류소, T6.2)
- 출처: 서울 열린데이터광장 OA-1095 "서울시 버스노선별 정류소 정보" https://data.seoul.go.kr/dataList/OA-1095/S/1/datasetView.do — 매월 XLSX(키 없음). `make fetch SRC=bus_routes` → `scripts/fetch_bus_routes.py` 가 페이지의 가장 최근 파일(seq)을 읽어 `nio_download.do` 로 한 번 받는다(frmFile infId OA-1095·seq 58·infSeq 2 — 페이지의 다른 폼 infSeq 4 는 HTML 이 온다). robots.txt: data.seoul.go.kr 전부 허용, datafile.seoul.go.kr 없음 (2026-11-08 확인). 공공누리 1유형
- 파일: `data/raw/bus_routes_20261108/OA-1095.xlsx` (원래 이름 `서울시버스노선별정류소정보(20260902).xlsx`, 3,251,120 B, sha256 `b54816e9…b1df`) + `_meta.json`
- 칸(실제): `ROUTE_ID, 노선명, 순번, NODE_ID, ARS_ID, 정류소명, X좌표, Y좌표` — **X·Y 는 WGS84 경위도**(126.43~127.19, 37.18~37.83). 41,688행, 노선 718개. 세종대로 일대(126.970~126.981, 37.558~37.575)에 정류소가 있는 노선 98개 — 심야(N)·새벽 노선이 섞여 있어 버스 폴러는 뺀다
- 노선 경로(폴리라인)는 없다 — 정류소 순서만. 경로는 아래 `bus_routes/<날짜>/` (getRoutePath, 태우 결정 — 도로 그래프로 정류소를 잇지 않는다)

### bus_routes/<날짜>/path_<노선>.json (노선 경로, 운영 워커)
- 출처: data.go.kr 15000193 서울특별시_노선정보조회 서비스 `http://ws.bus.go.kr/api/rest/busRouteInfo/getRoutePath` (`busRouteId`, `resultType=json`). 워커가 부른 노선마다 하루 한 번, 받은 그대로(키 가림, 기록 형식 `api, endpoint, params, called_at, status, raw`). 키는 `DATA_GO_KR_ROUTE_KEY`(없으면 `DATA_GO_KR_KEY`)
- 2026-11-08 18:5x 확인(live 2, 노선 01A 100100001): HTTP 401 `{"error":"Unauthorized","message":"유효하지 않은 서비스키입니다: 등록되지 않은 서비스키","status":401}` — 이 키로는 활용신청이 안 돼 있다(태우 신청). 아직 파일 없음
- 2026-11-09 07:56 KST `data/raw/bus_routes/20261109/` 8개 (T6.3, 워커와 같은 `RoutePaths.ensure`, live 8) — 기록된 버스 위치(recorded bus 11/8 18:38~18:48)의 노선. 형식(실제): `msgBody.itemList[]` = `no`(정점 순번 = 운행 순서), `gpsX`·`gpsY`(WGS84), `posX`·`posY`(EPSG:5181 — Y 가 45만대). 라이선스: 포털(data.go.kr 15000193) 이용허락범위 표기 아직 확인 안 함
  - `path_100100001.json` 77,918 B sha256 `ce7c1c0c7cb3…` 정점 599 · `path_100100033.json` 312,864 B `5d63e28d27c3…` 2,406 · `path_100100042.json` 198,233 B `eb9c369e62c3…` 1,528 · `path_100100046.json` 217,342 B `32f90853c746…` 1,680 · `path_100100118.json` 189,073 B `193372278688…` 1,469 · `path_100100185.json` 131,167 B `c1138aa73cf3…` 998 · `path_100900003.json` 46,323 B `ef68f59ba97d…` 349 · `path_100900007.json` 68,848 B `b67c3a108246…` 522
  - 확인(T6.3 test_bus_correction): 기록된 버스 94대가 경로에서 가운데값 0.49 m·최대 17 m — 노선에 맞춘 좌표로 보인다. 노선 길이는 버스 기록의 `rtDist`(km)와 비슷하다(100100001 경로 15.16 km · rtDist 16)

## recorded

| api | 최초 기록 | 파일 수 | 비고 |
|---|---|---|---|
| topis_notice | 2026-11-07 | 2 | TOPIS 공지 NoticeList 최신 300건 (xml) + 2026-11-08 최신 30건(T6.4). 운영 워커가 10분마다 바뀔 때만 더한다. 아래 "recorded/topis_notice" |
| incident | 2026-11-07 | 4 | TOPIS 돌발 — AccMainCode 13 · AccSubCode 43 · AccInfo 53행 (`make record API=incident`). 2026-11-08 AccInfo 1(워커 live 경로 확인, T6.1). 운영 워커(`NARU_INCIDENT_SOURCE=live`)가 5분마다 내용이 바뀔 때만 더한다 |
| links | 2026-11-07 | 14 | 돌발 링크 4개의 LinkInfo + LinkVerInfo (`make record API=links --limit 4`) + 2026-11-08 집회 링크 3개(`--links`, T6.1). 운영 워커는 처음 보는 링크만 받아 더한다 |
| rtd | 2026-11-07 | 2 | 실시간 도시데이터 citydata 광화문·덕수궁 (json) — 11/7 15:41(175 KB) + 11/9 08:28(T6.5, 사고통제현황 0건) |
| topis_web | 2026-11-09 | 3 | TOPIS 홈페이지 원문(T6.5 조사, ADR-011 E — robots 허용·같은 곳 10분 간격·NaruBot): 통제지도 openControlMap.do 와 그 내부 AJAX 응답. 아래 "recorded/… (T6.5 조사)" |
| data_go_kr_web | 2026-11-09 | 1 | 공공데이터포털 15088841(경찰청_교통돌발정보서비스) 페이지(T6.5) |
| seoul_opendata_web | 2026-11-09 | 1 | 열린데이터광장 OA-21285(실시간 도시데이터) 페이지(T6.5 — 라이선스 확인) |
| kakao | 2026-11-07 | 3 | 로컬 키워드 검색 숭례문·덕수궁·교보빌딩 (`kakao/keyword/<sha1(검색어)>.json`, 리졸버 재생용). 아래 "recorded/kakao" |
| kakao/local | 2026-11-08 | 10 | BE 지오코딩 재생용(T5.8, ADR-011 B) — 역지오코딩 4·키워드 6(쓰는 것 3) (`make record API=geocode`). 아래 "recorded/kakao/local" |
| bus | 2026-11-07 | 9 | 버스위치 getBusPosByRtid 노선 100100118, 차량 12대 (json) + 2026-11-08 광화문 노선 7개(`--routes`, T6.2) + 워커 live 경로 확인 1(100100118). 운영 워커(`NARU_BUS_SOURCE=live`)가 `bus/notice/`(공지 통제 창, 60초)·`bus/incident/`(TOPIS 집회·행사 돌발 기준 데이터, 120초, 하루 300)에 더한다(전체 하루 900). 나누기 전 9개는 `bus/` 바로 아래 그대로. 아래 "recorded/bus" |
| candidates/course | 2026-11-07 | 1 | `make record-candidates SOURCE=course` — CourseIngestor(T2.2) 출력 `CandidateBatch` 그대로: 후보 16개(시각표 16구간, geometry line, scheduled, confidence 0.9, evidence timetable, v0.6 `impact: blocks`·`toward: null`·`approx: false`). BE 테스트(T2.3)가 naru_ai 없이 최신 파일을 읽는다. 유효본은 `20261107T194153.json`(ADR-008 반영 재기록). 그 전 둘(185022 조각 겹침, 185247 impact 없음)은 삭제 대상. 2026-11-08 T5.9: 같은 입력으로 `20261108T162816.json`(sha256 54b369cb1c6a…, 후보 16 그대로, summary null) — 새 batch_id 라야 개발 DB 의 기존 행에 v0.12 메타(source·type)가 채워진다 |

### recorded/bus (서울 버스위치정보, data.go.kr)
- 출처: http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid (`serviceKey`=data.go.kr 일반 인증키, `busRouteId`, `resultType=json`). 개발계정 일 1,000회
- 파일: `data/recorded/bus/20261107T155630_getBusPosByRtid.json` (6 KB)
- 응답(실제): `comMsgHeader`, `msgHeader{headerCd("0"=정상), headerMsg, itemCount}` — **itemCount는 0으로 와도 itemList에 12대가 있다**, `msgBody.itemList[]{vehId, plainNo, busType, dataTm(YYYYMMDDHHmmss KST), gpsX, gpsY(WGS84 문자열), posX, posY, tmX, tmY, sectOrd, sectionId, sectDist, fullSectDist, rtDist, stopFlag, lastStnId, lastStTm, nextStId, nextStTm, isrunyn, islastyn, isFullFlag, congetion, trnstnid}`
- 노선 100100118은 활용가이드 예시 노선. 기록 시각 15:54~15:56, 차량 위치 126.909~126.959 / 37.495~37.614 (서울 서부). P6 버스 우회 감지에서 광화문 경유 노선으로 바꿔 기록한다
- 2026-11-08(일) 통제 없는 날 (live 7, T6.2 — `uv run python scripts/record_api.py --api bus --routes …`, 파일 `<ts>_getBusPosByRtid_<노선>.json`). 노선은 11/7 공지 통제 r04·r01 횡단보도 100 m 안 정류소가 많은 순(OA-1095):
  - 18:38 — 종로11 100900007 4대 (`8c9d40c0aa4f…`) · 종로09 100900003 5대 (`2fa5f51ab643…`) · 01A 100100001 7대 (`70a43d637aa2…`, INTERFACE §1.2 예시)
  - 18:44 — 1711 100100185 11대 (`df2f2ee5289d…`) · 160 100100033 20대 (`2fb4026fa17c…`) · 260 100100042 17대 (`43e15b789d34…`) · 270 100100046 18대 (`9d4b67f28224…`)
  - 전부 headerCd 0. 마을버스(종로09·11)는 `nextStId` "0". `sectDist`·`fullSectDist` 는 km 로 보인다(0.327·0.214). `tmX/tmY` 는 null 일 때가 있다 — 좌표는 `gpsX/gpsY`(WGS84)만 쓴다
  - 18:48 — 워커 `BusApi` live 경로 확인(키 가림·하루 호출 수 세기): 예시 노선 100100118 12대 `20261108T184839_getBusPosByRtid_100100118.json` (`ad792b80f08b…`) — 테스트가 쓰는 노선의 "가장 최근 기록"을 바꾸지 않으려고 예시 노선으로. 이날 호출 수 8 = 기록 파일 수
  - 통제일 기록은 아직 없다 — T6.3 통합 시험은 그날 기록이 생겨야 한다(실측 대기)

### recorded/kakao (카카오 로컬 키워드 검색)
- 출처: https://dapi.kakao.com/v2/local/search/keyword.json (`Authorization: KakaoAK <REST 키>`). 앱 `naru`에 카카오맵(로컬) API 사용 설정 필요(꺼져 있으면 403 "disabled OPEN_MAP_AND_LOCAL service"). 이용약관상 결과 저장은 서비스 내부 캐시 용도
- 파일: `data/recorded/kakao/keyword/765cd74f…9fc45.json`(숭례문), `18b733ab…f40f.json`(덕수궁) — 파일명은 sha1(검색어)
- 필드(실제): `meta{total_count, pageable_count, is_end, same_name}`, `documents[]{id, place_name, category_group_code, category_group_name, category_name, address_name, road_address_name, phone, place_url, distance, x(경도), y(위도)}` — 좌표는 WGS84 문자열
- 1순위 결과: 숭례문 id 7813430 (126.975313, 37.560003, 세종대로 40) · 덕수궁 id 10305191 (126.974895, 37.565564, 세종대로 99)
- `교보빌딩`(b8e23419…d65f.json, T3.1 라우터 출발점): 1순위는 **서초 교보타워**(7996006), 2순위 안양 교보빌딩, **3순위 광화문교보빌딩 id 24020019 (126.977904, 37.570969, 종로 1)**. 리졸버(T4.2)는 서울 범위·관할서 힌트로 골라야 한다 — 1순위 맹신 금지의 실례

### recorded/kakao/local (BE 지오코딩 재생용, T5.8)
- 출처: 카카오 로컬 `https://dapi.kakao.com/v2/local/geo/coord2address.json`(좌표 → 주소)·`.../search/keyword.json`. 수집 `make record API=geocode` → `scripts/record_api.py` `record_geocode`. 요청 모양·파일 이름은 BE `naru_be/models/repositories/kakao_local.py` 의 `coord2address_params`·`keyword_params`·`record_name`(sha1(endpoint?정렬한 params)) — BE `RecordedKakaoLocal` 이 같은 이름으로 재생한다. 형식은 위와 같다(`api, endpoint, params, called_at, status, raw`, 키 없음)
- 2026-11-08 15:19 (live 7): 역지오코딩 4 — 교보빌딩 126.9779040,37.5709686 → 도로명 "서울특별시 종로구 종로 1"(건물 광화문 교보생명 본사사옥) `1e979f8e…` sha256 acb90677c437… · 대한문 126.9765429,37.5650416 → "서울특별시 중구 세종대로 99"(덕수궁) `73e7bcdd…` sha256 24a955ec30b9… · 세종대로 건너기 출발(태우 실서버 요청) 126.9723,37.56368 → "서울특별시 중구 서소문로11길 19" `33bb4ce9…` sha256 bd927a886e9b… · 같은 요청 도착 126.98193,37.56368 → 도로명 없음, 지번 "서울 중구 남대문로2가 9-9" `32cbd381…` sha256 c621f6aff1d4…. 키워드 3(거리순 `sort=distance`, near 126.9775,37.5675) `ccb338ff…`·`c649f46a…`·`52b28b05…` — 건물 안 가게가 앞서서(교보빌딩 1위 "투데이세차 광화문점") **쓰지 않는다**(지워도 됨, 태우 판단)
- 2026-11-08 15:21 (live 3, 이 Task 합계 10): 키워드 반경 5 km 정확도 순(near 126.98,37.57 = FE 지도 기본 중심을 소수 2자리로) — `교보빌딩` 1위 광화문교보빌딩 24020019 `4826147a…` sha256 2749acd4a18b… · `덕수궁` 1위 덕수궁 10305191, 3위 덕수궁 대한문 17582477 `2a50cf58…` sha256 cc32f7f19c03… · `시청` 1위 서울특별시청 8430129 `984e9224…` sha256 5b3ebd591a1d…

### recorded/incident · links (TOPIS 돌발, `scripts/record_api.py`)
- 출처: 서울 열린데이터광장 OA-13312 돌발 유형 코드(`AccMainCode`) · OA-13313 세부유형(`AccSubCode`) · OA-13315 실시간 돌발(`AccInfo`) · OA-13310 링크정보(`LinkInfo`, LINK_ID 필수) · OA-13311 링크 Vertex(`LinkVerInfo`, LINK_ID 필수). 전부 **xml만**. 공공누리 1유형
- 파일: `data/recorded/incident/20261107T154053_{AccMainCode,AccSubCode,AccInfo}.json`, `data/recorded/links/20261107T154055_{LinkInfo,LinkVerInfo}_<link_id>.json` (1010011000 덕수궁길, 1000003700 청계천로, 1000003000 청계천로, 1210020200 서초대로)
- 유형 코드(실제): A01 교통사고 · A02 차량고장 · A03 보행사고 · A04 공사 · A05 낙하물 · A06 버스사고 · A07 지하철사고 · A08 화재 · A09 기상/재난 · **A10 집회및행사** · A11 기타 · A12 제보 · A13 단순정보. 세부 10B02 집회 · 10B03 행사
- AccInfo 필드(실제): `acc_id, occr_date(YYYYMMDD), occr_time(HHMM 또는 HHMMSS), exp_clr_date, exp_clr_time, acc_type, acc_dtype, link_id, grs80tm_x, grs80tm_y, acc_info(통제 문장, \r 줄바꿈), acc_road_code`. 2026-11-07 15:40 기준 53건: 공사 27 · 집회및행사 15 · 기타 6 · 교통사고 4 · 차량고장 1. 집회및행사 예: 1108984 "세종대로 (시청역 → 숭례문) 집회관련 무대설치로 진행방향 전차로 통제" link 1010005900 07:00~16:00
- **좌표계: `grs80tm_x/y`는 EPSG:5181** (중부원점, 북 500,000) — 봉은교 vertex (206174, 446261) → (127.0698, 37.5158). 5186으로 읽으면 위도 36.6으로 튄다
- 링크 ID ↔ 표준노드링크: 4개 중 2개(1000003700 청계천로, 1010011000 덕수궁길)는 nodelink_seoul에 같은 ID가 있고 양 끝 좌표가 10 m 안에서 같다. 2개(1000003000, 1210020200)는 없다 → 좌표는 LinkVerInfo로 받는 게 안전. `make record API=links`는 집회및행사 → 공사 → 기타 순으로 링크를 고른다(`--limit`)
- 2026-11-08 18:04 (live 6, T6.1 — 11/7 AccInfo 의 그래프 범위 안 집회 링크, `uv run python scripts/record_api.py --api links --links 1010005900,1010006000,1000012500`): `links/20261108T180400_{LinkInfo,LinkVerInfo}_<id>.json` — 1010005900 세종대로 시청역→숭례문 401 m 꼭짓점 4 (LinkInfo sha256 57fd3bcd59bb… · LinkVerInfo 2372984ba9c4…), 1010006000 세종대로 숭례문→시청역 401 m 꼭짓점 4 (511f3f043e36… · 08e14e3036c0…), 1000012500 사직로 경복궁역→사직공원 364 m 꼭짓점 6 (7031e7f053e6… · c06c31fc10dc…). 두 세종대로 링크는 방향별이고 약 20 m 떨어져 있다 — 15 m 선 버퍼로 각 4곳(그 방향 차로를 건너는 쪽), 25 m 면 6곳
- 2026-11-08 18:20 (live 1, T6.1 워커 live 경로 확인 — `SeoulOpenApi`, 키 가림 확인): `incident/20261108T182054_AccInfo.json` (sha256 714cd3ecea46…) 10건 — 공사 3 · 행사(10B03) 3 · 기타(11B01) 3 · 교통사고 1, 집회 0 → 후보 0(빈 배치)
- AccInfo `acc_road_code` 는 009(시각이 HHMM, 예 1109106 "세종대로 (숭례문 ↔ 덕수궁) 집회로 양방향 전면통제" 14:44)와 010(시각이 HHMMSS, 경찰 공지를 옮긴 듯한 "15:00∼17:00 서울시의회∼숭례문(편도全차로) ※행진…")이 섞여 있다. 뜻은 확인 못 함 — 둘 다 집회(10B02)면 같은 규칙으로 후보

### recorded/rtd (서울 실시간 도시데이터)
- 출처: 열린데이터광장 `citydata` (json), AREA_NM=광화문·덕수궁(AREA_CD POI009). 파일 `data/recorded/rtd/20261107T154125_citydata.json`
- 필드(실제): `CITYDATA.{AREA_NM, AREA_CD, LIVE_PPLTN_STTS[{AREA_CONGEST_LVL, AREA_CONGEST_MSG, AREA_PPLTN_MIN, AREA_PPLTN_MAX, PPLTN_TIME, FCST_PPLTN[]}], ROAD_TRAFFIC_STTS, PRK_STTS, SUB_STTS, LIVE_SUB_PPLTN, BUS_STN_STTS, LIVE_BUS_PPLTN, ACDNT_CNTRL_STTS, SBIKE_STTS, WEATHER_STTS}`. 2026-11-07 15:10 "약간 붐빔" 48,000~50,000명
- 기록 형식: `api, endpoint(키는 <키>), params, called_at(+09:00), status, raw`. 응답 본문의 키도 `<키>`로 가린다
- 2026-11-09 08:28:44 `data/recorded/rtd/20261109T082844_citydata.json` (186,128 B, sha256 `7388ab7220fb…`, T6.5) — `ACDNT_CNTRL_STTS` 0건(같은 때 OA-13315 AccInfo 08:24 는 서울 9건, 광화문·덕수궁 안 없음). 라이선스 공공누리 1유형(OA-21285 페이지, 아래)

### recorded/topis_web · data_go_kr_web · seoul_opendata_web (T6.5 조사 — 웹 페이지·내부 AJAX 원문)
- 받은 방법: `web_record`(조사 스크립트, 받은 그대로 `api, endpoint, params{method, body}, called_at, status, content_type, raw`, 키는 `<키>`). ADR-011 E — robots.txt 확인(TOPIS 11/8 19:19: `/visit/`·`/map/openTotalMap.do` 만 금지, data.go.kr: Googlebot 규칙뿐, data.seoul.go.kr: 모두 허용), 같은 곳 10분 간격, User-Agent `NaruBot/0.1 (+https://naru.antaewoo.com)`
- `topis_web/20261109T082705_openControlMap.json` (116,464 B, sha256 `6ee2efe548d1…`) — TOPIS 교통통제 지도 페이지. 안의 스크립트가 부르는 AJAX: 목록 `POST /map/accMap/selectAccAllListASC.do {accDate: NOW, trafficdataAppyYn: Y}`, 통제 도로 `POST /map/accMap/selectAccLinkList.do {accId, trafficdataAppyYn: Y}`, 링크 꼭짓점 `POST /map/selectVmsLinkList.do {linkId}`(rows `grs80tmX·grs80tmY`, EPSG:5181). 저작권·이용약관 표기 없음
- `topis_web/20261109T083719_selectAccAllListASC.json` (5,608 B, sha256 `2b0512512a61…`) — 목록 6행: `accId, ingYn(Y 통제 중·N 예정), accType/accTypeNm, accDtype/accDtypeNm, roadNm, roadNms, linkId, linkNm, posX·posY(EPSG:5181), occrDt·clrDt, accRoadYn(전체·부분 통제), accRoadCnt, accInfo …`. 예정 3(덕수궁길 행사, 국회대로 집회 1109233 — 경찰청 11/9 r02 행진 9.5 km, 강남대로 집회 1109234)은 OA-13315 에 없다(08:49 기록까지 — OA-13315 는 시작한 통제만). 통제 중 3(1071788·1071792·1108643 남이장군사당제 — TOPIS 공지 6289)은 OA-13315 와 같은 acc_id(1108643 은 08:30 시작이라 OA-13315 08:34 기록부터)
- `topis_web/20261109T084734_selectAccLinkList_1109233.json` (4,697 B, sha256 `32a9ce8fef6d…`) — 1109233 통제 도로 19행: `accId, linkId, linkSeq, axisCd, axisDirCd(NB·EB·WB·IN), stNodeNm, edNodeNm, roadName, ingYn`. 도로축(axisCd)마다 linkSeq 순으로 이으면 행진 경로 전체 — 국회대로 → 여의서로 → 여의대로(마포대교) → 마포대로 → 신촌로 → 충정로 → 새문안로 → 세종대로(세종대로사거리 → 광화문) → 사직로 → 효자로. 링크 꼭짓점은 OA-13311 LinkVerInfo 와 같은 TOPIS 링크(아직 기록 없음)
- `data_go_kr_web/20261109T082805_openapi_15088841.json` (188,740 B, sha256 `a2fda234f6e9…`) — 경찰청_교통돌발정보서비스: "고속도로 및 국도상의 실시간 돌발 정보", XML, "키 값 및 IP 인증 필요", 제공형태 LINK(경찰청 도시교통정보센터 쪽 키), 이용허락범위 제한 없음, 무료
- `seoul_opendata_web/20261109T082921_OA-21285.json` (115,011 B, sha256 `9bbd6924917c…`) — 서울시 실시간 도시데이터: 공공누리 1유형(출처표시, 상업적 이용·변경 가능), 제공기관 서울특별시, 실시간

### recorded/naru_api (로컬 Flask 응답 — FE 테스트 입력, T3.4)
- 출처: `make record-naru-api` → `scripts/record_naru_api.py`. 실제 앱(create_app, 개발 DB naru)에 `data/recorded/candidates/course/` 최신 배치를 POST 한 뒤 /route·/closures·/closures/events·/geocode/*·오류 응답을 그대로 기록. 기록일 2026-11-08T07:56:52+00:00, 커밋 c0b787d
- 좌표: 카카오 기록 광화문교보빌딩(24020019) → 덕수궁 대한문(17582477), bbox 광화문 `126.965,37.555,126.990,37.580`. 시각 2026-03-15 04:30(통제 전, 출발지 구간 05:00 예정이 scheduled 로)·07:45(1구간 중)·13:30(후)
- 2026-11-08 재기록: INTERFACE v0.7(ADR-009) — `/route` legs 에 `coord_range` 가 실린다. 07:45 지하보도 레그 [3, 8]
- 2026-11-08 재기록(T5.4): INTERFACE v0.8(ADR-010) `/closures/events` 추가. 개발 DB 에 코스 배치 2(course-20261107-194153·course-d153bf070b2c)와 공지 배치 2(notice-3643411ad2db·notice-c28fa67b1900)가 있어 사건 7개 — 2026-11-07 서울경찰청 집회 2(15:00~16:00 횡단보도 31곳, 12:00~16:00 13곳), 2026-03-15 마라톤 구간 5. `/closures`·코스 응답은 해시 그대로, `/route` 셋은 computed_at 만 바뀜
- 2026-11-08 재기록(T5.5, ADR-011 A): 라우터가 예정을 공지 창 안에서만 횡단보도당 +300초로 → `route_0430` 은 원래 길(674 s·808.3 m, 피한 곳 0)로 바뀜, 07:45·13:30 은 값 그대로. 공지 후보 배치(`candidates/notice/20261108T134915.json`, 후보 7)도 넣고 기록 → `candidates_notice.json`. 새 기록: `route_1107_1500.json`(태우 실서버 요청 11/7 15:00 세종대로 37.56368,126.97230 → 37.56368,126.98193 — 935 s·1,122.5 m 시청 지하보도 우회, 예정 1곳, 원래 길 871 s), `error_out_of_coverage.json`(잠실 37.5133,127.0980 → 422 out_of_coverage field from, 8,310 m)
- 2026-11-08 재기록(T5.7, INTERFACE v0.10 · ADR-011 C): `closure_events.json` 에 `coverage` [126.94810841609588, 37.54264971358972, 127.02668353217784, 37.63148349215145](보행망 노드 bbox, 종로·중구 그래프). 사건 7개 그대로, `/route` 넷은 computed_at 만 바뀜(값 그대로 — 04:30 674 s, 07:45 700 s, 11/7 15:00 935 s, 13:30 674 s)
- 2026-11-08 재기록(T5.8, INTERFACE v0.11 · ADR-011 B): 앱을 `geocode_source=recorded`(카카오 기록 `recorded/kakao/local` 재생, live 없음)로 띄워 `/geocode/*` 9개 추가 — 검색(near 37.5675,126.9775 = FE 지도 기본 중심) `geocode_search_kyobo`(1위 광화문교보빌딩)·`_deoksugung`(1위 덕수궁, 3위 덕수궁 대한문)·`_cityhall`(1위 서울특별시청), 주소 `geocode_reverse_kyobo`("종로구 종로 1")·`_daehanmun`("중구 세종대로 99")·`_sejong_from`("중구 서소문로11길 19")·`_sejong_to`(도로명 없음, "중구 남대문로2가 9-9"), 오류 `error_geocode_unavailable`(잠실 — 기록 없음 503)·`error_geocode_query`(한 글자 400 field q). 나머지는 값 그대로, `/route` 넷은 computed_at 만
- 2026-11-08 재기록(T5.9, INTERFACE v0.12 · ADR-012): 개발 DB 에 Alembic 0003(closure_states source·type·summary·notice) 적용, 새 코스 배치(`candidates/course/20261108T162816.json`)·공지 배치(`candidates/notice/20261108T162420.json`, summary 포함)를 넣고 기록 — `closure_events.json` 사건 7개 모두 type·source, 공지 사건 2개는 summary(r04 구간 3·50,000명·태평로 / r01 동화면세점 앞 고리·50,000명·세종대로)·notice, 코스 5개는 summary·notice null. `data_as_of` = smpa 2026-11-06T18:00+09:00 · course 2026-03-12T16:07+09:00 · topis_* null. 경로 값 그대로(computed_at 만). 새 기록 `closures_1107_1500.json`(광화문 bbox, 11/7 15:00 — 공지 집회 두 건 scheduled: r04 피처 38개·서로 다른 횡단보도 31곳, r01 13곳; FE 홈 목록의 공지 행 테스트 입력)
- 2026-11-08 재기록(T5.10): `/route` 횡단보도 레그에 이름 — 04:30·13:30 "세종대로사거리"·"청계광장", 07:45 "청계광장", 11/7 15:00 "덕수궁앞"(OA-23081 교차로명). 경로 값 그대로, 나머지 파일 해시 그대로
- 2026-11-09 새 기록(T6.9 서울 전체, INTERFACE v0.13 보충 `districts`): `closure_events_seoul.json` (16,862 B, sha256 `a994f2222183…`) — 운영과 같은 개발 DB 대신 테스트 DB `naru_test` 에 실제 앱(create_app, 기본 설정 = 서울 25개 구)을 띄우고 워커 발행 경로(IngestWorker.run_once = 코스 최신 배치 + 공지 `notices/sentences.jsonl`·LLM 기록 재생, 그다음 incident_batch = 돌발 `incident/20261107T154053_AccInfo.json`)로 실은 뒤 GET /closures/events 응답 그대로(형식 같음, 코드 8131f51 + districts). 사건 27, 구 8(광진·동대문·서초·성동·송파·영등포·종로·중구), coverage [126.79591…, 37.43053…, 127.18380…, 37.69427…](서울 전체 보행망). FE 통제 불러오기 구 칩·날짜 묶음 테스트 입력. `make record-naru-api` 는 개발 DB 에 POST 해서 통제일엔 돌리지 않았다. `_meta.json` 목록 밖
- 파일 형식: `method, path, query|json, status, body`. 토큰·키 없음. `_meta.json`에 파일 목록
- 파일 24개:
  - `candidates_course.json` sha256 643a38e02351…
  - `candidates_notice.json` sha256 4dd56113f472…
  - `closure_events.json` sha256 5b8916f1b52f…
  - `closures_0430.json` sha256 e53da338f7ca…
  - `closures_0745.json` sha256 7310ccb19e36…
  - `closures_1107_1500.json` sha256 53e5a96c58ae…
  - `closures_1330.json` sha256 abb34d528a87…
  - `error_geocode_query.json` sha256 16c66d5c8747…
  - `error_geocode_unavailable.json` sha256 1e24f4ccbad4…
  - `error_invalid_query.json` sha256 4f8d588a3e9c…
  - `error_not_found.json` sha256 9cdd91c37de0…
  - `error_out_of_coverage.json` sha256 7e11b2369543…
  - `error_unauthorized.json` sha256 54fb76bbef98…
  - `geocode_reverse_daehanmun.json` sha256 3872f010e03c…
  - `geocode_reverse_kyobo.json` sha256 caae35417abe…
  - `geocode_reverse_sejong_from.json` sha256 b19d581c8e69…
  - `geocode_reverse_sejong_to.json` sha256 46ab33c8c232…
  - `geocode_search_cityhall.json` sha256 e0f3b16194da…
  - `geocode_search_deoksugung.json` sha256 e23045b50ed2…
  - `geocode_search_kyobo.json` sha256 92b9e9c4818e…
  - `route_0430.json` sha256 d76791bf7d4d…
  - `route_0745.json` sha256 6923b9092cd7…
  - `route_1107_1500.json` sha256 b1174c5c48b0…
  - `route_1330.json` sha256 d12c7643a447…

### recorded/llm (Claude API 공지 파서 응답 — 재생용, T4.1)
- 출처: `make record-llm NOTICES=<sentences.jsonl> LIMIT=3` → `scripts/record_llm.py`. 모델 `claude-haiku-5-5`, 프롬프트 `notice_v1`(`packages/ai/naru_ai/llm/prompts/notice_v1.md`, 규칙서 v2 §0~§5·§9 + few-shot 8문장). 경로 `data/recorded/llm/anthropic/claude-haiku-5-5@api/notice_v1/<sentence_id>.json`. 기록일 2026-11-07, 호출 3회
- 입력: `sentences.jsonl` 의 경찰청 3행(few-shot 에 없는 것) — smpa-20261107-r06(出 약칭), smpa-20261109-r01(`·` 연속 지점), smpa-20261109-r02(방향어). strict tool `parse_notice`, tool_choice 강제, temperature 없음(Haiku 5.5 는 400)
- 파일 형식: `api, model, prompt_version, sentence_id, called_at, request{system, messages, tool}, response(Message 원문), usage, elapsed_ms`. 키 없음. 시스템 프롬프트 11,072 토큰이 캐시됨(2·3번째 호출 cache_read)
- `notice_v1/` 202개 (2026-11-07~08, 1차): sentences.jsonl 문장 5건(T4.1 3 + T4.4 r01·r04 — v1 few-shot 문장, 워커 e2e 용), 라벨 케이스 K-001~K-034 34건 + 합성 C-* 163건(T4.3 평가, `scripts/record_llm.py --ids all --max-calls`, 합성 봉투는 source news·published_at 2026-11-07T00:00+09:00 고정). 호출 합계 202회, 캐시 제외 입력 ≈ 95k·출력 ≈ 110k 토큰(≈ $0.09)
- `notice_v2/` 39개 (2026-11-08, 태우의 프롬프트 v2·라벨 교체 뒤 재기록): 라벨 K-001~K-034 34건 + 문장 5건(r01·r04·r06·1109-r01·1109-r02). 호출 39회, 캐시 제외 입력 ≈ 15k·출력 ≈ 19k 토큰(≈ $0.01). 합성 163건은 v2 로 미기록
- `notice_v2/` + TOPIS 공지 글 6건 (2026-11-08 19:26 KST, T6.4 — 워커 `topis_batch` live 경로, `max_calls=6`): `topis-6299-u202611061014`·`topis-6293-u202611052048`·`topis-6289-u202611051429`·`topis-6288-u202611051420`·`topis-6275-u202611051124`·`topis-6264-u202610271009` (topis_notice/20261108T192013.json 에서 11/8 19:30 에 볼 글). 호출 6회, 입력 4,129 + 캐시 생성 11,324·읽기 56,620, 출력 3,759 토큰(usage 합). 운영 워커(`--live`)가 새 글·고친 글마다 더한다(한 번 10·하루 `NARU_LLM_DAILY_CAP` 200, 하루 수는 그날 쓴 파일 수)
- `notice_v2/` + TOPIS 공지 글 22건 (2026-11-08 19:54~19:55 KST, T6.4 — 같은 경로, 볼 글을 고르는 기준 시각만 2026-10-26 으로 둬 같은 기록 30행 중 통제안내·버스안내 28건의 나머지 전부, 태우 2026-11-08 "기록은 유료여도 $50까지"): 6301·6300·6298·6297·6295·6294·6287·6286·6283·6281·6279·6277·6269·6268·6267·6266·6265·6263·6262·6261·6260·6258 (`topis-<번호>-u<update_date 분>`). 호출 22회, 실패 0, 입력 14,680 + 캐시 생성 11,324·읽기 237,804, 출력 14,389 토큰(usage 합, Haiku 5.5 단가 $0.10/$0.50 per MTok·캐시 읽기 0.1×·쓰기 1.25× 로 ≈ $0.013, 앞 6건 ≈ $0.004). 재생하면 후보는 6300(세종대로 3)·6281(서초 1)·6267·6262(올림픽공원 점 1씩) — test_topis_feed
- `notice_v2/` + 경찰청 PDF 행 13건 (2026-11-08 20:30 KST, T6.6 — 워커 smpa 경로의 파싱(`_parse_notices`), PDF 3개를 임시 inbox 로 복사, 기준 시각 2026-11-06 20:00): `smpa-20261107-r01~r06·20261108-r01~r03·20261109-r01~r04` 에 `-u202611061800`(기준 작성). 옛 ID(버전 없음) 5건과 따로 있다. 호출 13회, 실패 0, 입력 4,876 + 캐시 생성 11,324·읽기 135,888, 출력 6,192 토큰(≈ $0.006). 재생하면 후보 10 — test_smpa_inbox·e2e

### recorded/candidates/notice (공지 → ClosureCandidate, T4.2)
- 출처: `make record-candidates SOURCE=notice` → `scripts/record_candidates.py`. 기록된 LLM 응답 3건(recorded/llm) 재생 → 정렬기 → 리졸버(OA-23081 교차로명 + 카카오 기록 재생) → CandidateBuilder. live 호출 없음. 파일 `data/recorded/candidates/notice/20261107T211233.json` sha256 2a3d3a74b3ab…, 후보 3개
- 2026-11-08 재기록(T5.5): 지금 기록된 LLM 응답 전부로 → `20261108T134915.json` sha256 14e7545c96d9…, 후보 7개(11/7 r01 12:00~16:00 확신도 0.85, r04 15:00~16:00 0.75 ×3, r06 16:00~19:00, 11/9 r01·r02). BE 회귀 테스트(`test_route_regressions.py`)·`record_naru_api.py` 입력
- 2026-11-08 재기록(T5.9, INTERFACE v0.12 · ADR-012): 같은 LLM 응답으로 → `20261108T162420.json` sha256 7f1dc92f613a…, 후보 7개 그대로 + 후보마다 `summary`(구간 from_/to/via·지점 이름·reported_people·roads — r04 구간 3·50,000·태평로, r01 고리·50,000·세종대로, r06 5,000·은행로, 11/9 r01 200·여의도, r02 400·여의도). live 호출 없음
- 내용: segment 2(의사당역 5번출구→민주당사, 하나증권 앞→금감원→여의도역), point 1(국회의사당역 2번출구 — '사랑채 동측 건너편'은 여의도 힌트로 못 풀어 출발지만). 좌표는 전부 카카오 기록 documents 또는 교차로 평균점
- 카카오 기록 추가 12건(`scripts/record_api.py --api kakao --queries ...`): 2026-11-07 의사당역 5번출구·의사당역·민주당사·하나증권·금감원·여의도역·국회의사당역 2번출구·국회의사당역·사랑채, 2026-11-08 동화면세점·서울시의회·고용노동청(T4.4 워커 e2e 용)

### notices/cases_v1 (공지 파서 라벨 — 정확도 평가, T0.6·T4.3)
- 출처: 실제 공지(서울경찰청 「오늘의 주요집회」 smpa 22 · TOPIS 돌발 6 · TOPIS 공지 1 · 보도 3 · 서울시 보도자료 2)에서 뽑은 34건. 라벨(`expected.items`, 규칙서 v2 §9.1 스키마)은 태우가 직접 달았다(Syntitan 케이스 초안 검토 후 확정). 2026-11-07 수령, **2026-11-08 교체**(T4.3 1차 결과 반영: 지점 집회 unknown, K-016 item 1, 잠수교 car_free, K-027 라벨 정정, construction 추가)
- 파일: `data/raw/notices/cases_v1.jsonl` (34행, sha256 aacc1127c7b65fc50ed7e2e03d6839493ba4dc942898f3660b58cc25b8ca61d2). 열: case_id, notice_id, source, text, event_date, published_at, source_url, type(정상 16 / 놓치기쉬움 6 / none 6 / unknown 5 / 거절 1), expected, notes, check
- 용도: `scripts/eval_notice.py` 정확도(impact·kind·segments·window 일치율). git 에 올리지 않는다(raw 규칙)

### recorded/syntitan (합성 입력 — 견고성용, T4.3)
- 출처: 큐빅 Syntitan 이 규칙서·원문으로 생성한 에이전트 질문 163건. **합성이라 정답이 없다. 견고성(스키마 통과율·impact 분포)에만 쓰고 정확도 계산에 안 쓴다.** 2026-11-07 수령
- 파일: `data/recorded/syntitan/agent_questions.csv` (163행, sha256 4dc595848570eb157c72f10bcce030984943358a06dd10c28435f9f76e057803). 열: case_id, input(상황/요청 여러 줄)

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
