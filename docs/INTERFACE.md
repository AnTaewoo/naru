# INTERFACE.md — 파트 간 계약 v0.15

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
- `evidence[].kind ∈ {notice, timetable, topis_incident, bus_skip, bus_return, rtd_spike}`. `ref`는 데이터·recorded 파일 경로. '통제 중' 근거는 `timetable`·`topis_incident` 둘뿐 — `bus_skip`·`bus_return` 은 값으로 남지만 상태를 바꾸지 않는다(ADR-013 보류, 2026-11-09).
- TOPIS 교통통제 지도 예정 통제(producer `notice`, T7.3, ADR-014 B): 지도 목록의 예정(ingYn N) 집회(10B02, 보도 집회 빼고) — `candidate_id` `topismap-<acc_id>-<k>`, `source` `topis`, 경로 = 통제 도로 링크를 노드 이름으로 이은 선(링크 목록이 아직 없으면 대표 링크), 확신도 0.85, 근거 `notice`(`detail.feed` = `topis_map`, `ref` = 목록 원문#acc-<acc_id>), `notice_ref.source_url` = 지도 페이지. 시작해 OA-13315 돌발이 오면 같은 횡단보도·겹치는 시각이라 그 돌발 근거가 붙어 '통제 중'(아래 돌발 줄). 스키마 그대로.
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
버스는 후보(통제)를 만들지 않고 상태도 바꾸지 않는다 — 확신도 보정은 뺐다(ADR-013 보류, 2026-11-09: 1개 차로 행진 시간 안에 버스가 구간을 경로대로 124회 지나감). 워커는 **기록만** 한다: `NARU_BUS_RECORD_ONLY=1`(기본)이면 이 엔드포인트를 부르지 않는다. 0 이면 받은 위치를 판단 없이 그대로 보내고 BE 는 `bus_positions` 에 저장만 한다(T6.2). 어느 노선을 부르나:
- 전면 통제(공지 파싱 `lanes.scope` full·one_side_full)·마라톤(`type` marathon)의 통제 창(시작 1시간 전 ~ 끝+30분)에 그 통제 횡단보도 100 m 안 정류소가 많은 노선, 사건마다 최대 3개, 60초마다. 원문 `data/recorded/bus/notice/`(전면 통제)·`bus/marathon/`.
- 심야(N)·새벽 노선 제외, 하루 900회 상한. `bus/incident/`(2순위 TOPIS 돌발)는 2026-11-09 까지의 기록 — 대상에서 뺐다.

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

**요청** `from=lat,lng` · `to=lat,lng` · `depart_at=ISO8601` · `mode=walk` · `avoid=<사건 id,…>`(선택, v0.14)  (FE는 같은 오리진 `/api/route`로 호출 → Next.js rewrites → Flask `/route`)

- `avoid` (v0.14, ADR-014 A — "이 구역 피해서 길찾기"): §3.1 사건 `id`(12자리 소문자 16진수)를 쉼표로, 10개까지(겹치면 하나). 그 사건의 횡단보도는 시각·확신도와 상관없이 막는다(§5 규칙보다 앞). 없는 id 는 무시한다(지난 공유 링크). 기준 경로가 그 횡단보도를 지나면 `avoided[]` 에 들어가고, `status` 는 그 시각의 실제 상태(`released`·`scheduled` 일 수 있다) — FE 는 자기가 보낸 사건의 `reason`·끝(`until`)으로 알아본다.

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
     "evidence": [{"kind": "topis_incident", "ref": "data/recorded/incident/20270321T080015_AccInfo.json", "at": "2027-03-21T08:00:15+09:00"}]}
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

### §3.1 BE → FE: `GET /closures/events` (v0.8 ADR-010, v0.12 ADR-012, v0.14 ADR-014)

**요청** `bbox=minLng,minLat,maxLng,maxLat` (선택 — 없으면 전체). v0.14: `at`(ISO 8601 + 오프셋)을 주면 **지금 지도** — `[from, to]` 와 겹치는 사건만(`from` 기본 `at`, `to` 기본 `at` 의 다음 날 24:00 KST), 사건 `status` 는 `at` 기준. 겹침 = 시작 ≤ `to` 이고 (끝 또는 시작+6시간) + 30분 ≥ `from`. `from`·`to` 는 `at` 과 같이만. 셋 다 없으면 전부(하위 호환, `status` 는 서버 지금).

