# ADR-008 공지 파서 v2 출력(impact·toward·approx)을 BE가 어떻게 받는가 — 초안
- 상태: **제안** (2026-11-07, Claude 초안 → 태우 승인 대기). 승인 전에는 `naru_contracts`·INTERFACE를 바꾸지 않는다
- 근거 문서: `docs/data/notice_parser_rules_v2.md` §9.1(출력 스키마), §9.2 4·8·12(뒤 단계 = BE 규칙)
- 개정 대상: INTERFACE v0.5 → **v0.6** (아래 변경 목록), ARCHITECTURE "ClosureState 상태기계" 표 비고 한 줄, `naru_be/config.py` 상수 3개

## 맥락
파서 규칙서 v2는 `scope`를 `impact(blocks|none|unknown)`로 바꾸고, 한 입력에 `items[]` 여러 건을 낸다. 그중 세 규칙은 파서가 아니라 뒤 단계(AI CandidateBuilder → BE)가 해야 할 일이라고 명시한다.

| 규칙 | 파서가 내는 것 | 뒤 단계가 해야 할 것 |
|---|---|---|
| §9.2-4 종료 지점 없는 행진 | `segments []`, `points [출발지]`, `toward: "을지로입구역"`(문장 그대로), −0.15 | toward가 지명사전에 있으면 출발지→toward 선을 **낮은 확신**으로, 없으면 출발지 주변 구역 |
| §9.2-8 근사 시간("14시경", "오후") | 양끝 10분 넓힌 window, `approx: true`, −0.10 | 그대로 쓰되 "근사"임을 끝까지 전달(FE 표시·평가 ±10분) |
| §9.2-12 점유 표현 없는 지점 집회 | `impact: unknown`, `points` 필수, confidence 0.45 | 지점이 **도로 30 m 안**이거나 지점들이 도로를 감싸면 막는 것으로 본다 |

지금 계약(v0.5)에는 impact·toward·approx 칸이 없어 이 정보가 AI에서 BE로 넘어오지 못한다.

## 결정 (제안)
1. **`impact`는 ClosureCandidate에 싣는다. 값은 `blocks | unknown` 둘.** 파서의 `none`(자동차전용도로·차 없는 거리·보도·차량 조치·해제·안내)은 AI CandidateBuilder가 **후보를 만들지 않는다** — 단, `impact_reason: released`(해제 공지)는 후보 대신 `release` 신호로 BE에 보낸다(이건 별도 ADR, 지금은 범위 밖). 코스·돌발·버스 producer는 항상 `blocks`.
2. **`impact: unknown` 후보의 기하 승격 (§9.2-12, BE `CandidateIntake`)**: `PointGeom` 후보에 대해 RoadGraph에서 가장 가까운 도로 링크까지 거리를 잰다.
   - ≤ **30 m**(`unknown_impact_road_m`, config): `blocks`로 승격해 보통 후보처럼 `CrosswalkIndex.from_point(30 m)` → `scheduled`. 승격 사실을 evidence(`detail.rule: "unknown_near_road"`, 거리)에 남긴다.
   - 같은 공지의 `points`가 둘 이상이고 그 점들의 볼록껍질이 도로 링크와 겹치면(지점들이 도로를 감쌈) 같은 승격.
   - 그 밖에는 `zone_scheduled`(표시만, 라우팅 무관)로 적재. 횡단보도 상태를 만들지 않는다.
   - confidence는 파서 값(0.45)을 그대로 두므로 `review_required: true` → INTERFACE §1 규칙대로 "적재하되 라우팅엔 안 쓴다". 승격은 **라우팅 제외를 풀지 않는다**; 사람이 검토 큐에서 올리거나 실측(돌발·버스)이 와야 0.8 이상이 된다.
3. **`toward` (§9.2-4)**: AI `Resolver`가 `toward` 이름을 지명사전으로 풀어 보고,
   - 풀리면 CandidateBuilder가 `SegmentGeom(from_=출발지, to=toward, via=[], road=null)`을 만들고 **confidence를 `toward_confidence_cap`(0.65)로 상한**해 `review_required: true`로 보낸다. BE는 보통 segment처럼 `from_segment`로 선을 긋고 적재하되 라우팅엔 안 쓴다("낮은 확신" = 검토 큐).
   - 안 풀리면 출발지 `PointGeom`만 보낸다(`toward`는 문자열로 그대로 실림). BE는 §9.2-12와 같이 30 m 규칙 → 아니면 `zone_scheduled`.
   - `toward` 문자열은 ClosureCandidate에 그대로 실어 EvidencePopover가 "→ 을지로입구역 방향"을 보여 줄 수 있게 한다.
