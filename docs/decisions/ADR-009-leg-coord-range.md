# ADR-009 경로 레그가 선의 어디인지 — `legs[].coord_range`
- 상태: **승인** (2026-11-08, 태우) — "legs[]에 coord_range [i, j] (route.coordinates 인덱스, 양끝 포함) 추가로 간다"
- 개정 대상: INTERFACE v0.6 → **v0.7** §2, `naru_contracts.route.Leg`·`RouteResponse`, BE `TimeDependentRouter._build`·`route_view`, FE `map/layers/routeLayer.ts`
- 계기: T5.1 보고 — 시안 01 범례의 "지하보도 입구(파란 계단)"를 그릴 데이터가 계약에 없다

## 맥락
`GET /route` 응답(INTERFACE §2)의 `legs[]`는 `kind`·`name`·`distance_m`만 있어서, FE는 레그가 `route.coordinates`의 어느 부분인지 모른다. 그래서 지하보도 구간을 지도에 따로 칠할 수도, 지하보도 입구를 찍을 수도, LegList 의 행을 지도 위치와 잇지도 못한다.

선택지
1. 지하보도 입구 목록을 주는 별도 엔드포인트 — 도보망 오버레이(지하도·출입구)를 그대로 내보낸다. 경로와 상관없는 입구까지 나오고, 엔드포인트·계약이 하나 더 는다
2. 레그마다 LineString — 좌표가 두 번 실린다(route 와 legs). 응답이 커지고 둘이 어긋날 수 있다
3. **레그마다 `route.coordinates` 인덱스 범위** — 좌표는 한 번만, 레그는 범위만. 이것으로 간다 (태우)

## 결정
1. `Leg.coord_range: [i, j]` **필수**. `route.coordinates[i..j]`(양끝 포함)가 그 레그의 선이다
2. 레그는 경로를 **빈틈없이 나눈다**: 첫 레그 `i = 0`, 마지막 레그 `j = len(coordinates) - 1`, 이웃 레그는 경계 점 하나를 공유한다(`legs[k].j == legs[k+1].i`). `i ≤ j`. 레그가 없으면(출발·도착이 같은 노드 등) 규칙 없음
3. 출발점·도착점과 그래프 노드를 잇는 **접근 구간**(지금까지 `distance_m`에만 들어가고 어느 레그에도 없던 직선)은 `sidewalk` 레그로 셈한다 — 이웃 레그가 sidewalk면 합친다. 그래서 `Σ legs[].distance_m = distance_m`(반올림 차 1 m 안)
4. 위 1·2·3 은 `naru_contracts.RouteResponse` 검증기가 강제한다 — 어긋난 응답은 BE View 에서 터진다
5. FE: `kind ∈ {underpass, overpass}` 레그의 범위를 시안 02 의 "남색 터널"로 칠하고, 그 레그의 시작점 `coordinates[i]`에 입구 마커(시안 01 범례 "파란 계단")를 찍는다

## 근거
- 좌표 중복 없음, 응답 크기 거의 그대로(레그당 정수 두 개)
- 지하보도 입구가 "이 경로가 실제로 들어가는 입구"로만 나온다 — 홈 지도에 서울 전체 입구를 뿌리지 않는다
- LegList ↔ 지도 연동(T5.2)도 같은 범위로 된다
- 접근 구간을 레그에 넣으면 레그 합과 총거리가 맞는다. FE 가 레그별 시간·거리를 더해도 총합과 어긋나지 않는다

## 결과
- INTERFACE §2 예시·규칙 갱신(v0.7), `contracts.d.ts` 재생성(`make schema`)
- BE `_build`: 레그를 만들 때 인덱스를 채우고, 접근 구간을 sidewalk 레그로 넣는다. 레그 종류 순서는 그대로(첫·끝이 이미 sidewalk 인 경우가 대부분이라 합쳐진다), 첫·끝 레그의 `distance_m`만 접근 구간만큼 는다
- `data/recorded/naru_api/route_*.json` 다시 기록(`make record-naru-api`) — FE 테스트 입력
- 홈 지도에는 경로가 그려질 때(T5.2 RouteProvider) 지하보도 구간·입구가 함께 나온다