**응답** DB 에 있는 통제를 사건으로 묶은 목록. 사건 = 같은 `(reason, window.start, window.end)` 의 횡단보도 상태들
```json
{
  "events": [
    {"reason": "15:00~16:00 시의회~숭례문R → 광화문·고용노동청 <태평로 등> 50,000명 중부, 종로, 남대문",
     "window": {"start": "2026-11-07T15:00:00+09:00", "end": "2026-11-07T16:00:00+09:00"},
     "crosswalks": 31, "bbox": [126.9757, 37.5605, 126.9877, 37.5759], "approx": false,
     "id": "2e930ec6deeb", "status": "scheduled", "confidence": 0.75, "area": null, "centroid": null,
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
     "id": "adaea2f4cc02", "status": "released", "confidence": 0.9, "area": null, "centroid": null,
     "type": "marathon", "source": "course", "summary": null, "notice": null}
  ],
  "at": "2026-11-07T15:30:00+09:00", "truncated": false,
  "coverage": [126.948108, 37.54265, 127.026684, 37.631483],
  "data_as_of": {"topis_incident": null, "topis_notice": null,
                 "smpa": "2026-11-06T18:00:00+09:00", "course": "2026-03-12T16:07:00+09:00"}
}
```
- 순서: `window.start` 가 늦은 것 먼저, start 가 없으면 끝.
- `crosswalks` = 서로 다른 횡단보도 수(1 이상). 같은 공지 문장이 구간 여러 개로 나뉘어도 한 사건이다. `bbox` = 그 횡단보도들의 [minLng, minLat, maxLng, maxLat]. `approx` = 하나라도 근사면 true.
- `id` (v0.14) **필수** — `sha1("<reason>|<시작 UTC YYYY-MM-DDTHH:MM:SSZ>|<끝 UTC>")`(UTF-8, 없는 시각은 빈 문자열) hex 앞 12자. 같은 사건은 다시 받아도 같고, 공지 글이 고쳐져 reason·창이 바뀌면 새 id. FE 공유 링크 `?event=<id>`·알림(B)이 쓴다.
- `status` (v0.14) **필수** — 응답 `at` 기준 그 사건 횡단보도 상태 중 가장 심한 것(`confirmed` > `scheduled` > `zone_scheduled` > `released`, 규칙은 §3 과 같다). `confidence` **필수** — 그 사건 횡단보도 확신도 중 가장 큰 값. FE 의 "1시간 안 시작"·"확신도 0.7 미만"은 `window`·`confidence` 로 FE 가 가른다.
- `area`·`centroid` (v0.14) — 통제 구역(GeoJSON Polygon·MultiPolygon, EPSG:4326)과 그 중심 `[lng, lat]`. T7.2 전에는 null.
- 응답 `at` (v0.14) **필수** — 사건 `status` 의 기준 시각. `truncated` — `at` 을 주면 한 번에 300건까지(심한 상태·시작 가까운 순으로 고른 뒤 위 순서), 넘으면 true.
- `ETag`(v0.14) — 응답 본문 sha1. `If-None-Match` 가 같으면 `304`(본문 없음), `Cache-Control: no-cache`. FE 60초 갱신이 쓴다.
- FE "통제 불러오기": 누르면 t = `window.start`, 지도 = `bbox`. start 가 없는 사건은 누를 수 없다.
- `coverage` (v0.10, ADR-011 C) **필수** — 보행망(그래프) 노드의 [minLng, minLat, maxLng, maxLat]. FE 는 내 위치가 이 밖이면 길찾기 범위 밖이라고 안내한다(사각형이라 안쪽이어도 보행망에서 150 m 넘으면 `/route` 가 `out_of_coverage`).
- `type`·`source` (v0.12, ADR-012) — 사건을 만든 후보의 종류·출처(§4 enum). v0.12 전에 저장된 상태라 모르면 null. `summary` — 후보의 summary(§1) 그대로, 없으면 null(코스 등). `notice` — 후보의 `notice_ref`(§1) 그대로, 공지가 아니면 null. FE 는 summary 로 제목·둘째 줄을 만들고(없으면 `reason`), `notice.excerpt` 는 상세의 "공지 원문 보기"에서만 보인다.
- `districts` (v0.13 보충, T6.9) — 사건 횡단보도들이 있는 자치구(OA-23081 자치구 이름 그대로, 가나다순). 빈 목록이 기본이라 이전 응답·클라이언트는 그대로. FE 통제 불러오기의 구 필터 칩(지도 화면 안의 구 먼저).
- `data_as_of` (v0.12, ADR-011 C·ADR-012) **필수** — 출처마다 그 출처로 저장된 통제의 가장 늦은 근거 시각, 없으면 null: 공지(`smpa`, `topis_notice` = source `topis`)는 공지 게시 시각, `course` 는 시각표 게시 시각(상태 전이 근거는 뺀다), `topis_incident`(= source `incident`)는 돌발 배치를 마지막으로 받은 시각(범위 안 돌발이 없는 빈 배치·같은 배치 재전송 포함, T6.1). 예시는 2026-11-08 개발 DB(서울경찰청 11/6 18:00 공지 · 서울마라톤 3/12 16:07 시각표). FE 는 기준 시각을 `/licenses` 맨 아래 "데이터 기준 시각"에 쓰고(시트에는 없다, T7.12·T7.13), 시트에는 `topis_incident` 가 30분보다 오래면 슬라이더 위 한 줄 "통제 정보가 N분째 갱신되지 않았어요"(받은 적 없음 = null 이면 경고 없음).

