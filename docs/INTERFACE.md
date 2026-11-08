# INTERFACE.md — 파트 간 계약 v0.13

파트 경계의 단일 기준. 스키마를 바꾸면 **이 파일 먼저** 고치고, 하위호환이 깨지면 버전을 올린다. 변경은 ADR + 태우 승인.
코드 구현은 `packages/contracts`(`naru_contracts`, pydantic v2) 하나뿐이다. 테스트가 이 문서의 예시 JSON 블록을 그대로 파싱하므로, 예시를 고치면 코드도 고쳐야 한다. FE 타입은 `make schema`로 생성한다.

**표기 규칙**: enum 코드값은 영어 snake_case(한국어 라벨은 FE `i18n/ko.ts`). 시간은 ISO 8601 + 오프셋 필수, 서버 응답은 `+09:00`. 좌표는 `[lng, lat]`.

## §1 AI → BE: `ClosureCandidate` (v0.6)

AI 워커가 내놓는 유일한 출력. BE의 `CandidateIntake`(Model)가 `CrosswalkIndex`로 `geometry`를 `crosswalk_ids[]`로 바꾼 뒤 `ClosureEngine`에 넘긴다.
**모델(Claude)은 좌표를 만들지 않는다.** AI는 공지에서 표현(spans)과 구간(segments)을 뽑고, 리졸버가 정규형 → 좌표(`PlacePoint`)를 채운다. 선은 BE가 도로 그래프로 만든다.

```json
{
  "candidate_id": "smpa-20261107-row12-seg1",
  "source": "smpa",
  "type": "march",
  "status_hint": "scheduled",
  "impact": "blocks",
  "geometry": {
    "kind": "segment",
    "from_": {"canonical": "KB금융지주", "lng": 126.9256, "lat": 37.5215, "gazetteer_source": "kakao", "gazetteer_id": "8123456"},
    "to": {"canonical": "KB증권", "lng": 126.9271, "lat": 37.5206, "gazetteer_source": "kakao", "gazetteer_id": "8123457"},
    "via": [{"canonical": "여의도역", "lng": 126.9244, "lat": 37.5216, "gazetteer_source": "seoul_station", "gazetteer_id": "0527"}],
    "road": null,
    "road_class": null
  },
  "window": {"start": "2026-11-07T19:00:00+09:00", "end": "2026-11-07T19:30:00+09:00"},
  "confidence": 0.72,
  "evidence": [
    {"kind": "notice", "ref": "data/raw/notices/smpa/20261107.pdf#row12", "at": "2026-11-06T18:00:00+09:00", "detail": null}
  ],
  "notice_ref": {"notice_id": "smpa-20261107-row12", "sentence_id": "s_000412", "source_url": "https://www.smpa.go.kr/...", "published_at": "2026-11-06T18:00:00+09:00",
                 "excerpt": "※행진: KB금융지주→여의도역 5번出→KB증권 본사(19:00出, 0.5km, 2개차로)"},
  "toward": null,
  "approx": false,
  "review_required": false,
  "summary": {"segments": [{"from_": "KB금융지주", "to": "KB증권", "via": ["여의도역"]}], "points": [], "reported_people": null, "roads": []}
}
```
`geometry.kind`별 필드 (kind에 맞는 것만, 나머지는 없음):

| kind | 필드 | 누가 만드나 | BE 처리 (`CrosswalkIndex`) |
|---|---|---|---|
| `point` | `coordinates: [lng, lat]` | 리졸버 (교차로·장소·주소) | `from_point` 반경 30m. `impact: unknown`이면 먼저 도로 30 m 규칙(ADR-008) — 승격 안 되면 `zone_scheduled` |
| `line` | `coordinates: [[lng, lat], …]` | 코스 GPX, 돌발 링크 | `from_line` 버퍼 15m (코스·돌발 — TOPIS 링크는 방향별이라 그 방향 차로를 건너는 쪽 횡단보도) |
| `segment` | `from_`, `to`, `via[]`: `PlacePoint` · `road`, `road_class` | 리졸버 (Claude segments 출력) | `from_segment`: 도로 그래프 최단경로(from→via→to, road 있으면 그 도로만) → LineString → 등급별 버퍼(대로 25 / 로 15 / 길 8 m) → `from_line` |
| `zone` | `zone_name`, `polygon` | ZoneMatcher | 라우팅 무관, `zone_scheduled` 표시만 |

