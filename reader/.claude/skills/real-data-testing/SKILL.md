---
name: real-data-testing
description: notice-ner의 데이터·테스트 규칙. 테스트를 쓰거나, 데이터를 받거나, API를 호출하거나, 라벨·분할을 다루거나, fixture를 만들 때 반드시 따른다. 가짜·합성 데이터는 어떤 형태로도 만들지 않는다.
---

# 실데이터 테스트 (연구판)

한 줄 원칙: **테스트가 실제 데이터 없이 통과하면 틀린 테스트다. 실험 숫자가 실제 문장과 사람 라벨 없이 나오면 틀린 숫자다.**

## 1. 데이터를 구하는 순서
1. `data/MANIFEST.md`에 있나 → 그걸 쓴다
2. 공개 데이터인가 → 수집 CLI(`cli/fetch_<name>.py`)로 `data/raw/`에 받고 MANIFEST 항목 추가. **별도 데이터 Task**다. 지금 Task 안에서 슬쩍 받지 않는다
3. API 응답이 필요한가 → `make record API=<name>`으로 실제 호출을 기록하고 재생. 호출 수를 PLAN에
4. 정답이 필요한가 → 사람이 Label Studio에서 단다 → `make export`. Claude가 정답을 쓰지 않는다
5. 다 안 되면 **멈추고 태우에게 말한다.** 대체물을 만들지 않는다

## 2. MANIFEST 항목
```
### naver_news_index
- 파일: data/raw/naver/<run_ts>/ (페이지 파일 N개)
- 출처: <실제 엔드포인트>   쿼리: configs/collect_queries.yaml @ <commit>
- 수집일: YYYY-MM-DD   명령: make fetch SRC=naver
- 라이선스·조건: 네이버 검색 API 이용약관
- sha256: <값>  (디렉터리는 "정렬된 파일 경로 + 각 sha256"의 sha256 — 계산 규칙은 tests/test_manifest.py)
- 행 수: <값>
- 필드(실제): ← 파일을 열어 복사. 기억으로 쓰지 않는다
```
`tests/test_manifest.py`가 모든 항목의 파일 존재·sha256·행 수를 검사한다. 원천을 고치면 `make check`가 깨진다.

## 3. recorded 형식 (기록기가 만든다, 손으로 고치지 않는다)
```json
{
  "api": "naver_news",
  "endpoint": "<실제 URL>",
  "params": {"query": "교통통제", "display": 100, "start": 1, "sort": "date"},
  "called_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "status": 200,
  "raw": "<원문 응답 문자열 그대로>"
}
```
- 키·토큰은 params·headers에서 지우고 저장
- LLM 기록엔 추가로 `provider`, `model`, `revision`(로컬) 또는 `"api"`, `prompt_version`, `request`(system·messages·tool schema 전부), `usage`
- 재생할 땐 `raw`를 그대로 파싱한다. 필드명은 재생 결과를 열어 확인한다

## 4. 테스트 패턴
```python
# tests/conftest.py
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[1] / "data"

@pytest.fixture(scope="session")
def train_split() -> Path:
    p = DATA / "splits" / "v1" / "train.jsonl"          # SPLIT.md v1
    assert p.exists(), f"실데이터 없음: {p} — make split 먼저"
    return p
```
- 없으면 `assert`로 **실패**. `pytest.skip` 금지
- 기대값엔 확인 주석:
```python
# data/gazetteer/intersections.parquet 에서 canonical_name에 '세종' 포함 → 7행 (2026-11-08 확인)
assert len(hits) == 7
```
- 분할을 쓰는 테스트는 `train`·`val`만 `load_split`. 봉인 분할은 `load_split_meta`(id·날짜·dedupe 그룹)로만 검사
- API: 키가 있으면 live(상한 명시), 없으면 recorded. 분기는 fixture 하나에서만
- GPU가 필요한 테스트: `@pytest.mark.gpu` (`make check-gpu`에서 돈다. 건너뛰기가 아니라 분리다)

## 5. 라벨·분할
- `data/labeled/`, `data/splits/`는 명령 출력만. 테스트도 이 파일을 고치지 않는다 (읽기만)
- export 검증이 실패하면 테스트가 실패해야 한다. 데이터를 고쳐서 통과시키지 않는다 → `labeling/issues.md` → 사람이 Label Studio에서 수정 → 재export
- 사전 주석은 train만, 규칙만 (`.importlinter`)
- 규칙 시스템의 규칙마다 근거 train `sentence_id` 주석

## 6. 모델·LLM 테스트
- 학습 코드: 실제 train 문장으로 스팬 ↔ BIO 정렬 왕복, 출력 schema·오프셋, `gpu` 스모크(실제 train 몇 step 후 loss 감소)
- LLM: recorded 재생. recorded의 `provider`·`model`·`prompt_version`이 현재 config와 다르면 **fail** — 다른 모델 결과로 통과하는 걸 막는다
- `FakeLLM`, `EchoClient`, 고정 문자열을 돌려주는 클라이언트 금지. 클라이언트는 실제 제공자뿐
- 테스트에서 지표 숫자를 기대값으로 고정할 땐 train 데이터로만 (val·test 숫자를 테스트에 박으면 그 숫자에 맞춰 코드를 고치게 된다)

## 7. 금지 목록 (`scripts/check_no_fakes.sh`가 대소문자 무시로 찾는다)
- 모킹: `unittest.mock`, `MagicMock`, `monkeypatch`, `respx`, `import responses`, `import vcr`, `httpretty`
- 가짜: `faker`, `Faker(`, 이름의 `fake` `dummy` `stub` `mock`
- 건너뛰기: `pytest.skip`, `mark.skip`, `xfail`
- 합성·증강: `synthetic`, `augment`, `paraphras`, `back_translat`
- 변수명·파일명·주석까지 검사한다. 철자를 바꿔 피하는 것도 금지
- 정말 필요해 보이면 코드를 쓰지 말고 태우에게 "왜 실데이터로 안 되는지"를 설명한다. 대부분은 데이터를 더 받으면 된다

## 8. 허용되는 상수
순수 함수(거리, ISO 구간 파싱, 5-gram Jaccard, BIO 변환)의 단위 테스트는 실데이터에서 뽑은 값을 상수로 써도 된다. train에서만, 출처 주석 필수:
```python
# data/splits/v1/train.jsonl sentence_id=<id> 의 text 그대로 (2026-11-12)
TEXT = "…"
```