### §3.2 BE → FE: `GET /closures/events/{id}/march?from=&to=` (v0.15, ADR-015 F)
행진 확률 모델(ADR-015)의 예상 위치 키프레임. 대상 = type `march`, 창 시작·끝, 순서 있는 경로 하나(공지 구간 seg1..N 이 이어지거나 TOPIS 통제지도 사슬 하나). 대상이 아니면(갈라진 행진·집회·마라톤·없는 id) 404 `not_modeled`. `ClosureEvent`(§3.1) 스키마는 그대로 — FE 는 `type` 이 `march` 일 때만 부르고 404 면 정지 표시.
- `from`·`to`(ISO 8601 + 오프셋, 선택): 키프레임 범위. 기본 통제 창 전체. `[from, to] ∩ [start, end]` 를 `step_s`(60) 간격으로.
```json
{
  "event_id": "be5f89a4ebf3",
  "window": {"start": "2026-11-07T12:00:00+09:00", "end": "2026-11-07T16:00:00+09:00"},
  "step_s": 60,
  "crosswalk_points": {"06-0000036391": [126.97690673127867, 37.57012839904125],
                       "06-0000023206": [126.97713080460589, 37.57005044939709],
                       "06-0000002104": [126.97953158269354, 37.570204808084355]},
  "keyframes": [
    {"t": "2026-11-07T12:00:00+09:00",
     "samples": [[[126.975854, 37.569443]], [[126.975854, 37.569443]]],
     "center": [126.975854, 37.569443], "radius_m": 0.0,
     "crosswalks": {"06-0000036391": 1.0, "06-0000023206": 1.0, "06-0000002104": 0.2}}
  ]
}
```
- 2026-11-10 기록 `naru_api/march_be5f89a4ebf3.json`(11/7 r01 동화면세점 앞 → 종로1R → 동화면세점 앞, 50,000명, 12:00~16:00)의 첫 키프레임 — 표본 21개 중 2개, 횡단보도 13곳 중 3곳만 남긴 것. 시작 시각이라 머리가 출발점에 있고(점 하나씩, 반경 0), 출발점에서 300 m(`march_lead_m`) 안의 세종대로사거리 둘은 P 1.0, 1 km 뒤 종로구청입구는 하한 0.2.
- `keyframes[]`: `t` 시각(시각 순) · `samples` 표본(속도)별 머리~꼬리 점 `[lng, lat]`(경로 위 `march_point_step_m` 25 m 간격, 키프레임당 `march_points_max` 600 상한 — 넘으면 간격을 넓힌다) · `center` 그 점들의 가운데 · `radius_m` 그 점들이 퍼진 반경(표시용) · `crosswalks` 경로 위 횡단보도 id → 그 시각 막혀 있을 확률 0~1(창 안 하한 `march_p_floor` 0.2, 통제 중 행진은 `march_p_floor_confirmed` 0.5 — 라우터가 쓰는 값과 같다).
- `crosswalk_points`: 경로 위 횡단보도 id → `[lng, lat]`. FE 가 P 색을 칠할 점.
- FE 문구는 "공지 일정 기준 예상 위치" — 실제 추적처럼 보이는 말은 쓰지 않는다. 두 키프레임 사이는 FE 가 보간한다.
- `ETag`(본문 sha1)·`If-None-Match` → 304, `Cache-Control: no-cache` (§3.1 과 같다).

