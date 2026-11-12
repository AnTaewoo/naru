# P7 계획 — (A) 실시간 통제 지도 · (B) PWA 알림 (초안, 태우 승인 대기)

- 요청: 태우 2026-11-09. A 먼저(11/16 최종 제출 전 완료 목표), B 그다음. 승인되면 T7.1부터 Task 하나씩 → 보고(실제 앱 화면 iPhone 13 스크린샷 1장) → "다음".
- 같이 받은 것: "TOPIS 통제지도 예정 통제 서비스(T6.5 조사분) 붙이자"(11/9 16:4x) → T7.3 으로 넣었다.
- 계약·DB 변경은 ADR 초안 하나: `docs/decisions/ADR-014-live-map-push.md`.
- 번호: ROADMAP 의 기존 "P7 — 현장 실증(2027-03)"과 겹친다 → 정할 것 1.

## 지금 (2026-11-09 운영에서 읽기만 해서 잰 값)
| 요청 | 크기 | 시간 | 내용 |
|---|---|---|---|
| `GET /closures/events` | 12.5 KB | 32 ms | 사건 28(코스 16·돌발 8·경찰청 4), 횡단보도 551 — 과거 포함 전부 |
| `GET /closures` 서울 전체, 3/15 07:45 | 264 KB | 22 ms | 피처 318(통제 중 203·예정 115) |
| `GET /closures` 서울 전체, 11/7 15:30 | 83 KB | 8 ms | 피처 68 |
| `GET /closures` 서울 전체, 11/9 12:00 | 6 KB | 3 ms | 피처 8 |
- ETag 없음. 사건 = closure_states 를 (reason, 시작, 끝)으로 묶은 것이라 **id 가 없다**. 구간 선(도로 최단경로)은 접수 때 계산하고 **버린다** — 다각형을 만들 재료가 저장돼 있지 않다.
- FE: 시트 "오늘 통제" = 지금 화면 bbox 의 `/closures`, "통제 불러오기" = `/closures/events` 전체(T5.4·T6.9 날짜 묶음·구 칩). 위 칩(LayerChips) = 횡단보도 상태 수. 시각은 `?t=`(TimeProvider), 길찾기는 `?from=&to=`. Provider 4개(CONVENTIONS §5.5).

## A. 실시간 통제 지도 — "통제 불러오기"를 대체
**화면 규칙** (요청 그대로, 해석은 ← 표시)
- 앱을 열면 지금 기준 서울 전체 사건을 바로 그린다. "통제 불러오기" 버튼·빈 상태 삭제.
- 사건 상태(시각 t, 그 사건 횡단보도 중 가장 심한 것) ← 사건 단위로 합친다: 통제 중(빨강) · 1시간 안에 시작(진한 주황, 강조) · 오늘·내일 예정(주황) · 예정 구역(보라 윤곽) · 확신도 0.7 미만(흐린 점선, 지도에만 — 목록·칩 수에는 안 셈 ← 정할 것 15).
- 칩 "통제 중 N · 예정 N · 예정 구역 N" = 그 종류 켜고 끄기(예정 = 1시간 안 + 오늘·내일).
- 60초 갱신, ETag(응답 본문 해시)로 304 면 다시 그리지 않는다. 목록 위 data_as_of.
- 줌 3단계: 멀리 = 사건 중심점 클러스터(원 안 개수, 색은 그 안 가장 심한 상태 — maplibre `cluster`·`clusterProperties`, 새 의존성 없음) / 중간 = 사건 구역 다각형 / 가까이 = 횡단보도 하나하나(지금 `/closures` bbox).
- 구역·클러스터를 누르면 하단 시트에 카드. 클러스터 안에 사건이 여럿이면 목록 → 하나 고르면 카드.
- 카드: 원인(집회·행진·마라톤·행사 ← '공사'는 지금 후보가 안 된다(impact none) — 계약 type 에도 없어 표시 안 함)과 제목(ADR-012 summary, ko.ts 템플릿) · "11/14(토) 14:00–16:00" + 상태 + "1시간 20분 뒤 시작" 또는 "16:00 해제 예정" · 출처(경찰청 공지 / TOPIS 공지 / TOPIS 돌발 / 마라톤 시간표 / 보도) · 확신도 높음(≥ 0.8)·보통(0.7~0.8)·낮음(< 0.7) · 막히는 횡단보도 수 · 버튼 "통제 근거 보기"(지금 공지 원문 보기) · "이 구역 피해서 길찾기" · "☆ 이 근처 알림 받기"(B).
- 시트 기본 = "지금 서울 통제": 통제 중 → 1시간 안 시작 → 오늘 → 내일. 지난 통제는 기본으로 안 보임.
- 과거·미래: 시간 슬라이더에 날짜 선택. `?t=` 공유 링크(3/15 07:45 마라톤)는 지금처럼 — 회귀 e2e. 카드는 `?event=<id>` 로도 열린다(B 알림 클릭).

