---
name: real-data-testing
description: Naru의 테스트·개발 데이터 규칙. 테스트를 쓰거나, 데이터를 받거나, 외부 API를 호출하거나, fixture를 만들 때 반드시 따른다. 가짜 데이터는 어떤 형태로도 만들지 않는다.
---

# 실데이터 테스트

한 줄 원칙: **테스트가 실제 데이터 없이 통과하면 그 테스트는 틀린 것이다.**

## 1. 데이터를 구하는 순서
1. `data/MANIFEST.md`에 이미 있는가 → 그걸 쓴다.
2. 없으면 공개 데이터인가 → `scripts/fetch_<name>.py`를 만들어 `data/raw/`에 받고 MANIFEST에 항목 추가. 이 작업은 **별도 Task**다(ROADMAP P0 또는 T<n>.0으로 추가 제안). 현재 Task 안에서 슬쩍 받지 않는다.
3. API 응답이 필요한가 → `scripts/record_api.py --api <name>`으로 실제 호출을 기록해 `data/recorded/<name>/<ts>.json`에 저장. 쿼터를 확인하고 호출 수를 시작 메모에 적는다.
4. 위 셋 다 안 되면 **멈추고 태우에게 말한다.** 대체 데이터를 만들지 않는다.

## 2. MANIFEST 항목 형식
```
### seoul_crosswalks
- 파일: data/raw/seoul_crosswalks_20261105.csv
- 출처: https://data.seoul.go.kr/dataList/OA-23081/F/1/datasetView.do
- 수집일: 2026-11-05  스크립트: scripts/fetch_seoul_spatial.py
- 라이선스: 공공누리 1유형
- sha256: <값>
- 행 수: <값>  좌표계: WGS84 (확인 방법: 파일 열어 경도 126~127, 위도 37~38 범위 확인)
- 컬럼(실제): 자치구, 횡단보도관리번호, 교차로관리번호, 횡단보도종류, 보행신호등설치여부, 교차로명, X좌표, Y좌표  ← 파일에서 복사. 기억으로 쓰지 말 것
```

## 3. recorded 파일 형식 (스크립트가 자동 생성, 손으로 수정 금지)
```json
{
  "api": "seoul_bus_pos",
  "endpoint": "http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid",
  "params": {"busRouteId": "100100118"},
  "called_at": "2026-11-08T14:00:15+09:00",
  "status": 200,
  "raw": "<원문 응답 문자열 그대로>"
}
```
- 키·토큰은 `params`에서 제거하고 저장한다.
- 재생 시 `raw`를 그대로 파싱한다. 필드명은 재생 결과를 열어 확인한다.

## 4. 테스트 작성 패턴
```python
# packages/be/tests/conftest.py
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[3] / "data"

@pytest.fixture(scope="session")
def crosswalks_path() -> Path:
    p = DATA / "raw" / "seoul_crosswalks_20261105.csv"   # MANIFEST: seoul_crosswalks
    assert p.exists(), f"실데이터 없음: {p} — scripts/fetch_seoul_spatial.py 먼저 실행"
    return p
```
- 없으면 `assert`로 **실패**. `pytest.skip` 금지.
- 기대값엔 확인 주석:
```python
# data/raw/seoul_crosswalks_20261105.csv 에서 교차로명 == '세종대로사거리' 필터 → 4행 (2026-11-05 확인)
assert len(ids) == 4
```
- API 테스트: 키가 있으면 live(호출 수 상한 명시), 없으면 recorded 재생. 분기는 fixture 하나에서만.
```python
@pytest.fixture
def bus_response(recorded_latest):
    if os.getenv("DATA_GO_KR_KEY"):
        return call_live(max_calls=1)      # 쿼터 소모 1회
    return recorded_latest("seoul_bus_pos")  # 가장 최근 기록
```
- DB는 docker compose의 실제 MySQL, 스키마 `naru_test`. 테스트 후 픽스처가 테이블을 `TRUNCATE`. SQLite로 대체 금지.

## 4.1 BE (MVC) 계층별 테스트
| 계층 | 방법 | 입력 |
|---|---|---|
| Model | Flask 없이 순수 파이썬. **테스트 대부분이 여기** | `data/raw/`, `data/recorded/candidates/`, `from_segment`는 표준노드링크 |
| View | Model을 실데이터로 돌린 **실제 출력** → `render()` → 응답이 contracts로 `model_validate` | Model 테스트 픽스처 재사용 |
| Controller | `create_app(test_settings).test_client()` — 실제 앱 인프로세스. 400/401 경로 포함 | 실데이터 + recorded 후보 |
- View 테스트에서 도메인 객체를 손으로 만들지 않는다. 반드시 Model을 실데이터로 실행한 결과를 쓴다.
- Controller·Model·View 어느 것도 patch하지 않는다.

