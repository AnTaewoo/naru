# ADR-012 통제 목록 — 파서 요약·공지 원문·데이터 기준 시각을 사건까지
- 상태: **승인** (2026-11-08, 태우 — "ADR-012 1번으로 승인", 조건 둘: ① summary 는 문장이 아니라 구조화된 칸만(구간 from/to 이름, 지점 이름, reported_people 숫자, road). 파서가 이미 낸 정규 이름(spans canonical)을 그대로 쓰고, 이걸 위해 Claude 출력 스키마를 늘리지 않는다 ② 제목·둘째 줄 문장은 FE 가 i18n/ko.ts 템플릿으로 만든다. "5만 명" 같은 숫자 표기도 FE)
- 개정 대상: INTERFACE §1(`ClosureCandidate.summary`)·§3.1(`ClosureEvent.type·source·summary·notice`, 응답 `data_as_of`), BE `closure_states` 열 4개(Alembic), AI CandidateBuilder
- 관련: ADR-011 C(`data_as_of` 승인 — 이 ADR 이 뜻을 정한다), ROADMAP T5.9

## 맥락
- `/closures/events` 의 사건 제목(`reason`)은 공지 원문 그대로다: "15:00~16:00 시의회~숭례문R → 광화문·고용노동청 <태평로 등> 50,000명 중부, 종로, 남대문". 태우 T5.9: 제목은 파서 결과로 "시의회~숭례문오거리 집회 → 광화문·고용노동청 행진", 둘째 줄 "5만 명 · 태평로", 원문은 상세의 "공지 원문 보기"
- 파서(notice_v2)는 item 마다 segments(from·to 정규 이름)·points·reported_people·road_hints 를 낸다(recorded 응답 smpa-20261107-r04 로 확인). 그런데 후보 계약(§1)에 칸이 없어 BE 까지 오지 않는다. 좌표가 안 풀린 이름(예: "시의회")은 geometry 에서도 빠진다
- `data_as_of`(ADR-011 C)는 출처별 시각인데 `closure_states` 에 출처(source)가 없다

## 결정 (초안)
1. §1 `ClosureCandidate.summary`(선택) = `{"segments": [{"from_": "시의회", "to": "숭례문오거리", "via": []}, {"from_": "숭례문오거리", "to": "광화문", "via": []}, {"from_": "숭례문오거리", "to": "고용노동청", "via": []}], "points": [], "reported_people": 50000, "roads": ["태평로"]}` — 구조화된 칸만(문장 없음). 파서 item 의 segments(from_·to·via)·points 이름은 spans 정규 이름(canonical) 그대로, roads 는 road_hints 와 구간 road 의 정규 이름, reported_people 은 숫자 그대로. 좌표가 안 풀린 이름(예: "시의회")도 남는다. Claude 출력 스키마는 그대로. 같은 item 의 후보는 같은 summary. 시각표(코스) 후보는 null
2. BE `closure_states` 에 `source`·`type`·`summary`(JSON)·`notice`(JSON: excerpt·source_url·published_at) 열을 더한다. 상태를 만들 때 후보 값을 그대로 넣는다 (Alembic, 기존 행은 재수집으로 채움)
3. §3.1 `ClosureEvent` 에 `type`(enum)·`source`(enum)·`summary`(null 가능)·`notice`(null 가능) 를 더한다. 응답에 `data_as_of` = `{"topis_incident", "topis_notice", "smpa", "course"}` 각 ISO 시각 또는 null — 그 출처로 저장된 통제의 가장 늦은 근거 시각: 공지(smpa·topis_notice)는 게시 시각, course 는 시각표 게시 시각, topis_incident 는 돌발 수신 시각(T6.1 전까지 null)
4. 제목·둘째 줄은 FE 가 `i18n/ko.ts` 템플릿으로 만든다(한국어·숫자 표기는 FE 에서만): route 첫 구간 "A~B", 그 끝에서 이어지는 구간들 "→ C·D" — 이어지는 구간이 있으면 "A~B 집회 → C·D 행진", 없으면 "A~B {종류}". points 만 있으면 "소녀상 앞 집회". 둘째 줄은 인원("5만 명" — 만 단위는 FE 가 정함) · 도로("태평로"). summary 가 없으면(마라톤 등) 지금처럼 reason
5. "공지 원문 보기"는 사건 상세에서 누를 때만 `notice.excerpt` 와 게시 시각·출처 링크를 보인다 — 목록·통제 근거에는 출처를 쓰지 않는다(태우 2026-11-08)

## 근거
- 이름·인원·도로는 이미 파서가 뽑았다 — 버리지 말고 전달만 하면 된다. 원문을 다시 규칙으로 쪼개면 같은 일을 두 번 하고 틀린다
- 화면 문구(집회·행진·만 명)는 FE i18n 에만 둔다(CLAUDE.md §3-7)
- data_as_of 는 출처를 알아야 정할 수 있다

## 결과
- T5.9: INTERFACE v0.12, contracts, AI CandidateBuilder, BE 엔티티·Alembic·Repository·View, recorded 재기록(record-candidates notice·record-naru-api), FE 목록