**통제 구역 다각형 — 어디서 만드나**
| 안 | 어떻게 | 좋은 점 | 걸리는 점 |
|---|---|---|---|
| **BE 접수 때 (추천)** | 후보마다 횡단보도를 고른 모양 그대로 — 구간 = 도로 최단경로 + 등급 버퍼(대로 25·로 15·길 8 m), 선 15 m, 점 30 m — 를 사건 단위로 union → 5 m 단순화 → EPSG:4326 `area`(Polygon·MultiPolygon)·`centroid`. 새 표 `closure_events`(Alembic 0005) | "이 구역 안 횡단보도가 막힘"과 뜻이 같다. 공간 연산은 Python(CLAUDE.md §3-5). 읽기가 빠르고 ETag 가 쉽다 | 표 하나·마이그레이션. 접수 때 계산 |
| BE 읽을 때(점만) | 그 사건 횡단보도 점을 buffer → union → buffer-close | DB 변경 없음 | 구간 선이 없어 횡단보도 사이가 먼 곳(세종대로 100~300 m)은 끊긴 원들. 매 요청 계산 |
| FE(turf.js) | 브라우저에서 같은 계산 | BE 변경 없음 | 공간 연산은 Python 규칙 위반, 의존성 추가, 휴대폰 계산, BE·FE 모양이 어긋남 |

**성능 — 서울 전체 사건이 많을 때**
- 멀리·중간은 사건 단위만 그린다. 횡단보도 점은 가까이(줌 ≥ 15)에서 화면 bbox 로만 — 서울 전체 피처 318개(264 KB) 대신 사건 수십 개.
- 사건 API 기본 창 = 지금 진행 중 + 내일 24:00(KST)까지. 하루 수십 건(11/7 11건, 3/15 마라톤 16구간). 한 번에 최대 300건(심한 상태·시작 가까운 순, 넘으면 `truncated: true` 와 안내). bbox 는 선택 파라미터 — 서울 전체는 자르지 않는다.
- 다각형 5 m 단순화·좌표 소수 6자리. 목표: 서울 전체 응답 gzip 100 KB 미만, 300 사건 첫 렌더 1초 안(iPhone 13 크기 Playwright 측정). T7.4 에서 11/7·3/15 실데이터로 재고 보고한다.
- ETag 가 맞으면 304(본문 없음) → 60초 폴링은 대부분 공짜.