### §3.3 누구나: `GET /closures/feed?at=` — 통제 데이터 GeoJSON 피드 (v0.15 보충, T7.17 — 교수님 멘토링 T-C)
그 시각(`at`, ISO 8601 + 오프셋, 없으면 서버 지금, 분 단위로 내림)에 걸린 통제를 GeoJSON FeatureCollection 으로. 판정은 `/closures`·`/closures/events`·`/route` 와 같다(상태는 `at` 기준, 행진 확률 모델 사건은 §3.2 의 P). 인증 없음, CORS `*`, `Cache-Control: public, max-age=60`, ETag·304. IP 당 분당 60회(`feed_rate_per_min`)를 넘으면 429 `rate_limited`(§6).
```json
{
  "type": "FeatureCollection",
  "at": "2026-11-07T13:00:00+09:00",
  "generated_at": "2026-11-10T20:11:59.431205+09:00",
  "attribution": "나루(naru.antaewoo.com) — 서울 열린데이터광장(횡단보도 OA-23081, TOPIS 돌발 OA-13315, 공공누리 1유형)·서울경찰청 집회 공지·TOPIS 통제 공지·서울마라톤 공지를 읽어 만든 추정값. 실제 통제와 다를 수 있다",
  "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [126.9769067, 37.5701284]},
     "properties": {"kind": "crosswalk", "crosswalk_id": "06-0000036391", "name": "세종대로사거리", "p": 1.0,
                    "event_id": "be5f89a4ebf3", "event": "12:00~16:00 동화면세점 앞 → 종로1R → 동화면세점 앞 <세종대로 등> 50,000명 종로, 남대문",
                    "type": "march", "source": "smpa", "start": "2026-11-07T12:00:00+09:00", "end": "2026-11-07T16:00:00+09:00",
                    "status": "scheduled", "confidence": 0.85, "approx": false}},
    {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[126.975854, 37.569443], [126.975823, 37.569522]]},
     "properties": {"kind": "march_path", "crosswalk_id": null, "name": null, "p": null,
                    "event_id": "be5f89a4ebf3", "event": "12:00~16:00 동화면세점 앞 → 종로1R → 동화면세점 앞 <세종대로 등> 50,000명 종로, 남대문",
                    "type": "march", "source": "smpa", "start": "2026-11-07T12:00:00+09:00", "end": "2026-11-07T16:00:00+09:00",
                    "status": "scheduled", "confidence": 0.85, "approx": false}}
  ]
}
```
- 2026-11-10 기록 `naru_api/feed_1107_1300.json`(11/7 13:00 — 횡단보도 37·구역 7·행진 경로 1)에서 11/7 r01 사건의 횡단보도 하나와 경로(점 39개 중 앞 둘)만 남긴 것.
- `features[].properties.kind`: `crosswalk`(Point — 그 사건이 막는 횡단보도, `crosswalk_id`·`name` 교차로명·`status` 그 시각 상태·`confidence`·행진 모델 사건이면 `p`) · `area`(Polygon·MultiPolygon — 사건 통제 구역, §3.1 `area` 와 같다) · `march_path`(LineString — 행진 모델 사건의 경로). 사건 칸은 셋이 같다: `event_id`(§3.1 id)·`event`(이름 = reason)·`type`·`source`(§4)·`start`·`end`·`approx`.
- 같은 사건·같은 횡단보도는 하나(후보 여럿이 골라도) — 가장 심한 상태. `p` 는 창 밖이면 0, 경로 밖·행진 모델 아님이면 null.
- `at`·`generated_at`·`attribution` 은 GeoJSON 여분 멤버(RFC 7946 §6.1). `attribution` 을 붙여 쓴다 — 공공누리 1유형(출처 표시), 추정값임을 밝힌다.

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
- (v0.15, ADR-015 E) 행진 확률 모델 대상 사건(§3.2)의 경로 위 횡단보도는 `scheduled`든 `confirmed`든 창 전체 대신 그 시각 P(t, s): 비용 = P × 300초, P ≥ 0.8(`march_p_block`)이면 차단, 창 밖은 P 0, 창 안 하한은 예정 0.2·통제 중 0.5. 비용이 붙은 횡단보도도 `avoided` 에 그 시각 상태로.

