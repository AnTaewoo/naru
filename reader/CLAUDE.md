# CLAUDE.md — notice-ner (Naru 통제 공지 파싱 실측)

이 저장소는 **실측 연구**다. 제품 코드가 아니다. 답할 질문은 하나다.

> 통제 공지 문장에서 시간·장소를 뽑아 정규화하는 일을, **로컬 소형 모델 + 사후학습**이 **Claude API(few-shot)** 만큼 하는가? 차이가 있다면 어디서 얼마나 나고, 비용·지연은 얼마인가?

결과(`reports/report.md`)는 Naru `docs/decisions/ADR-007-llm.md`의 근거가 된다. **결론을 미리 정하지 않는다.** 로컬이 지면 진 대로 쓴다.

- 과제 정의 `docs/PROBLEM.md` · 실험 규칙 `docs/experiments.md` · 라벨 규칙 `docs/labeling_guide.md`. 이 셋과 충돌하는 구현은 하지 않는다. 바꾸려면 `docs/decisions/`에 ADR 초안 → 태우 승인.
- 이 저장소에는 구현 코드가 없다. 게이트(금지어 검사·import 계약·권한)와 문서만 있다. 코드는 ROADMAP Task마다 태우와 같이 쓴다.
- 이 파일은 `.claude/skills/*/SKILL.md`보다 우선한다. 스킬은 절차, 이 파일은 원칙.

---

## 1. 태우가 운전한다 (최우선)

목적은 숫자만이 아니다. 태우가 수집부터 평가까지 전부를 이해하고 손으로 고칠 수 있게 되는 것이다.

1. **한 번에 Task 하나.** `ROADMAP.md`에서 `status: GO`인 Task만. GO·DONE은 태우만 쓴다. GO가 없으면 "다음은 R?.?입니다. GO 주시면 PLAN부터 씁니다"라고 하고 멈춘다.
2. **코드 전에 PLAN.** `docs/walkthrough/<task-id>.md`에 PLAN(15줄 이내)을 쓰고 태우 `ok` 전엔 `src/`·`tests/`·`configs/`를 건드리지 않는다. 🧪 실험 Task는 PLAN 아래에 **사전 등록**(가설·주지표·기대 범위·판정 규칙)을 쓴다.
3. **Red → Green → Refactor → Gate.** 단계마다 멈추고 5줄 이내로 보고. 커밋당 변경 200줄 이하(테스트 포함). 넘을 것 같으면 쪼개자고 제안.
4. **Task 끝엔 READ-ALONG + QUIZ 3문제** (🧪는 + RESULT). 채점까지 끝나면 `REVIEW`. `DONE`은 태우.
5. **서브에이전트·병렬·백그라운드 금지.** 학습처럼 오래 도는 건 포그라운드로, 예상 시간과 로그 경로를 먼저 말한다. 파일 하나 만들 때마다 왜 필요한지 한 줄.
6. **선택지가 둘 이상이면 묻는다.** 하이퍼파라미터, 임계값, 라이브러리, 분할 경계 — 추천안과 이유를 붙여 한 번에 하나씩.
7. **확인할 수 있는 건 열어 보고 말한다.** 컬럼명, API 응답 필드, Label Studio export 구조, 모델 카드 라이선스, 가격. 기억으로 쓰지 않는다.
8. **사람 Task는 대신하지 않는다.** 라벨링, 로그인이 필요한 다운로드, 키 발급, ADR 승인, `make freeze`. Claude는 체크리스트와 진행률 도구까지만.

## 2. 데이터 원칙 (절대)

### 2.1 허용되는 데이터는 셋뿐

| 종류 | 위치 | 규칙 |
|---|---|---|
| 공개·수집 원천 | `data/raw/` | 수집 CLI(`python -m notice_ner.cli.fetch_*`)로 받는다. 로그인이 필요한 곳만 태우가 직접 받는다(§4). `data/MANIFEST.md`에 출처 URL·수집일·sha256·라이선스·행 수. 받은 뒤 수정 금지 |
| 실제 API 응답 | `data/recorded/<api>/<YYYYMMDD-HHMMSS>.json` | 요청 파라미터(키 제거)·호출 시각·원문 응답 그대로. 손 편집 금지. 테스트는 키가 있으면 live(호출 수 상한 명시), 없으면 재생 |
| 사람 라벨 | `data/labeled/` | Label Studio export를 변환만 한 것. `ANNOTATORS`에 있는 사람이 단 라벨만 |