## 4.2 AI ↔ BE 경계
- BE 테스트는 `naru_ai`를 import할 수 없다(`.importlinter`). AI가 만든 후보가 필요하면 `scripts/record_candidates.py --source <s>`로 **실제 AI 실행 결과**를 `data/recorded/candidates/<source>/<ts>.json`에 저장해 쓴다.
- `CandidatePublisher`(AI)와 `NaruApiClient`(FE)처럼 경계를 넘는 HTTP 클라이언트는 단위 테스트하지 않는다. `make dev` e2e에서 실제 상대로만.

## 4.3 LLM 테스트 (Claude API, ADR-007)
- `make record-llm`이 실제 공지 문장을 호출해 `data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json`에 요청(system·messages·input_schema)·원문 응답·usage를 저장한다. 키는 저장하지 않는다.
- 테스트는 recorded 재생만. recorded의 `model`·`prompt_version`이 현재 설정과 다르면 **fail**. live는 `make record-llm`에서만, 상한(`LIMIT`)을 시작 메모에 적는다.
- `FakeLLM`, `EchoClient`, 고정 문자열 클라이언트 금지. 클라이언트는 `AnthropicClient` 하나.
- 정확도 기대값은 `docs/eval/`의 실제 결과 표에서만. 테스트에 val 숫자를 박지 않는다(train 문장 기준값만).
- 리졸버: 카카오 응답은 `data/recorded/kakao/<kind>/<sha1(canonical)>.json`에 기록·재생. 추측 좌표 금지 — 못 찾으면 `None`이고 테스트는 그걸 확인한다.

## 4.4 FE 테스트 (Next.js)
- 입력은 `data/recorded/naru_api/<endpoint>/<ts>.json` — `scripts/record_naru_api.py`가 로컬 실제 Flask에서 기록한 것.
- 순수 함수(레이어 변환·reducer·라벨)와, Provider 초기 state에 recorded를 넣은 **클라이언트 컴포넌트** 렌더 테스트만. fetch를 가로채지 않는다.
- Server Component(`layout`, `page`)와 `NaruApiClient`·rewrites는 Playwright e2e(`make dev`: Flask + `next dev`)에서만.
```ts
// packages/fe/src/map/layers/closureLayer.test.ts
import closuresAtPeak from "../../../../../data/recorded/naru_api/closures/20270321-090000.json";
// ↑ scripts/record_naru_api.py, 통제 중 시각 (MANIFEST: naru_api)
test("confirmed 횡단보도는 빨강", () => {
  const src = toClosureSource(closuresAtPeak);
  expect(src.data.features.filter(f => f.properties.status === "confirmed").length)
    .toBe(closuresAtPeak.features.filter(f => f.properties.status === "confirmed").length);
});
```

## 5. 금지 목록 (`harness/gates/check_no_fakes.sh`가 grep)
- Python: `unittest.mock`, `MagicMock`, `monkeypatch`, `respx`, `import responses`, `import vcr`, `httpretty`, `faker`, `Faker(`
- FE: `msw`, `vi.mock`, `vi.fn`, `vi.spyOn`, `jest.`, `nock`, `sinon`
- 공통: `fake`, `dummy`, `stub`, `mock`, `sample_`, `pytest.skip`, `mark.skip`, `xfail`, `test.skip`, `it.skip`, `describe.skip`
- 변수명·파일명·주석까지 포함해서 검사한다. 우회(철자 바꾸기)도 금지.
- 정말 필요하다고 생각되면 코드를 쓰지 말고 태우에게 "왜 실데이터로 안 되는지"를 설명한다. 대부분은 데이터를 더 받으면 된다.

## 6. 허용되는 유일한 상수 데이터
순수 수학 함수(haversine, bearing, 버퍼 폭 변환)의 단위 테스트는 실데이터에서 뽑은 좌표를 상수로 써도 된다. 출처 주석 필수:
```python
# 광화문광장 세종대왕상 — data/raw/seoul_rtd_places.json 'POI001' 중심 (2026-11-05)
GWANGHWAMUN = (126.9769, 37.5725)
```
