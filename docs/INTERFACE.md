# INTERFACE.md — 파트 간 계약 v0.6

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
  "review_required": false
}
```
`geometry.kind`별 필드 (kind에 맞는 것만, 나머지는 없음):

| kind | 필드 | 누가 만드나 | BE 처리 (`CrosswalkIndex`) |
|---|---|---|---|
| `point` | `coordinates: [lng, lat]` | 리졸버 (교차로·장소·주소) | `from_point` 반경 30m. `impact: unknown`이면 먼저 도로 30 m 규칙(ADR-008) — 승격 안 되면 `zone_scheduled` |
| `line` | `coordinates: [[lng, lat], …]` | 코스 GPX, 버스 이탈 구간, 돌발 링크 | `from_line` 버퍼 15m (코스·버스), 링크 폭 |
| `segment` | `from_`, `to`, `via[]`: `PlacePoint` · `road`, `road_class` | 리졸버 (Claude segments 출력) | `from_segment`: 도로 그래프 최단경로(from→via→to, road 있으면 그 도로만) → LineString → 등급별 버퍼(대로 25 / 로 15 / 길 8 m) → `from_line` |
| `zone` | `zone_name`, `polygon` | ZoneMatcher | 라우팅 무관, `zone_scheduled` 표시만 |

- `from_`·`to` 중 하나라도 리졸버가 못 풀면 `segment`를 만들지 않고 풀린 쪽만 `point`로 보낸다. 틀린 선보다 빠진 점이 낫다.
- `confidence < 0.7` → `review_required: true`. BE는 적재하되 라우팅에 쓰지 않는다.
- `impact ∈ {blocks, unknown}` **필수** (ADR-008, 파서 규칙서 §9). 파서의 `none`(자동차전용도로·차 없는 거리·보도·차량 조치·해제·안내)은 AI가 후보를 만들지 않는다. `unknown`(점유 표현 없는 지점 집회)이면 `confidence ≤ 0.65`여야 하고(→ review_required), BE `CandidateIntake`가 지점이 도로 링크 30 m 안이거나 지점들이 도로를 감싸면 `blocks`로 승격(evidence `detail.rule: unknown_near_road`), 아니면 `zone_scheduled`로 표시만. 코스·돌발·버스는 항상 `blocks`.
- `toward`: 종료 지점 없는 행진의 방향 표현을 **문장 그대로**(예: `"을지로입구역"`). `geometry.kind ∈ {point, segment}`일 때만. 리졸버가 풀면 AI가 `segment`(출발지 → toward)를 만들고 `confidence`를 0.65로 상한(검토 큐), 못 풀면 `point`만 보낸다.
- `approx`: 파서가 근사 시간("14시경", "오후")을 양끝 10분씩 넓혔으면 `true`. BE는 window를 넓히지도 좁히지도 않고 상태·응답에 그대로 싣는다. 평가는 ±10분 허용.
- `window.end`가 null이면 "종료 미정". 엔진은 시작+6시간을 임시 end로 두고 evidence에 남긴다.
- `evidence[].kind ∈ {notice, timetable, topis_incident, bus_skip, bus_return, rtd_spike}`. `ref`는 데이터·recorded 파일 경로.
- `notice_ref`는 공지에서 온 후보에만. `excerpt`를 FE `EvidencePopover`에 그대로 보여준다.

### §1.1 전송: `POST /internal/candidates` (AI 워커 → BE)
AI와 BE는 서로 import하지 않는다. 후보는 이 엔드포인트로만 넘어간다.

**요청** 헤더 `X-Naru-Internal-Token: <Settings.internal_token>`, `Content-Type: application/json`
```json
{
  "batch_id": "worker-20270321-080015-bus",
  "produced_at": "2027-03-21T08:00:15+09:00",
  "producer": "bus_deviation | course | incident | notice | congestion",
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

## §2 BE → FE: `GET /route` (v0.6)

**요청** `from=lat,lng` · `to=lat,lng` · `depart_at=ISO8601` · `mode=walk`  (FE는 같은 오리진 `/api/route`로 호출 → Next.js rewrites → Flask `/route`)

**응답**
```json
{
  "route": {"type": "LineString", "coordinates": [[126.9751, 37.5658], [126.9769, 37.5725]]},
  "duration_s": 840,
  "distance_m": 1120,
  "legs": [
    {"kind": "underpass", "name": "시청역 지하보도", "distance_m": 120}
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
ARCHITECTURE.md "ClosureState 상태기계" 표가 기준. 임계값(0.7, 0.8, ×3, 30분)은 `naru_be/config.py` 상수. 바꾸면 이 문서와 ARCHITECTURE 표도 같이.

## §6 오류 응답 (Flask)
```json
{"error": {"code": "invalid_query", "message": "depart_at: 오프셋 없는 시각", "field": "depart_at"}}
```
- `code ∈ {invalid_query, unauthorized, not_found, no_route, internal}`. HTTP 400 / 401 / 404 / 422(`no_route`) / 500. Flask `error_view`(View 계층)가 만든다.

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