파생물(`data/interim/`, `data/splits/`, `data/gazetteer/`)은 위 셋에서 명령 하나로 다시 만들 수 있어야 한다.

### 2.2 금지 — 하나라도 있으면 `make check` 실패 (`scripts/check_no_fakes.sh`)
- 모킹: `unittest.mock`, `MagicMock`, `monkeypatch`, `respx`, `responses`, `vcr`, `httpretty`
- 가짜: `faker`, 임의 좌표, 손으로 친 공지 문장, 파일·심볼 이름에 `fake`·`dummy`·`stub`·`mock`
- 건너뛰기: `pytest.skip`, `mark.skip`, `xfail`. 데이터가 없으면 **실패**해야 한다
- **합성·증강 (v0 전부)**: LLM 생성·패러프레이즈·역번역·템플릿 문장. 학습·평가 입력은 수집한 실제 문장뿐. 바꾸려면 ADR-R03
- **LLM이 만든 라벨 (v0)**: 교사 라벨·자동 라벨을 정답이나 학습 데이터로 쓰지 않는다. ADR-R03

### 2.3 정답 보호
- 정답(스팬·정규형)은 **사람만** 쓴다. Claude는 `data/labeled/`·`data/splits/`를 손으로 만들거나 고치지 않는다. export·split 명령의 출력만 거기 들어간다 (`.claude/settings.json`이 Edit을 거부한다).
- 라벨 오류를 찾으면 `labeling/issues.md`에 적는다. 주석자가 Label Studio에서 고치고 재export → `data_version`을 올린다.
- **사전 주석(pre-annotation)은 train 기간 문장에만, 지명사전+정규식으로만.** LLM·학습 모델로 사전 주석 금지 (`.importlinter`). val·test·test_ood는 빈 화면에서 단다. 이유: 주석자는 제안을 받아들이는 쪽으로 기운다. 어떤 시스템의 출력을 보여 주고 단 정답은 그 시스템 점수를 부풀린다.
- 규칙 시스템(exp001, 정규화기)의 규칙은 **train 문장을 근거로** 만든다. 규칙 옆 주석에 근거 `sentence_id`.

### 2.4 기대값 주석
테스트 기대값은 데이터를 열어 확인한 값만 쓰고, 옆에 확인 방법을 단다.
`# data/raw/klue_ner/ — datasets 로드 결과 train 21,008행 (2026-11-06 확인)`

## 3. 실험 원칙

1. **사전 등록.** 🧪 Task PLAN 아래에 가설·주지표·기대 범위(val)·판정 규칙을 실행 전에 쓰고 커밋한다. 실행 후 고치지 않는다. 틀렸으면 RESULT에 틀렸다고 쓴다.
2. **튜닝·선택·오류 분석은 val로만.** test·test_ood는 R4.7에서 모든 실험을 한꺼번에, 실험당 1회.
3. **봉인.** test·test_ood 기간 문장은 `data/interim/<ver>/sealed/`, 라벨은 `data/splits/<ver>/sealed/`에 있다. 여는 코드는 `notice_ner.eval`의 test 모드뿐이고 `make test-run`만 연다. **Claude는 sealed 경로와 test 산출물(`predictions_test*`, `errors_test*`)을 어떤 방법으로도 열지 않는다 — Read 도구, `cat`, `python -c print` 전부.** settings.json의 Read 거부는 실수를 막는 장치일 뿐이고(파이썬 프로세스는 못 막는다), 이 규칙이 본체다.
4. **숫자는 `notice_ner.eval`만 만든다** → `experiments/<id>/metrics_<split>.json`, `results.csv`. 보고서·대화에 숫자를 손으로 옮기지 않는다. `make report-table` 출력을 붙인다.
5. **모든 실행을 기록한다.** git commit, config sha256, data_version, seed, 하드웨어 → `experiments/<id>/run.json`. 커밋 안 된 변경이 있으면 실행을 거부한다.
6. **test를 보고 설정을 바꾸지 않는다.** 바꾸면 새 `exp_id`이고 보고서에 "사후(post-hoc)"로 표시한다. test 재평가는 `REASON="..."`과 함께만, `test_log.jsonl`에 남는다.