- `from_`·`to` 중 하나라도 리졸버가 못 풀면 `segment`를 만들지 않고 풀린 쪽만 `point`로 보낸다. 틀린 선보다 빠진 점이 낫다.
- `confidence < 0.7` → `review_required: true`. BE는 적재하되 라우팅에 쓰지 않는다.
- `impact ∈ {blocks, unknown}` **필수** (ADR-008, 파서 규칙서 §9). 파서의 `none`(자동차전용도로·차 없는 거리·보도·차량 조치·해제·안내)은 AI가 후보를 만들지 않는다. `unknown`(점유 표현 없는 지점 집회)이면 `confidence ≤ 0.65`여야 하고(→ review_required), BE `CandidateIntake`가 지점이 도로 링크 30 m 안이거나 지점들이 도로를 감싸면 `blocks`로 승격(evidence `detail.rule: unknown_near_road`), 아니면 `zone_scheduled`로 표시만. 코스·돌발은 항상 `blocks`. 버스는 후보를 만들지 않는다(§1.2, ADR-013).
- `toward`: 종료 지점 없는 행진의 방향 표현을 **문장 그대로**(예: `"을지로입구역"`). `geometry.kind ∈ {point, segment}`일 때만. 리졸버가 풀면 AI가 `segment`(출발지 → toward)를 만들고 `confidence`를 0.65로 상한(검토 큐), 못 풀면 `point`만 보낸다.
- `approx`: 파서가 근사 시간("14시경", "오후")을 양끝 10분씩 넓혔으면 `true`. BE는 window를 넓히지도 좁히지도 않고 상태·응답에 그대로 싣는다. 평가는 ±10분 허용.
- `window.end`가 null이면 "종료 미정". 엔진은 시작+6시간을 임시 end로 두고 evidence에 남긴다.
- `evidence[].kind ∈ {notice, timetable, topis_incident, bus_skip, bus_return, rtd_spike}`. `ref`는 데이터·recorded 파일 경로.
- 돌발(producer `incident`, T6.1): OA-13315 실시간 돌발 중 **집회(10B02)만** — 행사(차 없는 거리·축제)·공사·기타(버스 무정차)·사고와 "(인도)" 보도 집회는 후보가 아니다(README impact). `geometry` = TOPIS 링크 선(OA-13311 LinkVerInfo, 없으면 돌발 좌표 `point`), `type` rally, `confidence` 0.9, `status_hint` scheduled, `summary` = 링크 시작·끝 노드 이름과 도로명(OA-13310 LinkInfo). 같은 링크·같은 시각의 돌발은 한 후보(근거는 돌발마다, 후보 ID = 가장 작은 acc_id). `evidence` = `topis_incident`(`at` = 수신 시각, `ref` = 원문 기록 파일`#acc_id`, `detail.acc_id`·`link_id`). BE 는 같은 횡단보도·겹치는 시각의 공지 후보(smpa·topis·news·seoul_press) 전체에도 그 근거를 붙인다(어느 쪽이 먼저 와도) — 공지 확신도가 0.8 이상이면 시작 뒤 `confirmed`. 범위 안 돌발이 없어도 빈 배치를 보낸다.
- `notice_ref`는 공지에서 온 후보에만. `excerpt`는 FE 사건 상세의 "공지 원문 보기"에서만 보인다(v0.12, ADR-012 — 목록·통제 근거에는 출처를 쓰지 않는다).
- `summary` (v0.12, ADR-012, 선택) — 공지 item 의 **구조화 칸만**(문장 없음): `segments[]`{`from_`, `to`, `via[]`}·`points[]` 이름은 파서 spans 의 정규 이름(canonical) 그대로(좌표가 안 풀린 이름도 남는다), `reported_people` 숫자 또는 null, `roads[]` = road_hints·구간 road 의 정규 이름. 같은 item 의 후보는 같은 summary. 코스(시각표) 후보는 null. 화면 문장("…집회 → …행진", "5만 명")은 FE `i18n/ko.ts` 가 만든다.