## B. PWA 알림
1. manifest·서비스워커·iOS 홈 화면 추가 안내. 알림 권한은 버튼으로만(앱 열 때 묻지 않는다).
2. 구독·관심 지역 API: VAPID, `POST /push/subscribe`, `/watch-areas` — saved(반경 300·500·1000 m), last_seen(약 150 m 격자로 반올림, 3시간 뒤 삭제). 계정 없음 — 구독 endpoint 가 손잡이.
3. 매칭: 새 통제(created)·통제 시작(confirmed) → impact blocks·확신도 ≥ 0.7 → 관심 지역과 STRtree(원 ↔ 사건 구역) → (구독, 사건, 종류)당 한 번. 22~07시 created 는 07시에 모아서.
4. 발송: pywebpush, 410·404 면 active=false. 서비스워커는 push 를 받으면 항상 showNotification.
5. 알림을 누르면 A 의 그 사건 카드가 열린 지도(`/?event=<id>&t=<시작>`).
- **발송 확인은 가짜 엔드포인트 없이** 운영(https://naru.antaewoo.com) 배포 뒤 태우 PC Chrome 과 폰(안드로이드 Chrome / iOS 16.4+ 홈 화면 앱)에서 실제 구독해서 한다: 관심 지역을 그날 실제 통제 근처에 두고 created·confirmed 알림이 오는지, 누르면 카드가 열리는지 — 보고에 시각·화면. `make check` 는 매칭·중복·조용한 시간을 기록된 사건과 기록된 지오코딩 점(광화문교보빌딩·덕수궁 대한문)으로만.

## Task 목록
| Task | 무엇 | 파일 | 실데이터 검증 | 의존 |
|---|---|---|---|---|
| T7.1 | BE 사건 API v2 — `GET /closures/events?at=&from=&to=(&bbox=)`: 사건 `id`(sha1(reason·시작·끝) 12자), `status`(t 기준 가장 심한), `confidence`(최대), 기본 창, 300건 상한, ETag/304. 파라미터 없으면 지금처럼 | contracts `closures_api.py`, `docs/INTERFACE.md` §3.1 v0.14, BE `closure_controller`·`closure_view`·`closure_repository`, `make schema`, 테스트, naru_api 재기록 | naru_test 에 11/7(공지 r01·r04·r06 + TOPIS 6300 + 돌발 11/7 15:40) → 11/7 15:30 사건 수·상태·id 가 재접수에도 같음·304. 3/15 07:45 마라톤 16구간 상태 | — |
| T7.2 | BE 통제 구역 — 접수 때 사건 `area`·`centroid`(위 추천안), 표 `closure_events`(0005) | BE `models/domain/event_area.py`, `entities/closure_event.py`, `migrations/0005`, `candidate_intake.py`, `closure_repository.py`, 테스트 | 3/15 1구간(세종대로 6곳)이 구역 안·폭 25 m, 11/7 TOPIS 6300 구간 셋, 11/9 국회대로 1109233(링크 선). 꼭짓점 수·응답 크기 보고 | T7.1 |
| T7.3 | TOPIS 통제지도 예정 통제 소스(T6.5) — 목록 AJAX `selectAccAllListASC`·통제 도로 `selectAccLinkList` 를 10분마다(ADR-011 E: robots 허용 경로·같은 곳 10분·NaruBot·원문 기록) → 예정(ingYn N) 통제를 후보로. 경로 = 링크 순서(꼭짓점은 OA-13311 LinkVerInfo·LinkBook), 전체·부분 통제(accRoadYn) → 전면 통제는 버스 기록 대상, 후보 ID = 돌발과 같은 acc_id | AI `ingest/topis_map.py`, 워커 소스, 테스트, `data/recorded/topis_web/` | T6.5 기록 `topis_web/20261109T083719_selectAccAllListASC.json`(6행 — 예정 3: 덕수궁길 행사·국회대로 1109233·강남대로 1109234), `…_selectAccLinkList_1109233.json`(19 링크 국회대로→…→효자로) → 후보 경로·횡단보도 수, 11/9 OA-13315 1109233 과 같은 ID 로 이어지는지 | T7.1, 정할 것 6 |
| T7.4 | FE 실시간 지도 — 앱 열면 서울 전체, 줌 3단계(클러스터·구역·횡단보도), 상태 5종 스타일, 칩 = 필터, 60초 ETag 갱신, data_as_of. "통제 불러오기"·빈 상태 삭제 | `api/naruApiClient.ts`(If-None-Match), `state/ClosureProvider.tsx`, `map/layers/eventLayer.ts`(순수), `map/MapView.tsx`, `components/LayerChips.tsx`, `map/colors.ts`, vitest·e2e | recorded naru_api 새 기록(사건 v2: 11/7 15:30·11/9 12:00·3/15 07:45) — 상태별 수·클러스터 색·줌 단계. 성능(사건 수·응답 크기·렌더 시간) 보고 | T7.1, T7.2 |
| T7.5 | FE 시트 — "지금 서울 통제" 목록, 사건 카드, 클러스터 목록, `?event=<id>` | `components/LiveSheet.tsx`·`EventCard.tsx`(+css), `ClosureSheet.tsx` 대체, `i18n/ko.ts`(남은 시간·해제 예정·출처·확신도 라벨), vitest·e2e | 같은 기록으로 순서·라벨("1시간 20분 뒤 시작" 등은 시각 고정 순수 함수), 실제 스택 e2e 로 카드·`?event=` | T7.4 |
| T7.6 | 시간 슬라이더 날짜 선택, 3/15 07:45 공유 링크 회귀, "이 구역 피해서 길찾기"(`/route?avoid=<id>`) | `TimeSlider.tsx`·`TimeProvider.tsx`·`RouteProvider.tsx`, BE `route_controller`·`RoutePlanner`, contracts `RouteQuery`, INTERFACE §2, `e2e/regressions.spec.ts` | 3/15 07:45 링크 → 마라톤 통제 중·지하보도 우회(지금 e2e 그대로), avoid=11/7 r04 → 세종대로 횡단보도를 안 지나는 길 | T7.5 |
| T7.7 | PWA 기반 — manifest, 서비스워커(push → 항상 showNotification, 클릭 → `/?event=`), iOS 안내, 권한 버튼 | `src/app/manifest.ts`, `public/sw.js`, `components/PushButton.tsx`·`InstallHint.tsx`, `src/push/usePush.ts`(Provider 추가 안 함), e2e | 실제 스택 Playwright(Chrome) 로 SW 등록·manifest, 태우 폰 홈 화면 추가 화면 | T7.5 |
| T7.8 | BE 구독·관심 지역 — `GET /push/vapid-public-key`, `POST·DELETE /push/subscribe`, `GET·POST·DELETE /watch-areas`, 표 셋(0006) | contracts `push.py`, INTERFACE §7, BE `push_controller`·`push_view`·`entities/push.py`·`push_repository`·`migrations/0006`·config(VAPID), 테스트 | 관심 지역 = 기록된 지오코딩 점(교보빌딩·대한문): 저장·150 m 격자·3시간 만료(시각 주입). 구독 입력 = 정할 것 12 | T7.7 |
| T7.9 | 매칭·발송 — created·confirmed 감지 → blocks·≥ 0.7 → STRtree → (구독, 사건, 종류) 한 번 → 22~07 created 는 07시 → pywebpush(410·404 → 끔). 워커 `push` 소스 60초 → `POST /internal/push/dispatch` | BE `models/domain/push_dispatcher.py`(순수)·`web_push.py`, internal 컨트롤러, AI 워커·publisher, 테스트 | 기록된 사건: 11/7 TOPIS 6300(05:00 통제 중)·돌발 집회, 교보빌딩 500 m 관심 지역 → 걸리는 사건·종류, created 23:00 → 07:00. 실제 발송은 태우 Chrome·폰(수동, 보고) | T7.2, T7.8 |
| T7.10 | 알림 → 카드, 카드 "☆ 이 근처 알림 받기"(중심 반경 500 m 기본), 관심 지역 목록·삭제, last_seen(내 위치 켰을 때만) | `EventCard.tsx`, `components/WatchAreas.tsx`, `usePush.ts`, `sw.js`, e2e | 운영 배포 뒤 태우 PC Chrome·폰 실제 구독으로 끝에서 끝(관심 지역 → 실제 통제 알림 → 눌러서 카드) | T7.9 |

- 모든 Task: 테스트 먼저(실데이터), `make check` 초록, 계층별 커밋 200줄 이하, 보고에 iPhone 13 스크린샷 1장(임시 스택 naru_test 5060/3060, 실제 앱).
- 일정: A 는 6 Task — 11/16 까지 하루 하나 꼴로 빠듯하다. 밀리면 T7.6 의 "피해서 길찾기"를 B 뒤로, T7.3 을 T7.6 뒤로 미룬다(정할 것 6·8).

## 계약·DB 변경 (→ ADR-014 초안)
- INTERFACE v0.14
  - §3.1 `GET /closures/events` 파라미터 `at`·`from`·`to`·`bbox`(없으면 지금처럼 전부). `ClosureEvent` 에 `id`, `status`, `confidence`, `area`(GeoJSON Polygon·MultiPolygon, 없으면 null), `centroid`([lng, lat], 없으면 null), 응답에 `truncated`. ETag·`If-None-Match` → 304.
  - §2 `GET /route` 에 `avoid`(사건 id, 쉼표로 여럿) — 그 사건 횡단보도를 시각·확신도와 상관없이 막힘.
  - §1 돌발 후보의 출처에 TOPIS 통제지도 예정 통제(같은 acc_id, T7.3) — 근거 종류는 정할 것 6.
  - §7(새) 알림: `GET /push/vapid-public-key`, `POST·DELETE /push/subscribe`, `GET·POST·DELETE /watch-areas`, `POST /internal/push/dispatch`(워커, 토큰).
- DB: 0005 `closure_events`(event_id PK, reason, window_start·end UTC, type, source, area GeoJSON, centroid lng·lat, crosswalks, updated_at) · 0006 `push_subscriptions`(endpoint 유일, p256dh, auth, active, created·last_ok) · `watch_areas`(subscription, kind saved·last_seen, lng·lat, radius_m, expires_at) · `push_sends`(subscription, event_id, kind created·confirmed, due_at, sent_at, http_status, 유일키 (subscription, event_id, kind)).
- 의존성: BE `pywebpush`(+ py-vapid·http-ece·cryptography) — ADR-006 스택 추가. FE 새 의존성 없음.
- 설정·비밀: `NARU_VAPID_PRIVATE_KEY`·`NARU_VAPID_PUBLIC_KEY`·`NARU_VAPID_SUBJECT`(.env, 태우), 워커 `NARU_PUSH_INTERVAL_S`(60).

## 태우가 정할 것 (선택지 · 추천)
1. 번호 — 기존 "P7 현장 실증(2027-03)"을 **P8 로 미룬다(추천)** / 새 계획을 P8 로.
2. 구역 다각형 — **BE 접수 때 `closure_events`(추천)** / BE 읽을 때 점만 / FE.
3. 사건 id — **sha1(reason·시작·끝) 12자(추천, 재접수에도 같음 — 공지 글이 고쳐지면 새 id)** / DB 일련번호.
4. 사건 API 기본 창 — **진행 중 + 내일 24:00(추천)** / 오늘만 / 48시간.
5. "1시간 안 시작" = 시작 60분 전부터, "오늘·내일" = KST 날짜 — 요청 그대로.
6. TOPIS 통제지도 예정 통제 — 근거: **예정 단계는 공지처럼(확신도 0.85, '통제 중'은 OA-13315 돌발이 와야 — 추천)** / topis_incident(시작 시각이 지나면 바로 통제 중). 출처 값: **incident 재사용(같은 acc_id 로 예정 → 통제 중이 이어짐, 추천)** / 새 값 `topis_map`(계약 enum 추가). 순서: **T7.3(추천)** / A 다 끝난 뒤.
7. T6.9 구 칩 — **"지금 서울 통제" 목록 위에 남김(추천)** / 뺌.
8. "이 구역 피해서 길찾기" — **`/route?avoid=` 로 그 사건을 무조건 막음(추천)** / 지금 라우터 규칙 그대로(확신도·시각).
9. 줌 경계 — **클러스터 < 12 · 구역 12~15 · 횡단보도 ≥ 15(추천, 스크린샷 보고 조정)**.
10. 발송 실행 — **워커 `push` 소스 60초 → `/internal/push/dispatch`(추천)** / BE 안 스레드(gunicorn 워커 2개라 중복 위험) / systemd 타이머.
11. VAPID 키 — 태우가 한 번 만든다(T7.8 보고에 명령 한 줄, `.env` 는 태우가 `!` 로).
12. 구독 테스트 입력 — **태우 실제 구독을 endpoint 토큰·키를 가린 채 `data/recorded/push/` 에 기록(추천 — 가짜 없이 저장·파싱 테스트, 가린 값이라 발송은 안 됨)** / 자동 테스트 없이 수동만.
13. 개인정보 — **last_seen 150 m 격자·3시간, saved 는 지울 때까지, 계정 없음 — 권한 버튼 옆 한 줄 + `/licenses` 에 절(추천)**.
14. iOS — **16.4+ 홈 화면 앱에서만 웹 푸시. Safari 브라우저면 "공유 → 홈 화면에 추가" 안내만(추천)**.
15. 확신도 0.7 미만 사건 — 지도에만 흐린 점선(요청). **칩 수·목록에서는 뺀다(추천)**.

## 메모
- 11/9 태우 README 커밋 둘(1963386·51e93cf)에 작업 중 코드가 같이 들어갔다. README 만 올릴 땐 `git commit README.md` 처럼 경로를 붙여 주면 섞이지 않는다.
- 승인 뒤: ROADMAP 에 P7(T7.1~T7.10) 블록·기존 P7 → P8, ADR-014 상태 → 승인, CONVENTIONS(FE 레이어·PWA)·ARCHITECTURE 반영 — 하네스 커밋 하나.