4. **`approx` (§9.2-8)**: ClosureCandidate에 `approx: bool`을 싣고 `ClosureState`·`/closures` Feature properties·`/route` avoided에도 그대로 전달한다. BE는 window를 **넓히지도 좁히지도 않는다**(파서가 이미 ±10분). 상태기계 전이 시각(start/end+30분)도 그 window 그대로. FE는 "약 14:00~16:00"처럼 표시. 평가(T4.3)는 `approx` 케이스에 ±10분 허용.
5. **ClosureEngine**: `impact: unknown`이 승격되지 않은 후보는 `zone_scheduled`로 낸다. 그 외 전이 규칙은 ADR-007·T2.3 그대로.

## INTERFACE v0.6 변경 목록 (승인 후 문서 → `naru_contracts` → `make schema` 순으로)
| § | 변경 | 코드 |
|---|---|---|
| §1 `ClosureCandidate` | `impact: "blocks" \| "unknown"` **필수** | `ClosureCandidate.impact: Impact` (StrEnum `Impact`: blocks, unknown) |
| §1 `ClosureCandidate` | `toward: string \| null` (기본 null). 문장에 있던 방향 표현 그대로. `geometry.kind=point`일 때만 의미 | `toward: str \| None = None` |
| §1 `ClosureCandidate` | `approx: boolean` (기본 false) | `approx: bool = False` |
| §1 규칙 | `impact: unknown`이면 `confidence ≤ 0.65`(review_required 강제). `toward`가 있으면 `geometry.kind ∈ {point, segment}` | `model_validator` 추가 |
| §1 예시 JSON | `"impact": "blocks", "toward": null, "approx": false` 추가 | `test_interface_examples.py` 갱신 |
| §1 표 (kind별 BE 처리) | `point` 행에 "impact unknown이면 도로 30 m 규칙(ADR-008) 뒤 from_point" | — |
| §2 `/route` `avoided[]` | `approx: boolean` 추가 | `Avoided.approx: bool = False` |
| §3 `/closures` properties | `approx: boolean` 추가, `impact` 추가(`blocks \| unknown`) | `FeatureProperties.approx`, `.impact` |
| `ClosureState` | `approx: bool = False`, `impact: Impact = blocks` | `ClosureState` |
| §4 enum | `impact` 행: `blocks · unknown` (FE 라벨 "통제 · 미확인") | `enums.Impact` |
| §4 enum | `evidence[].kind`에 변화 없음. `detail.rule`에 `unknown_near_road`, `toward_resolved`, `toward_unresolved` 문자열 | — |
| 변경 이력 | 2026-11-xx v0.6 — ADR-008 | — |
| `naru_be/config.py` | `unknown_impact_road_m = 30.0`, `toward_confidence_cap = 0.65`, (`approx`는 상수 없음) | — |
| FE | `make schema` 재생성, `i18n/ko.ts`에 `impact` 라벨, `EvidencePopover`에 toward·approx | T5.x |

하위호환: `impact`를 필수로 두면 기존 기록(`data/recorded/candidates/course/*.json`)은 다시 만든다(`make record-candidates SOURCE=course` — CourseIngestor가 `impact: blocks`를 넣도록 한 줄). 기본값을 두면 재기록 없이도 열리지만 "AI가 impact를 안 적어도 통과"가 돼서 **필수**를 제안한다.

## 이유
- 파서는 좌표·도로를 모른다는 원칙(ADR-003·007)을 지키면서 "종료 없는 행진"·"점유 표현 없는 지점"을 버리지 않는 유일한 길이 뒤 단계 규칙이다. 규칙은 전부 config 상수라 PC-4 평가 뒤 바꿀 수 있다.
- 30 m는 CrosswalkIndex `point_radius_m`와 같은 값으로 맞췄다(한 지점 집회가 막는 횡단보도 반경과 같은 스케일). 지점이 도로에서 30 m보다 멀면 광장·공원 집회다.
- 0.65 상한은 review 임계값(0.7) 바로 아래 — 자동 라우팅에는 절대 안 들어가고, 지도에는 노랑 점으로 보인다.
- `impact: none`을 BE까지 보내지 않는 건 INTERFACE §1 "틀린 선보다 빠진 점이 낫다"와 같은 방향. 단 `released`는 해제 신호라 버리면 안 되므로 후속 ADR로 남긴다.

## 결과 — 이 선택 때문에 바뀌는 것
- T4.2 CandidateBuilder: items 순회, `impact none` 제외, `toward` 리졸브, confidence 상한.
- T3.4 CandidateIntake: `impact unknown` 30 m 규칙(RoadGraph 최근접 링크 거리). `RoadGraph.nearest_link_distance_m(lng, lat)` 메서드 추가(T1.2 코드에 +15줄).
- T2.3 ClosureEngine: `zone_scheduled` 분기 하나.
- T2.1 테스트·`contracts.d.ts` 재생성, course 후보 재기록.

## 열린 질문 (태우)
1. `impact: none/released`(해제 공지)를 후보 대신 어떤 형태로 BE에 보낼지 — 별도 ADR로 미룰지, 지금 같이 정할지.
2. `impact`를 필수로 할지 기본값(`blocks`)을 둘지.
3. 30 m·0.65 값.