### §1.1 전송: `POST /internal/candidates` (AI 워커 → BE)
AI와 BE는 서로 import하지 않는다. 후보는 이 엔드포인트로만 넘어간다.

**요청** 헤더 `X-Naru-Internal-Token: <Settings.internal_token>`, `Content-Type: application/json`
```json
{
  "batch_id": "worker-20270321-080015-bus",
  "produced_at": "2027-03-21T08:00:15+09:00",
  "producer": "course | incident | notice | congestion",
  "candidates": [ { "...": "§1 ClosureCandidate" } ]
}
```
**응답** `202 Accepted`
```json
{"batch_id": "worker-20270321-080015-bus", "accepted": 3, "review_required": 1, "crosswalks_updated": 12}
```
- 토큰이 없거나 다르면 `401` + §6 `unauthorized`. 스키마 위반이면 `400` + `invalid_query`.
- 같은 `batch_id`를 다시 보내면 중복 적용하지 않는다(멱등). 재시도 안전.
- 브라우저에서 부르지 않는다. Next.js rewrites 대상에서 `/internal/*`는 제외한다.

### §1.2 전송: `POST /internal/bus-positions` (AI 워커 → BE, v0.13 ADR-013 D)
버스는 후보(통제)를 만들지 않는다. 워커가 받은 위치를 판단 없이 그대로 보내고, BE 는 저장만 한다(T6.2). 확신도 보정은 T6.3. 어느 노선을 부르나(ADR-013 G·I):
- 1순위 공지 통제 — 통제 창(시작 1시간 전 ~ 끝+30분)에 그 통제 횡단보도 100 m 안 정류소가 많은 노선, 사건마다 최대 3개, 60초마다. 원문 `data/recorded/bus/notice/`.
- 2순위 TOPIS 집회·행사 돌발(기준 데이터, 보정에는 안 씀) — 지금 걸린 돌발마다 링크 선 100 m 안 노선 1개, 120초마다, 하루 300회(공지가 쓰고 남은 만큼, 돌발 하나 30회까지). 원문 `data/recorded/bus/incident/`.
- 둘 다 심야(N)·새벽 노선 제외, 전체 하루 900회 상한. 같은 배치 형식 — 어느 쪽인지는 `ref` 의 폴더로 안다.

**요청** 헤더는 §1.1 과 같다. 예시는 2026-11-08 18:38 실제 기록(노선 01A 의 첫 차량).
```json
{
  "batch_id": "bus-100100001-67062dc1ad5c",
  "produced_at": "2026-11-08T18:38:33+09:00",
  "route_id": "100100001",
  "ref": "data/recorded/bus/20261108T183832_getBusPosByRtid_100100001.json",
  "called_at": "2026-11-08T18:38:32+09:00",
  "positions": [
    {"veh_id": "106024536", "plain_no": "서울74사6145", "data_tm": "2026-11-08T18:38:19+09:00",
     "lng": 126.998005, "lat": 37.562053, "sect_ord": 3, "section_id": "101600172", "sect_dist": 0.327,
     "stop_flag": false, "last_stn_id": "101000054", "next_st_id": "101000117", "is_run": true}
  ]
}
```
**응답** `202 Accepted`
```json
{"batch_id": "bus-100100001-67062dc1ad5c", "accepted": 1}
```
- 필드는 getBusPosByRtid `itemList` 그대로 — `vehId`→`veh_id`, `plainNo`→`plain_no`, `dataTm`(YYYYMMDDHHmmss KST)→`data_tm`, `gpsX`·`gpsY`→`lng`·`lat`, `sectOrd`, `sectionId`, `sectDist`(응답 값 그대로), `stopFlag`(1 = 정류소 도착), `lastStnId`, `nextStId`(마을버스는 "0"), `isrunyn`. `batch_id` = `bus-<노선>-<원문 sha1 앞 12자리>`.
- 같은 (노선, 차량, `data_tm`)은 한 번만 저장한다(멱등). `accepted` = 새로 저장한 위치 수.
- 토큰·스키마 오류는 §1.1 과 같다(`401`·`400`).

