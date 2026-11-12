# 간접 신호 기록 — T7.19 (멘토링 T-E), 2026-11-11

통제 중에 주변 교통이 실제로 어떻게 변하는지를 **기록만** 쌓는다. 경로·확신도·상태 어디에도 쓰지 않는다(ADR-002 — 밀집도에 의존하지 않는다, ADR-013 — 버스와 같은 기록만). 나중에 공지 ↔ 실제 통제 라벨(T7.18 §3)의 보조 근거로 쓴다.

## 1. 원천 하나로 둘 다 — 서울 실시간 도시데이터(OA-21285 `citydata`)
한 장소(주요 121장소) 응답 안에 두 가지가 같이 온다.
- **도로 링크 속도** `ROAD_TRAFFIC_STTS.ROAD_TRAFFIC_STTS[]`: `LINK_ID, ROAD_NM, START_ND_CD/XY, END_ND_CD/XY, DIST, SPD(km/h), IDX(원활·서행·정체)` + `AVG_ROAD_DATA{ROAD_TRAFFIC_IDX, ROAD_TRAFFIC_SPD, ROAD_TRAFFIC_TIME}`. 광화문·덕수궁은 159 링크.
- **장소 혼잡도** `LIVE_PPLTN_STTS[0]`: `AREA_CONGEST_LVL(여유·보통·약간 붐빔·붐빔), AREA_PPLTN_MIN/MAX, PPLTN_TIME`.
별도의 "서울 실시간 도로 소통 정보"(OA-13291)는 열린데이터광장에 **서비스 종료**로 표시돼 있어(검색 결과) 쓰지 않는다.

## 2. 링크 ID ↔ 표준노드링크 1회 대조 (`scripts/check_citydata_links.py`, 요청 없음)
입력: `recorded/rtd/20261107T154129_citydata.json`·`20261109T082844_citydata.json`(광화문·덕수궁, 링크 159개 합집합) vs `raw/nodelink_seoul_20261014/link.gpkg`(63,383 링크).

| 항목 | 결과 |
|---|---|
| 같은 `LINK_ID` 가 표준노드링크에 있다 | **159 / 159 (100%)** |
| 양 끝 좌표(`START_ND_XY`·`END_ND_XY`)가 그 링크 선의 양 끝과 10 m 안 | **159 / 159** — 전부 "반대 방향"(citydata 의 START→END 가 gpkg 선의 저장 순서와 거꾸로. 좌표는 같다) |
| 시작·끝 **노드 코드**(`START_ND_CD`·`END_ND_CD`)가 gpkg `F_NODE`·`T_NODE` 와 같다 | 0 / 159 — 노드 코드는 다른 체계. 링크는 ID 로, 방향은 좌표로 본다 |

→ "맞으면 기록"의 조건을 만족한다. 링크 속도는 LINK_ID 로 우리 도로 그래프(nodelink_seoul)에 바로 붙는다. 방향(상·하행)을 쓸 때는 노드 코드가 아니라 좌표로 맞춘다.

## 3. 무엇을, 언제, 얼마나 기록하나 (`naru_ai.signal.citydata`, 워커 소스 `signals`)
- **장소 고르기**: 주요 121장소 영역(`raw/citydata_areas_20261111`, shp EPSG:4326)에서 활성 통제 사건의 중심(`/closures/events` `centroid`)으로부터 **1 km 안**, 사건마다 가까운 **2곳**(영역 안이면 거리 0, 같으면 코드순). 겹치면 한 번. 예: 교보빌딩 → POI009 광화문·덕수궁·POI088 광화문광장, 논현역 → POI037 신논현역·논현역·POI059 가로수길, 국회의사당 → POI072 여의도·POI126 여의서로.
- **활성 통제**: 사건 창 시작 1시간 전 ~ 끝 30분 뒤(버스 ADR-013 G 와 같은 창). 종류·출처 가리지 않는다(공지·통제지도·돌발 전부, 중심이 있는 사건).
- **주기·상한**: 5분(`NARU_SIGNALS_INTERVAL_S` 300), 하루 **200회**(`NARU_SIGNALS_DAILY_CAP` — 열린데이터광장 키를 돌발 5분(288)·TOPIS 공지 10분(144)과 나눠 쓴다, 키 한도 1,000/일). 장소 2곳 × 12회/시간 = 하루 8시간 통제 두 건이면 ≈ 200.
- **기록**: `recorded/rtd/signals/<ts>_citydata_<AREA_CD>.json` — 원문 그대로(`api rtd, params{AREA_NM}, called_at, status, raw`), 키는 `<키>`. recorded 모드(테스트)는 그 장소의 가장 최근 기록을 재생하고, 없으면 건너뛴다(지어내지 않는다).
- **켜기**: 운영 워커 unit 에 `Environment=NARU_SIGNALS_SOURCE=live`(기본 recorded = 호출 없음). 키는 `.env` `SEOUL_OPENDATA_KEY`.
- **경로 확인(11/11 23:27, live 1회)**: 광화문·덕수궁 → `recorded/rtd/signals/20261111T232719_citydata_POI009.json`(141 KB) — 혼잡도 여유 8,000~8,500(22:55 기준), 도로 서행 23 km/h(23:25), 링크 159. 통제가 없는 밤이라 워커 대상은 0곳이고, 이 한 건은 API 클래스로 직접 부른 것.
- **안 하는 것**: S-DoT 센서(ARCHITECTURE 표에 있던 "센서 10분")는 이번에 안 넣었다 — 장소 혼잡도가 같은 응답에 있어서. BE 전송·표·API 없음(INTERFACE 변경 없음).

## 4. 11/14 뒤 할 일
- `signals/` 기록과 그 시각 통제(공지 창·돌발·현장 제보 T7.15)를 겹쳐 — 통제 중 링크 `SPD`·`IDX` 가 평소(같은 요일·시각)와 얼마나 다른지, 혼잡도 단계가 통제와 같이 움직이는지 센다. 결과가 뚜렷하면 ADR 로 confidence 승격 논의(ADR-002 결과 "같은 슬롯에 꽂는다").