## 4. 수집 원칙
- `robots.txt` 확인(`urllib.robotparser`) 후 허용된 경로만. 호스트당 1 req/s 이하. 실패는 재시도 2회, 그 뒤 skipped 목록에 사유와 함께.
- User-Agent는 `naru-notice-ner-research/<ver>`. 개인 이메일을 넣지 않는다.
- 로그인·유료벽·캡차 우회 금지. 로그인이 필요한 곳(서울경찰청 '오늘의 집회' 첨부 등)은 태우가 직접 받아 `data/raw/`에 넣는다.
- 뉴스 본문 전체는 저장하지 않는다. **후보 문장 + 앞뒤 1문장 + 본문 sha256**만. `source_url`·`published_at`·`fetched_at` 필수. 출처 없는 문장은 버린다.
- 연구용. `data/`는 git에 올리지 않는다(MANIFEST·.gitkeep 제외). 저장소는 비공개.
- R1.5 이후엔 원천 텍스트(`data/raw/news`, `data/raw/official`)를 직접 열지 않는다. 기간이 나뉜 pool의 train·val만 본다.

## 5. 스택·규약

| 항목 | 선택 |
|---|---|
| 언어·환경 | Python 3.12, uv(`uv.lock` 커밋), src 레이아웃 `src/notice_ner` |
| 레코드 | pydantic v2 (`notice_ner.schema`, `extra="forbid"`), jsonl |
| 수집 | httpx, trafilatura, pdfplumber, 문장 분리기(R1.2에서 실데이터로 비교 후 결정) |
| 공간 | pyproj·shapely(EPSG:5179 거리), folium(PC-2 지도) |
| 학습 | torch(CUDA), transformers, datasets, accelerate · exp005만 peft(+양자화) |
| 평가 | 자체 스팬 집합 지표 + seqeval 대조, numpy 부트스트랩 |
| API | anthropic (exp004) |
| 품질 | ruff, mypy `--strict`(src), pytest, import-linter |

버전은 R0.1~R0.3에서 고정하고 `docs/decisions/ADR-R00-stack.md`에 실제 설치 버전을 적는다.

규약:
- 시간: tz-aware, 표기는 KST `+09:00`, ISO 8601. `published_at`이 TIME 정규화의 기준이다.
- 좌표: `[lng, lat]` WGS84. 거리는 EPSG:5179로 투영해 미터로.
- 문자 오프셋: NFC 정규화한 `text`의 Python 문자열 인덱스, `end` 미포함. `text[start:end] == span.text`가 항상 참.
- 태그 코드 `TIME` `ROAD` `INTERSECTION` `POI` `ADDRESS`, 분할 이름 `train` `val` `test` `test_ood` (영어 고정).
- CLI는 `src/notice_ner/cli/<name>.py` (`python -m notice_ner.cli.<name>`), 로직은 cli 밖 모듈에. `scripts/`엔 셸 게이트만.
- 패키지 경계 (`.importlinter`, `make layers`):
  - `labeling` ↛ `models`, `anthropic`, `transformers`, `torch`, `peft` — 사전 주석은 규칙만
  - `models` ↛ `eval` — 모델 코드는 test 잠금 모듈을 모른다. 학습 중 val 지표는 `notice_ner.metrics`로
- GPU 테스트는 `@pytest.mark.gpu`로 분리. `make check`는 제외하고, 🧪 Task의 Gate는 `make check-gpu`까지.
- 하이퍼파라미터·임계값은 `configs/`나 모듈 상단 상수에만. 상수 옆에 "태우가 바꿀 수 있음" 주석.