## §2 BE → FE: `GET /route` (v0.7)

**요청** `from=lat,lng` · `to=lat,lng` · `depart_at=ISO8601` · `mode=walk`  (FE는 같은 오리진 `/api/route`로 호출 → Next.js rewrites → Flask `/route`)

**응답**
```json
{
  "route": {"type": "LineString", "coordinates": [[126.9751, 37.5658], [126.9760, 37.5690], [126.9764, 37.5700], [126.9769, 37.5725]]},
  "duration_s": 840,
  "distance_m": 1120,
  "legs": [
    {"kind": "sidewalk", "name": null, "distance_m": 450, "coord_range": [0, 1]},
    {"kind": "underpass", "name": "시청역 지하보도", "distance_m": 120, "coord_range": [1, 2]},
    {"kind": "sidewalk", "name": null, "distance_m": 550, "coord_range": [2, 3]}
  ],
  "avoided": [
    {"crosswalk_id": "<관리번호>", "status": "confirmed", "reason": "세종대로 전면통제", "until": "2027-03-21T11:15:00+09:00", "approx": false,
     "evidence": [{"kind": "bus_skip", "ref": "data/recorded/seoul_bus_pos/20270321-080015.json", "at": "2027-03-21T08:00:15+09:00"}]}
  ],
  "baseline": {
    "route": {"type": "LineString", "coordinates": []},
    "duration_s": 600,
    "distance_m": 780
  },
  "computed_at": "2027-03-21T08:02:11+09:00"
}
```
- `baseline`은 같은 그래프에서 closures를 끈 경로. FE "통제 전후 비교"에 쓴다. 외부 API 아님.
- `legs[].kind`로 FE가 아이콘·안내 문구를 고른다.
- `legs[].name`: 지하보도·육교는 시설 이름, 횡단보도는 교차로명(OA-23081 `교차로명` — 위치명 열은 없다), 관리번호가 없는 횡단보도는 20 m 안의 가까운 도로명(표준노드링크 `ROAD_NAME`), 그래도 없으면 null. 이어진 같은 종류 간선은 한 레그 — 이름은 처음 나온 교차로명이 도로명보다 먼저 (T5.10, 스키마는 그대로).
- `legs[].coord_range: [i, j]` **필수** (v0.7, ADR-009) — `route.coordinates[i..j]`(양끝 포함)가 그 레그의 선. 레그는 경로를 빈틈없이 나눈다: 첫 레그 `i = 0`, 마지막 레그 `j = len(coordinates) − 1`, 이웃 레그는 경계 점을 공유(`legs[k].j == legs[k+1].i`), `i ≤ j`. 출발점·도착점 ↔ 그래프 노드 접근 구간은 `sidewalk` 레그에 들어가서 `Σ legs[].distance_m = distance_m`(1 m 안). FE는 `underpass`·`overpass` 레그 범위를 남색 터널로, 그 `coordinates[i]`에 입구 마커를 그린다.
- `avoided[].evidence`는 §1의 evidence를 그대로 전달. `avoided[].approx`는 후보의 `approx` 그대로 (FE "약" 표시).