## §6 오류 응답 (Flask)
```json
{"error": {"code": "invalid_query", "message": "depart_at: 오프셋 없는 시각", "field": "depart_at"}}
```
- `code ∈ {invalid_query, unauthorized, not_found, no_route, out_of_coverage, geocode_unavailable, too_many_reports, not_modeled, rate_limited, internal}`. HTTP 400 / 401 / 404(`not_found`·`not_modeled`) / 422(`no_route`·`out_of_coverage`) / 429(`too_many_reports`·`rate_limited`) / 503(`geocode_unavailable`) / 500. Flask `error_view`(View 계층)가 만든다.
- `out_of_coverage` (v0.9, ADR-011): 출발·도착을 보행망 노드에 붙일 거리가 150 m(`max_snap_m`)를 넘는다. `field` = `from` 또는 `to`.
- `geocode_unavailable` (v0.11, ADR-011 B): 카카오 로컬을 못 불렀다 — 서버 키 없음·카카오 오류·시간 초과(재생 모드면 기록 없음). FE 는 검색이면 "검색을 못 했어요", 주소면 "선택한 위치".
- `too_many_reports` (v0.14 보충, T7.15): 같은 기기가 같은 횡단보도를 600초(`report_min_interval_s`) 안에 다시 제보했다(§8.2). `field` = `crosswalk_id`.
- `not_modeled` (v0.15, ADR-015 F): 행진 확률 모델 대상이 아닌 사건 — 없거나, 방향을 모르거나 갈라진 행진, 집회·마라톤(§3.2). `field` = `event_id`.
- `rate_limited` (v0.15 보충, T7.17): 공개 피드(§3.3) IP 당 분당 60회를 넘었다. `field` 없음.

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

## §8 FE → BE: 통제 제보 (v0.14 보충, 태우 지시 11/10 — 교수님 멘토링 T-A)
사람이 지금 위치에서 가장 가까운 횡단보도를 "막혔어요 / 열렸어요"로 남긴다. **기록만** — 경로·확신도·상태에 쓰지 않는다(버스 신호와 같은 원칙, ADR-013 보류). 현장 검증 제보(`source` = `field`)는 `scripts/field_compare.py` 가 그 시각 나루 예측과 맞춰 본다.
- 좌표는 §8.1 요청 본문으로만 받는다(POST — 쿼리 문자열·접근 로그에 안 남게). 저장·로그하지 않는다. 제보 행에는 횡단보도 ID·상태·서버 시각·정확도·출처·기기 해시(sha256)만 남는다.
- 횡단보도 ID 는 OA-23081 횡단보도관리번호 모양(숫자 2 `-` 숫자 10).

### §8.1 `POST /crosswalks/nearest`
- 본문 `{"lat": …, "lng": …}`(범위는 §7.2 와 같다, 다른 칸은 받지 않는다). 100 m(`report_snap_m`) 안에서 가장 가까운 횡단보도, 없으면 `{"crosswalk": null}`
```json
{"crosswalk": {"id": "06-0000051345", "name": "교보생명", "district": "종로구",
               "coord": [126.97768829792257, 37.571585764131775], "distance_m": 71}}
```
- §7.1 광화문교보빌딩 카카오 좌표에서. OA-23081 행 20198(교차로명 '교보생명', 종로구), 71.1 m. `name` = 교차로명, `coord` = [lng, lat], `distance_m` = 요청 점과의 거리(EPSG:5179, 반올림)

