# ADR-010 통제 사건 목록 — `GET /closures/events`
- 상태: **승인** (2026-11-08, 태우) — T5.4 계획 승인: "통제 불러오기로 간다, 첫 화면은 지금 시각 그대로 두고 안내 버튼만"
- 개정 대상: INTERFACE v0.7 → **v0.8** §3.1, `naru_contracts.closures_api`(`ClosureEventsQuery`·`ClosureEvent`·`ClosureEventsResponse`), BE `ClosureRepository.events`·`closure_controller`·`closure_view`, FE 하단 시트 "통제 불러오기"
- 계기: 배포(https://naru.antaewoo.com)를 그냥 열면 시각이 "지금"이고, 그 시각 통제는 0건이다. `?t=` 주소를 모르면 통제 → 우회를 못 본다

## 맥락
FE 는 시각 t 와 bbox 로만 통제를 묻는다(`/closures`). 어떤 날·시각에 통제가 있는지 알 길이 없다. DB 에는 2026-03-15 서울마라톤 구간 5개와 2026-11-07 서울경찰청 집회 2건이 있다(2026-11-08 SELECT).

선택지
1. 날짜 달력(FE 만) — 계약 변경 없음. 하지만 통제 있는 날을 사람이 알아야 하고, 대부분의 날은 빈 화면이다
2. FE 에 사건 목록을 상수로 — 새 공지가 들어와도 목록이 그대로이고, 손으로 친 데이터가 된다
3. **DB 의 통제를 사건으로 묶어 주는 `GET /closures/events`** — 이것으로 간다 (태우)

## 결정
1. `GET /closures/events?bbox=minLng,minLat,maxLng,maxLat` — bbox 는 선택, 없으면 전체. 응답 `{"events": [ClosureEvent]}`
2. 사건 = 같은 `(reason, window.start, window.end)` 의 횡단보도 상태 묶음. 같은 공지 문장이 구간 여러 개(후보 여러 개)로 나뉘어도 한 사건이다. FE 시트의 행 묶음(`closureRows`)과 같은 키
3. `ClosureEvent` = `reason`, `window`(+09:00), `crosswalks`(서로 다른 횡단보도 수, 1 이상), `bbox`([minLng, minLat, maxLng, maxLat], 그 횡단보도들), `approx`(하나라도 근사면 true)
4. 순서: `window.start` 가 늦은 것 먼저, start 가 없는 사건은 끝. 계약 검증기가 강제한다
5. 상태(status)는 넣지 않는다. 상태는 시각마다 다시 판정되므로, FE 는 고른 시각으로 `/closures` 를 다시 묻는다
6. FE "통제 불러오기": 사건을 누르면 t = `window.start`, 지도 = `bbox`. start 가 없는 사건은 누를 수 없다

## 근거
- 기준은 DB — 공지가 더 들어오면 목록이 저절로 늘고, FE 에 손으로 친 시각이 없다
- 쿼리 하나(GROUP BY)로 끝나고 응답이 작다(사건 수 × 다섯 필드)
- 상태를 빼서 `/closures` 와 판정이 두 곳으로 갈라지지 않는다

## 결과
- INTERFACE §3.1(v0.8), contracts 세 모델과 예시 테스트, `make schema`
- BE: `ClosureRepository.events(bbox)` → `closure_view.render_events`, 컨트롤러는 검증 → Model → View
- recorded `naru_api/closure_events.json`(`make record-naru-api`) — FE 테스트 입력
- FE: 하단 시트 "통제 불러오기"(날짜별 목록), 통제가 없을 때 빈 칸 안내 버튼, 슬라이더 "지금", 시트 제목 날짜