## §3 BE → FE: `GET /closures` (v0.6)

**요청** `bbox=minLng,minLat,maxLng,maxLat` · `at=ISO8601`
- `at`에 진행 중인 통제 + `at`부터 60분(`route_horizon_min`) 안에 시작하는 통제. status는 `at` 기준으로 다시 판정한다(`/route`와 같은 지평이라 지도와 경로가 어긋나지 않는다). 2026-11-07 태우 결정

**응답** GeoJSON FeatureCollection. Feature 하나 = 횡단보도 하나(Point) 또는 예정-구역 하나(Polygon).
```json
{
  "type": "FeatureCollection",
  "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [126.9769, 37.5725]},
     "properties": {"crosswalk_id": "<관리번호>", "status": "confirmed", "confidence": 0.85, "impact": "blocks", "approx": false,
                    "window": {"start": "...", "end": "..."}, "reason": "...", "evidence": [ ... ]}},
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[ ... ]]},
     "properties": {"zone_name": "광화문·덕수궁", "status": "zone_scheduled", "confidence": 0.4,
                    "window": {"start": "...", "end": "..."}, "reason": "집회 예정 (공지 분류)"}}
  ]
}
```

### §3.1 BE → FE: `GET /closures/events` (v0.8 ADR-010, v0.12 ADR-012)

**요청** `bbox=minLng,minLat,maxLng,maxLat` (선택 — 없으면 전체)

**응답** DB 에 있는 통제를 사건으로 묶은 목록. 사건 = 같은 `(reason, window.start, window.end)` 의 횡단보도 상태들
```json
{
  "events": [
    {"reason": "15:00~16:00 시의회~숭례문R → 광화문·고용노동청 <태평로 등> 50,000명 중부, 종로, 남대문",
     "window": {"start": "2026-11-07T15:00:00+09:00", "end": "2026-11-07T16:00:00+09:00"},
     "crosswalks": 31, "bbox": [126.9757, 37.5605, 126.9877, 37.5759], "approx": false,
     "type": "march", "source": "smpa",
     "summary": {"segments": [{"from_": "시의회", "to": "숭례문오거리", "via": []},
                              {"from_": "숭례문오거리", "to": "광화문", "via": []},
                              {"from_": "숭례문오거리", "to": "고용노동청", "via": []}],
                 "points": [], "reported_people": 50000, "roads": ["태평로"]},
     "notice": {"notice_id": "smpa-20261107", "sentence_id": "smpa-20261107-r04",
                "source_url": "https://www.smpa.go.kr/user/nd54515.do", "published_at": "2026-11-06T18:00:00+09:00",
                "excerpt": "15:00~16:00 시의회~숭례문R → 광화문·고용노동청 <태평로 등> 50,000명 중부, 종로, 남대문"}},
    {"reason": "marathon 1구간 세종대로 사거리~숭례문 오거리",
     "window": {"start": "2026-03-15T07:20:00+09:00", "end": "2026-03-15T08:08:00+09:00"},
     "crosswalks": 6, "bbox": [126.9757, 37.5608, 126.9772, 37.5701], "approx": false,
     "type": "marathon", "source": "course", "summary": null, "notice": null}
  ],
  "coverage": [126.948108, 37.54265, 127.026684, 37.631483],
  "data_as_of": {"topis_incident": null, "topis_notice": null,
                 "smpa": "2026-11-06T18:00:00+09:00", "course": "2026-03-12T16:07:00+09:00"}
}
```
- 순서: `window.start` 가 늦은 것 먼저, start 가 없으면 끝.
- `crosswalks` = 서로 다른 횡단보도 수(1 이상). 같은 공지 문장이 구간 여러 개로 나뉘어도 한 사건이다. `bbox` = 그 횡단보도들의 [minLng, minLat, maxLng, maxLat]. `approx` = 하나라도 근사면 true.
- 상태(status)는 없다 — 시각마다 다르다. 그 시각의 상태는 §3 `/closures?at=`.
- FE "통제 불러오기": 누르면 t = `window.start`, 지도 = `bbox`. start 가 없는 사건은 누를 수 없다.
- `coverage` (v0.10, ADR-011 C) **필수** — 보행망(그래프) 노드의 [minLng, minLat, maxLng, maxLat]. FE 는 내 위치가 이 밖이면 길찾기 범위 밖이라고 안내한다(사각형이라 안쪽이어도 보행망에서 150 m 넘으면 `/route` 가 `out_of_coverage`).
- `type`·`source` (v0.12, ADR-012) — 사건을 만든 후보의 종류·출처(§4 enum). v0.12 전에 저장된 상태라 모르면 null. `summary` — 후보의 summary(§1) 그대로, 없으면 null(코스 등). `notice` — 후보의 `notice_ref`(§1) 그대로, 공지가 아니면 null. FE 는 summary 로 제목·둘째 줄을 만들고(없으면 `reason`), `notice.excerpt` 는 상세의 "공지 원문 보기"에서만 보인다.
- `data_as_of` (v0.12, ADR-011 C·ADR-012) **필수** — 출처마다 그 출처로 저장된 통제의 가장 늦은 근거 시각, 없으면 null: 공지(`smpa`, `topis_notice` = source `topis`)는 공지 게시 시각, `course` 는 시각표 게시 시각(상태 전이 근거는 뺀다), `topis_incident`(= source `incident`)는 돌발 배치를 마지막으로 받은 시각(범위 안 돌발이 없는 빈 배치·같은 배치 재전송 포함, T6.1). 예시는 2026-11-08 개발 DB(서울경찰청 11/6 18:00 공지 · 서울마라톤 3/12 16:07 시각표). FE 는 목록 위에 기준 시각을 쓰고, 실시간 출처(`topis_incident`)가 없거나 30분보다 오래면 회색 경고.

