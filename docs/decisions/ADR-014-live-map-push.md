# ADR-014 실시간 통제 지도(사건 단위·통제 구역)와 PWA 알림 — 계약·DB·엔드포인트
- 상태: **승인** (2026-11-09 17:05, 태우 "다음" — 계획의 정할 것 15개는 추천안 그대로, 열린 질문도 추천안). 계획 `harness/plans/active/P7_plan.md`
- 개정 대상: INTERFACE v0.14(§1·§2·§3.1, 새 §7), ADR-006 스택(pywebpush), ARCHITECTURE(BE Model·FE·흐름), CONVENTIONS §5(지도 레이어·PWA), DB Alembic 0005·0006
- 구현 Task: P7 T7.1~T7.10 (A 실시간 지도 T7.1~T7.6, B 알림 T7.7~T7.10)

## 맥락
- 지금 앱은 시각·화면 bbox 의 횡단보도 점(`/closures`)과, 버튼을 눌러야 보이는 과거 포함 사건 목록(`/closures/events`)만 보여 준다. 태우(11/9): 앱을 열면 서울 전체 통제를 지도에 바로(A), 관심 지역 근처 통제는 알림으로(B).
- 사건은 closure_states 의 (reason, 시작, 끝) 묶음일 뿐 id 도 모양도 없다. 구간 선(도로 최단경로)은 접수 때 계산하고 버린다.
- 서울 전체 횡단보도 피처는 무겁다 — 3/15 07:45 318개 264 KB(운영 11/9 측정). 사건은 28개 12.5 KB.
- T6.5: TOPIS 통제지도는 예정 통제를 시작 전에, 행진 경로를 링크 순서로 준다(11/9 1109233 링크 19개). OA-13315 에는 시작한 통제만 있다.

## 결정 (안)
A. **사건이 지도의 단위다.**
- `id` = sha1(reason · window_start · window_end, UTC ISO) 앞 12자 — 재접수에도 같고, 공지 글이 고쳐지면 새 id.
- 통제 구역은 BE 가 접수 때 만든다. 후보마다 횡단보도를 고른 모양 그대로 — 구간 = 도로 최단경로 + 등급 버퍼(대로 25·로 15·길 8 m), 선 15 m, 점 30 m — 를 사건 단위로 union → 5 m 단순화 → EPSG:4326 `area`(Polygon·MultiPolygon)와 `centroid`. 표 `closure_events`(0005: event_id PK, reason, window_start·end UTC, type, source, area GeoJSON, centroid lng·lat, crosswalks, updated_at).
- `GET /closures/events?at=&from=&to=&bbox=` — 기본 창은 진행 중 + 내일 24:00(KST), 한 번에 300건(넘으면 `truncated: true`). 사건마다 `id`·`status`(at 기준 그 사건 횡단보도 중 가장 심한 상태)·`confidence`(최대)·`area`·`centroid`. 파라미터가 없으면 지금처럼 전부(하위 호환). ETag = 응답 본문 sha1, `If-None-Match` 가 같으면 304, `Cache-Control: no-cache`.
- `GET /route?avoid=<id,…>` — 그 사건 횡단보도를 시각·확신도와 상관없이 막는다("이 구역 피해서 길찾기").

B. **TOPIS 통제지도 예정 통제(T7.3).** 목록(`selectAccAllListASC`)·통제 도로(`selectAccLinkList`) AJAX 를 웹 페이지 수집 규칙(ADR-011 E — robots 허용 경로, 같은 곳 10분, NaruBot, 원문 기록)으로 받는다. 링크 꼭짓점은 OA-13311 LinkVerInfo(키로 쓰는 공개 API). 후보 ID 는 돌발과 같은 acc_id 라, 예정 통제가 시작되면 OA-13315 돌발이 같은 후보를 이어 받는다. 전체 통제(accRoadYn)는 버스 기록 대상(ADR-013 보류의 전면 통제). 근거 종류·출처 값은 열린 질문 1.

C. **알림.**
- 표 0006: `push_subscriptions`(endpoint 유일, p256dh, auth, active, created·last_ok) · `watch_areas`(subscription, kind saved·last_seen, lng·lat, radius_m 300·500·1000, expires_at — last_seen 은 약 150 m 격자로 반올림, 3시간 뒤 삭제) · `push_sends`(subscription, event_id, kind created·confirmed, due_at, sent_at, http_status, 유일키 (subscription, event_id, kind)).
- 엔드포인트(새 §7): `GET /push/vapid-public-key` · `POST·DELETE /push/subscribe` · `GET·POST·DELETE /watch-areas` — 계정 없이 구독 endpoint 가 손잡이 · `POST /internal/push/dispatch`(워커 `push` 소스 60초, 토큰).
- 매칭: created(처음 보는 사건 id)·confirmed(at 에 통제 중이 된 사건) → impact blocks·확신도 ≥ 0.7 → 관심 지역 원과 사건 구역의 교차(STRtree) → (구독, 사건, 종류)당 한 번 → 22~07시 created 는 07:00 에 모아서 → pywebpush, 410·404 면 active=false. VAPID 키는 `.env`(태우).
- 서비스워커는 push 를 받으면 항상 showNotification, 누르면 `/?event=<id>&t=<시작>`.
- 확인은 실제 구독(태우 PC Chrome·폰)으로만 — 가짜 push 엔드포인트를 만들지 않는다.

D. **스택.** BE 에 pywebpush(+ py-vapid·http-ece·cryptography)를 더한다(ADR-006). FE 는 새 의존성 없음 — 클러스터는 maplibre 내장, manifest 는 Next App Router `app/manifest.ts`, 서비스워커는 `public/sw.js`. Provider 는 4개 그대로(CONVENTIONS §5.5) — 알림 상태는 훅.

## 대안
- 통제 구역을 FE(turf.js)에서 — 공간 연산은 Python(CLAUDE.md §3-5), 의존성·휴대폰 계산·BE 와 모양 불일치로 안 한다.
- 통제 구역을 읽을 때 횡단보도 점만으로 — DB 는 그대로지만 구간 선이 없어 횡단보도 사이가 먼 곳은 끊긴 원이 된다.
- 사건 id 를 DB 일련번호로 — 재접수·재적재 때 바뀌어 공유 링크·알림 중복 제거가 깨진다.
- 발송을 BE 안 스레드로 — gunicorn 워커 2개라 같은 알림이 두 번 갈 수 있다.

## 열린 질문 (계획 "태우가 정할 것"과 같은 번호)
1. (6) TOPIS 통제지도 예정 통제: 예정 단계 근거를 공지처럼(0.85, '통제 중'은 OA-13315 가 와야) 둘지, topis_incident 로 둘지. 출처 값은 incident 재사용 / 새 값 `topis_map`.
2. (8) avoid 의 뜻 — 무조건 막음 / 지금 규칙.
3. (12) 구독 테스트 입력 — 태우 실제 구독을 토큰·키를 가린 채 `data/recorded/push/` 에 기록 / 수동만.
4. (13) 개인정보 안내 위치.

## 결과
- 사건 응답이 커진다(구역) — gzip 100 KB 목표, ETag 304 로 60초 폴링 비용은 작다.
- 접수가 조금 느려진다(사건마다 union) — T7.2 에서 잰다.
- 지도 홈의 기본이 "지금 서울 통제"로 바뀌고 "통제 불러오기"(ADR-010)는 날짜 선택 슬라이더로 대체된다.
