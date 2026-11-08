# ADR-011 실서버 운영 결정 묶음 — 라우터 비용·그래프 밖·지오코딩·데이터 신선도·운영 워커 live·외부 수집
- 상태: **승인** (2026-11-08, 태우) — naru.antaewoo.com 을 실제로 눌러 보고 실서버 API 를 직접 불러 본 뒤 "승인한 결정 — ADR 하나에 묶어서 초안". A 의 창 밖 처리는 같은 날 질문으로 확정("창 안에서만 +300초")
- 개정 대상: INTERFACE §2(avoided 표기)·§3.1(coverage·data_as_of)·§5(라우터 반응)·§6(`out_of_coverage`)·§7(지오코딩, 새로), ARCHITECTURE 상태기계 표의 Router 칸, `.claude/CLAUDE.md` §2(운영 워커 상한)
- 구현 Task: A·A′ → T5.5, B → T5.8, C → T5.9, D·E → T6.1·T6.2·T6.4

## 맥락 (실서버에서 본 것, 2026-11-08)
- 잠실 3/15 10:00 요청(37.5133,127.0980 → 37.5145,127.1035)이 그래프 밖인데 먼 노드에 붙어 16.9 km·14,118초 경로가 나왔다
- 11/7 15:00 세종대로 건너기(37.56368,126.97230 → 37.56368,126.98193)가 예정 집회(공지 15:00–16:00)를 피하지 않았다. 지금 규칙 "예정이면 간선 길이 ×3"은 짧은 횡단보도에서 수십 m 라 우회가 생기지 않는다
- 장소를 이름으로 찾거나 고른 점의 주소를 볼 방법이 없다(좌표만 보인다)
- 화면의 통제가 언제 데이터인지 알 수 없다
- 운영 워커가 `--once` 로 기록 5건만 재생하고 끝난다(live 0)

## 결정
A. **라우터 비용** — scheduled 통제는 횡단보도에 닿는 시각이 공지 창 안(start ≤ 도착 ≤ end)일 때만 그 횡단보도마다 +300초 페널티(상수 `scheduled_penalty_s`, 비용 단위가 m 라 걷는 속도로 환산). 하드 차단이 아니다. 창 밖(시작 전·끝난 뒤)은 보통 간선이고 지금의 "예정 ×3"은 없앤다. confirmed 는 지금처럼 차단. 확신도 0.7 미만 예정·예정 구역은 지금처럼 무시. 상태기계는 그대로 두고 라우터 비용만 바꾼다. FE 는 avoided[] 의 status 로 confirmed "통제 중" / scheduled "공지상 통제 시간 · 현장 확인 전"을 나눈다

A′. **그래프 밖** — 출발·도착을 그래프 노드에 붙일 때 거리 상한 150 m(상수 `max_snap_m`). 넘으면 422 `out_of_coverage`(field 는 from 또는 to). INTERFACE §6 오류 코드에 넣는다

B. **지오코딩** — 장소 검색·주소 변환은 BE 가 카카오 로컬 API 를 대신 부른다. 키는 서버에만 둔다. `GET /geocode/search?q=&near=lat,lng`, `GET /geocode/reverse?lat=&lng=` 를 INTERFACE 에 넣는다. 테스트는 `data/recorded/kakao/` 재생

C. **데이터 신선도** — `/closures/events` 응답에 `coverage`(그래프 bbox)와 `data_as_of {topis_incident, topis_notice, smpa, course}` 를 넣는다

D. **운영 워커 live** — 운영 워커는 Claude live 파싱을 한다. 하루 상한 `NARU_LLM_DAILY_CAP=200`, 넘으면 다음 날로 미룬다. 응답은 전부 `data/recorded/llm/` 에 기록한다. CLAUDE.md §2 의 "Task당 10회"는 개발·테스트 규칙이고, 운영 워커는 이 상한을 따른다

E. **외부 수집** — robots.txt 를 지킨다. 같은 곳 요청 간격은 최소 10분. User-Agent 는 `NaruBot/0.1 (+https://naru.antaewoo.com)`. 받은 원문은 `data/recorded/<source>/<timestamp>.*` 에 그대로 저장한다

## 근거
- A: 예정 집회를 실제로 피하게 하되, 현장 확인 전이라 막지는 않는다(돌아가는 길이 300초 넘게 길면 원래 길). 창 밖까지 피하면 아직 시작도 안 한 통제 때문에 돌아간다
- A′: 그래프 밖 좌표를 먼 노드에 붙이면 틀린 경로를 자신 있게 보여 준다. 없다고 말하는 게 낫다
- B: 키를 브라우저에 두지 않고, 응답을 기록·재생해 테스트할 수 있다
- C: 사용자가 화면의 통제를 얼마나 믿을지 판단할 근거
- D·E: 실시간 공지를 읽되 비용과 상대 서버 부담에 상한을 둔다

## 결과
- T5.5: 라우터 비용·`out_of_coverage`, INTERFACE §5·§6, ARCHITECTURE 표, 회귀 테스트 3개, recorded 재기록(3/15 04:30 경로는 원래 길로 바뀐다)
- T5.8: INTERFACE §7, contracts, BE Geocoder, recorded kakao
- T5.9: INTERFACE §3.1 coverage·data_as_of
- T6.1·T6.2·T6.4: 워커 live·수집 규칙, CLAUDE.md §2 한 줄