## §4 enum
| 필드 | 코드값 | FE 라벨 |
|---|---|---|
| `status` / `status_hint` | `scheduled` · `confirmed` · `released` · `zone_scheduled` | 예정 · 확인 · 해제 · 예정 구역 |
| `impact` | `blocks` · `unknown` | 통제 · 미확인 (ADR-008) |
| `source` | `course` · `smpa` · `topis` · `news` · `seoul_press` · `incident` · `bus` · `rtd` | 코스 · 경찰청 공지 · TOPIS · 보도 · 보도자료 · 돌발 · 버스 · 혼잡 |
| `type` | `marathon` · `march` · `rally` · `event` · `incident` | 마라톤 · 행진 · 집회 · 행사 · 돌발 |
| `geometry.kind` | `point` · `line` · `segment` · `zone` | — |
| `geometry.road_class` | `대로` · `로` · `길` | (도로명 접미사, 버퍼 폭 결정) |
| `evidence[].kind` | `notice` · `timetable` · `topis_incident` · `bus_skip` · `bus_return` · `rtd_spike` | 공지 · 시각표 · 돌발 · 버스 우회 · 버스 복귀 · 혼잡 급등 |
| `legs[].kind` | `sidewalk` · `crosswalk` · `underpass` · `overpass` · `stairs` · `elevator` · `station` | 보도 · 횡단보도 · 지하보도 · 육교 · 계단 · 엘리베이터 · 역 통과 |