### §8.2 `POST /reports`
- 본문 `{crosswalk_id, state, accuracy_m, source, device}` — `state` ∈ {`blocked`, `open`}, `accuracy_m` 위치 정확도 0~1000(정수 m, 브라우저 값 반올림), `source` ∈ {`user`, `field`(현장 검증 — FE `?mode=field`)}, `device` 기기 토큰(영문·숫자·`-` 16~64자, FE 가 처음 한 번 만든 무작위 값). BE 는 토큰의 sha256 만 저장한다
- 201 `{id, crosswalk_id, state, reported_at}` — `id` 정수, `reported_at` 서버가 받은 시각(+09:00)
- 오류: 본문 형식 400 `invalid_query`(field = 그 이름), 범위에 없는 횡단보도 400 `invalid_query`(field `crosswalk_id`), 같은 기기·같은 횡단보도 600초 안 429 `too_many_reports`(§6)

### §8.3 `GET /reports/recent?ids=&minutes=60`
- `ids` 횡단보도 ID 쉼표(1~50개, 겹치면 하나), `minutes` 1~1440(기본 60)
- 200 `{"counts": {"<id>": {"blocked": n, "open": n}}}` — 그 시간 안에 제보가 있는 ID 만. FE 통제 근거(§2 `avoided` 사유별) "최근 1시간 제보 N건"

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
| 2026-11-09 | v0.13 (보충) | §3.1 사건 `districts`(자치구, 기본 빈 목록) 추가 — 서비스 범위 서울 전체(T6.9)의 구 필터 칩 | 태우 (T6.9) |
| 2026-11-09 | v0.13 (보충) | ADR-013 보류 — §1 `bus_skip`·`bus_return` 은 상태를 바꾸지 않는다('통제 중' 근거 = `timetable`·`topis_incident`), §1.2 버스는 전면 통제·마라톤만 기록(`NARU_BUS_RECORD_ONLY`), §2 예시 근거 `topis_incident`. 스키마 그대로 | 태우 (2026-11-09) |
| 2026-11-09 | v0.14 | §3.1 `GET /closures/events` 에 `at`·`from`·`to`(지금 지도 — 시간 창), 사건 `id`·`status`·`confidence` 필수·`area`·`centroid`(T7.2 까지 null), 응답 `at`·`truncated`, ETag·304 (ADR-014 A, T7.1) | 태우 승인 (ADR-014) |
| 2026-11-10 | v0.14 (보충) | §3.1 `data_as_of` FE 표시 설명만 — 기준 시각은 `/licenses`, 시트는 TOPIS 돌발 30분 멈춤 경고만(null 은 경고 없음, T7.12·T7.13). 스키마 그대로 | 태우 (11/10) |
| 2026-11-10 | v0.14 (보충) | §2 `GET /route` 에 `avoid`(사건 id 쉼표, 10개까지) — 그 사건 횡단보도를 시각·확신도와 상관없이 막음, 없는 id 는 무시, 응답 스키마 그대로 (ADR-014 A, T7.6) | 태우 승인 (ADR-014) |
| 2026-11-10 | v0.14 (보충) | §8 통제 제보 `POST /crosswalks/nearest`·`POST /reports`·`GET /reports/recent` 추가 — 기록만(경로·확신도·상태에 안 씀), 좌표는 본문으로만·저장 안 함, 기기는 해시. §6 `too_many_reports`(429) | 태우 지시 (11/10, T7.15) |
| 2026-11-10 | v0.15 | §3.2 `GET /closures/events/{id}/march` 행진 예상 위치 키프레임(표본 점·중심·반경·횡단보도별 P, 1분), §5 행진 예정 비용 = P × 예정 비용(P ≥ 0.8 제외, scheduled·confirmed 모두), §6 `not_modeled`(404) (ADR-015) | 태우 승인 (ADR-015) |
| 2026-11-10 | v0.15 (보충) | §3.3 `GET /closures/feed?at=` 공개 GeoJSON 피드(횡단보도·사건 구역·행진 경로, 사건 칸·상태·확신도·P, 분 캐시·IP 분당 60회), §6 `rate_limited`(429) | 태우 지시 (11/10, T7.17 — 이력만) |