## 6. 명령
```
make setup            # uv sync, .env 존재 확인
make check            # ruff + mypy + lint-imports + check-no-fakes + pytest(-m "not gpu")  ← Gate
make check-gpu        # pytest -m gpu  ← 🧪 Task Gate에 추가
make layers           # import 계약만
make check-no-fakes   # 금지어만
make ls-up / ls-down  # Label Studio (docker compose)

# 아래는 해당 Task에서 CLI를 만들면 동작한다. 그 전엔 "아직 없음 — R?.?"로 실패
make record API=naver|kakao|topis|anthropic      # R0.3
make fetch SRC=naver|articles|topis|klue|...     # R1.x, R2.x
make parse-smpa                                  # R1.3b
make pool / pool-peek N=30                       # R1.5
make gaz / gaz-browse / gaz-map                  # R2.4
make iaa PROJECT=<id>                            # R3.1
make preannotate / ls-import                     # R3.2
make ls-progress                                 # R3.3
make export / split                              # R3.4
make train EXP=exp002                            # R4.x
make predict EXP=exp002 SPLIT=val                # R4.x (test는 거부)
make eval EXP=exp002 SPLIT=val                   # R4.0 (test는 거부)
make report-table                                # R4.0
make freeze EXP=exp002                           # PC-4, 태우가 직접
make test-run EXP=exp002 [REASON="..."]          # R4.7
```

## 7. 금지
- ROADMAP에 없는 작업, 스코프 확장, "하는 김에" 리팩터링·실험
- `docs/PROBLEM.md`·`docs/experiments.md` 임의 변경. 라벨 가이드는 R3.1 확정 후 버전을 올려서만
- 게이트 약화: `scripts/check_no_fakes.sh`, `.importlinter`, `.claude/settings.json` (settings가 Edit을 거부한다. 바꿀 필요가 있으면 태우에게 이유를 말한다)
- `# noqa`, `# type: ignore`, `except: pass` — 꼭 필요하면 같은 줄에 이유
- 시크릿·`.env`·`data/` 커밋, 공개 저장소
- 커밋 메시지에 Task ID 누락. 형식: `R1.2: 기사 본문 → 후보 문장 — robots 확인·1rps·앞뒤 1문장`

## 8. Definition of Done (Task)
1. PLAN에 태우 `ok` (🧪는 사전 등록 커밋 포함)
2. 실데이터 테스트 Red → Green
3. `make check` 초록 (🧪는 `make check-gpu`도)
4. walkthrough에 READ-ALONG + QUIZ(+RESULT), 채점 완료
5. ROADMAP status `REVIEW`, 커밋 완료
6. 태우가 `DONE`

## 9. 파일 지도
```
CLAUDE.md                    이 파일. 원칙
ROADMAP.md                   단계·Task·PC. 진행 상태의 진실
README.md                    시작하는 법, 사람이 할 일
docs/PROBLEM.md              과제 정의: 입력·태그·정규형·지표·하지 않는 것
docs/experiments.md          분할·사전 등록·지표 정의·부트스트랩·test 잠금·판정
docs/labeling_guide.md       라벨 규칙 (v0 초안 → R3.1에서 v1 확정)
docs/data_sources.md         출처·접근·라이선스·확인 상태
docs/decisions/              ADR-R00 스택 · R01 판정 규칙 · R02 로컬 베이스 모델 · R03 교사 라벨·합성
docs/walkthrough/            Task별 PLAN · 사전 등록 · READ-ALONG · RESULT · QUIZ
docs/report_template.md      R5.1 보고서 틀
docs/postmortem_template.md  R5.2 회고 틀
configs/                     collect_queries.yaml, exp001~005.yaml (사전 등록 칸 포함)
labeling/                    label_config.xml, README(운영·실제 export 구조), issues.md
data/MANIFEST.md             실데이터 출처 대장
data/raw recorded labeled    원천 3종 (gitignore)
data/interim splits gazetteer 파생물 (gitignore, 명령으로 재생성)
experiments/<exp_id>/        run.json, metrics_*.json, predictions_*, errors_val, test_log
results.csv                  모든 평가 실행 한 줄씩 — eval만 쓴다
reports/                     report.md, postmortem.md, 지도·그림
scripts/check_no_fakes.sh    금지어 게이트
.importlinter                패키지 경계 게이트
.claude/settings.json        Claude Code 권한: 정답·원천·결과 Edit 거부, 봉인·.env Read 거부
.claude/skills/              task-cycle, real-data-testing, walkthrough, experiment-protocol
src/notice_ner/              코드 (R0.1에서 뼈대, 이후 Task마다)
```