## §5 상태별 라우팅 반응 (엔진·라우터·FE 공통 규칙)
ARCHITECTURE.md "ClosureState 상태기계" 표가 기준. 임계값(0.7, 0.8, 예정 +300초, 30분, 붙임 150 m)은 `naru_be/config.py` 상수. 바꾸면 이 문서와 ARCHITECTURE 표도 같이.
- (v0.9, ADR-011 A) `scheduled`(확신도 ≥ 0.7)는 횡단보도에 닿는 시각이 공지 창 안일 때만 그 횡단보도마다 +300초(`scheduled_penalty_s`) — 하드 차단이 아니라 페널티. 창 밖(시작 전·끝난 뒤)은 보통. `confirmed`는 차단. FE 는 `avoided[].status` 로 confirmed "통제 중" / scheduled "공지상 통제 시간 · 현장 확인 전"을 나눈다.

## §6 오류 응답 (Flask)
```json
{"error": {"code": "invalid_query", "message": "depart_at: 오프셋 없는 시각", "field": "depart_at"}}
```
- `code ∈ {invalid_query, unauthorized, not_found, no_route, out_of_coverage, geocode_unavailable, internal}`. HTTP 400 / 401 / 404 / 422(`no_route`·`out_of_coverage`) / 503(`geocode_unavailable`) / 500. Flask `error_view`(View 계층)가 만든다.
- `out_of_coverage` (v0.9, ADR-011): 출발·도착을 보행망 노드에 붙일 거리가 150 m(`max_snap_m`)를 넘는다. `field` = `from` 또는 `to`.
- `geocode_unavailable` (v0.11, ADR-011 B): 카카오 로컬을 못 불렀다 — 서버 키 없음·카카오 오류·시간 초과(재생 모드면 기록 없음). FE 는 검색이면 "검색을 못 했어요", 주소면 "선택한 위치".

## §7 BE → FE: 지오코딩 (v0.11, ADR-011 B)
BE 가 카카오 로컬 API 를 대신 부른다. 키는 서버 `.env` 의 `KAKAO_REST_KEY` 에만 — 브라우저·응답·로그에 없다. FE 는 `/api/geocode/*` 로만 부른다.

### §7.1 `GET /geocode/search?q=&near=lat,lng`
- `q`: 앞뒤 공백을 뺀 2~50자. `near`(선택) `"lat,lng"` — 있으면 그 점 반경 5 km 안에서 정확도 순(BE 가 near 를 소수 2자리, 약 1 km 로 맞춘다), 없으면 전국 정확도 순. 최대 10개, 없으면 `"places": []`
```json
{
  "places": [
    {"id": "24020019", "name": "광화문교보빌딩", "address": "서울 종로구 종로 1",
     "coord": [126.9779039768265, 37.5709686446227]},
    {"id": "492201422", "name": "교보재단빌딩", "address": "서울 종로구 경희궁1길 1",
     "coord": [126.971610332329, 37.5707060102746]}
  ]
}
```
- 2026-11-08 기록(`q=교보빌딩&near=37.5675,126.9775`)의 앞 두 개. `id` = 카카오 장소 id, `address` = 도로명 주소(없으면 지번, 카카오 표기 그대로), `coord` = [lng, lat]

### §7.2 `GET /geocode/reverse?lat=&lng=`
```json
{"label": "종로구 종로 1", "road_address": "서울특별시 종로구 종로 1", "address": "서울 종로구 종로1가 1"}
```
- 2026-11-08 기록(광화문교보빌딩 점 37.5709686, 126.9779040). `label` = 화면용 짧은 주소 — 도로명 주소에서 시·도를 뺀 것, 도로명이 없으면 지번에서(예: "중구 남대문로2가 9-9"). 주소가 없는 점이면 셋 다 null 이고 FE 는 "선택한 위치"
- 오류: `q`·`near`·`lat`·`lng` 형식이 틀리면 400 `invalid_query`(field = 그 이름). 카카오를 못 부르면 503 `geocode_unavailable`(§6)

## 변경 이력
| 날짜 | 버전 | 변경 | 누가 |
|---|---|---|---|
| 2026-11-01 | v0.1 | 초안 (지오코더 버전) | — |
| 2026-11-03 | v0.2 | geometry 유니온(polyline/link_ids/point/zone/crosswalk_ids), evidence 구조화, baseline을 자체 그래프로, /closures에 예정-구역 Polygon 추가 | — |
| 2026-11-04 | v0.3 | enum 코드값 영어화(§4), 오류 응답(§6), 코드 구현을 naru_contracts로 일원화 (ADR-006) | — |
| 2026-11-04 | v0.4 | §1.1 AI→BE 전송(`POST /internal/candidates`, 멱등 batch), 401 `unauthorized`, FE는 `/api/*` rewrites 경유 (ADR-006 개정 1) | — |
| 2026-11-06 | v0.5 | §1 geometry를 `point / line / segment / zone`으로 재정의, `segment`(from/to/via PlacePoint + road_class)·`notice_ref` 추가, source에 smpa/topis/news/seoul_press, Claude API 확정(ADR-007) | — |
| 2026-11-07 | v0.6 | §1 `impact`(필수, blocks/unknown)·`toward`·`approx` 추가, unknown이면 confidence ≤ 0.65, §2 `avoided[].approx`, §3 properties `impact`·`approx`, §4 `impact` 행 (ADR-008) | 태우 승인 |
| 2026-11-07 | v0.6 | §3 `at` 의미 보강: 진행 중 + 60분 안 시작 예정, status는 `at` 기준 재판정 (스키마 변경 없음) | 태우 결정 |
| 2026-11-08 | v0.7 | §2 `legs[].coord_range` [i, j] 필수(route.coordinates 인덱스, 양끝 포함, 레그가 경로를 빈틈없이 나눔), 접근 구간을 sidewalk 레그로 셈해 Σ legs.distance_m = distance_m (ADR-009) | 태우 승인 |
| 2026-11-08 | v0.8 | §3.1 `GET /closures/events` 추가 — DB 통제를 (reason, window) 사건으로 묶은 목록, 상태 없음, 시작 늦은 순 (ADR-010) | 태우 승인 |
| 2026-11-08 | v0.9 | §5 예정은 공지 창 안에서만 횡단보도당 +300초(×3 폐지), §6 `out_of_coverage`(422, 붙임 150 m 초과) (ADR-011 A) | 태우 승인 |
| 2026-11-08 | v0.10 | §3.1 응답에 `coverage`(보행망 bbox) 필수 (ADR-011 C 의 앞부분, data_as_of 는 뒤에) | 태우 승인 |
| 2026-11-08 | v0.11 | §7 지오코딩 `GET /geocode/search`·`GET /geocode/reverse` 추가, §6 `geocode_unavailable`(503) (ADR-011 B) | 태우 승인 |
| 2026-11-08 | v0.12 | §1 `summary`(구조화 칸: 구간·지점 이름·reported_people·roads), §3.1 사건 `type`·`source`·`summary`·`notice`, 응답 `data_as_of` 필수 (ADR-012, ADR-011 C) | 태우 승인 |
| 2026-11-08 | v0.12 (보충) | §2 `legs[].name` 뜻 — 횡단보도는 교차로명, 없으면 가까운 도로명. 스키마 그대로 (ROADMAP T5.10) | 태우 (T5.10) |
| 2026-11-08 | v0.12 (보충) | §1 돌발 후보(집회 10B02만·TOPIS 링크 선·0.9·`topis_incident` 를 같은 횡단보도·겹치는 시각의 공지 후보에도), §3.1 `data_as_of.topis_incident` = 돌발 배치를 마지막으로 받은 시각. 스키마 그대로 (ROADMAP T6.1) | 태우 (T6.1) |
| 2026-11-08 | v0.13 | §1.2 `POST /internal/bus-positions` 버스 위치 전송 추가(getBusPosByRtid 필드 그대로, 같은 노선·차량·시각은 한 번) — 버스는 후보를 만들지 않는다 (ADR-013 D) | 태우 승인 (ADR-013) |
