# ROADMAP.md — notice-ner 실측

진행 상태의 진실. `status`: `TODO → GO → DOING → REVIEW → DONE`. **GO·DONE은 태우만 쓴다.** Claude는 `DOING`·`REVIEW`만.
**PC(Phase Check)** 는 태우가 직접 눈으로 보는 관문이다. 통과해야 다음 단계 Task에 GO를 준다.

Task 종류: 🧩 코드 · 🗂 데이터 · 🧪 실험 · 🧑 사람. Claude Task는 한 번에 하나. 🧑 사람 Task는 그와 따로 병행한다.
절차: `.claude/skills/task-cycle` (🧪는 + `experiment-protocol`).

## 이 실측이 답할 것

| | 질문 | 답이 나오는 곳 |
|---|---|---|
| Q1 | 로컬 소형 모델 + 사후학습이 Claude few-shot만큼 하나? | R4.7 test 주지표의 paired Δ + 95% CI → ADR-R01 판정 |
| Q2 | 차이는 어디서 나나? | 태그별 · test_ood · novel · news/official · 학습량 곡선(val) |
| Q3 | 비용·지연은? | 1,000문장당 비용, 문장당 p50/p95, 하드웨어 |

→ `reports/report.md` → Naru `ADR-007-llm.md` 초안

## 일정 (2주 초안)

| 날 | 단계 | 사람이 할 일 |
|---|---|---|
| D1–2 | R0 준비 | 키 발급 4종, Label Studio 버전·계정, ADR-R01 읽기 |
| D2–4 | R1 수집 | '오늘의 집회' 매일 저장(끝까지 계속), PC-1에서 문장 읽기 |
| D4–5 | R2 지명사전 | PC-2 지도 핀 30개 확인 |
| D5–10 | R3 라벨 | 파일럿 20문장(2명), 본 라벨 500문장(팀), 교차 50문장, 판정 |
| D9–13 | R4 실험 | 실험마다 사전 등록 승인, PC-4 동결 |
| D14 | R5 보고 | 판정 확인, Naru 반영 결정 |

---

## R0 — 준비

### R0.1 🧩 툴체인·패키지 뼈대
- status: TODO
- depends: —
- 산출: `pyproject.toml`(uv, Python 3.12, src 레이아웃. 기본 의존성 pydantic, `dev` 그룹 ruff·mypy·pytest·import-linter), ruff·mypy·pytest 설정(마커 `gpu` 등록), `uv.lock`. `src/notice_ner/` 아래 빈 하위 패키지 8개 — `cli` `collect` `gazetteer` `labeling` `normalize` `metrics` `models` `eval`. 각 `__init__.py`에 docstring 한 줄: 역할과 import해도 되는 범위 (`.importlinter`가 이 이름들로 돈다)
- 테스트: 없음(환경 Task). `make check`가 "테스트 0개" 경고와 함께 초록, `make layers` 2 kept
- Gate 시연 (태우가 직접 보고 되돌린다. walkthrough에 결과 기록):
  1. `src/notice_ner/labeling/x.py`에 `import anthropic` → `make layers` BROKEN
  2. `tests/test_x.py`에 `pytest.skip` 한 줄 → `make check-no-fakes` 실패
  3. Claude에게 `results.csv`를 Edit해 보라고 → Claude Code가 거부
- 기록: 실제 버전 → `docs/decisions/ADR-R00-stack.md`

### R0.2 🧩 GPU·학습 스택
- status: TODO
- depends: R0.1
- 산출: `ml` 의존성 그룹 — torch(CUDA 휠), transformers, datasets, accelerate. `docs/env/gpu_<YYYYMMDD>.txt`: `nvidia-smi` 출력 그대로 + torch가 본 장치명·VRAM·CUDA 버전
- 테스트(`gpu`): `torch.cuda.is_available()`, 장치명·VRAM이 env 기록과 일치
- 질문: torch CUDA 휠 인덱스 — `nvidia-smi`의 드라이버/CUDA 버전을 보고 추천
- 기록: VRAM → exp005 가능 범위 메모 (RTX 3060은 12GB·8GB 모델이 있다. 판단은 R4.6과 ADR-R02에서)

### R0.3 🗂 API 키 확인·응답 기록기
- status: TODO
- depends: R0.1
- 🧑 태우: `.env`에 NAVER·KAKAO·SEOUL_OPENDATA·ANTHROPIC 키. Anthropic 콘솔에서 월 한도 설정
- 산출: `src/notice_ner/recording.py`(호출 → `data/recorded/<api>/<ts>.json`, 키 제거, 원문 그대로), `cli/record.py` → `make record API=naver|kakao|topis|anthropic`
- 실데이터: API당 live 1회 — naver(`교통통제`, display 10) · kakao 키워드(`숭례문`) · TOPIS 공지 최근 몇 건 · anthropic(`claude-haiku-5-5`에 한 줄 응답 요청 — 연결과 usage 형식 확인용)
- 테스트(재생): 기록을 열어 확인한 필드가 있는지. 필드명은 기록 파일을 연 뒤에 적는다
- 질문: 네이버 엔드포인트 — `openapi.naver.com` vs NCP API 허브. 발급된 키 종류를 보고 결정 (`docs/data_sources.md` #1)
- 주의: 이후 테스트는 재생만. live 추가 호출은 PLAN에 횟수를 적는다

### R0.4 🧩 Label Studio 기동·export 형식 확인
- status: TODO
- depends: R0.3
- 🧑 태우: `.env`의 `LABEL_STUDIO_VERSION`을 Docker Hub 태그에서 골라 고정(latest 금지) → `make ls-up` → 첫 계정(관리자) → 프로젝트 생성 후 `labeling/label_config.xml` 붙여넣기 → Access Token을 `.env`에
- 산출: R0.3 네이버 기록의 `description` 1개(HTML 태그만 제거, 출처 URL 유지)를 task로 import → 태우가 스팬 2개 + 정규형 → export JSON 원본을 `labeling/format_probe/<ts>.json`에 그대로. `labeling/README.md` §2에 실제 구조(키 경로, offset 기준, 정규형↔region 연결, 주석자 식별 필드, quality 경로)를 적는다
- 테스트(실데이터): format_probe의 모든 region에서 `text[start:end] == value.text`, 정규형이 region에 짝지어짐, 주석자 식별 가능
- 질문: per-region TextArea가 기대대로 안 묶이면 대안 — 실제 동작을 보고 결정

### PC-0 (태우)
- [ ] `make check` 초록, Gate 시연 3개를 직접 봤다
- [ ] `docs/env/gpu_*.txt`에 VRAM이 있다
- [ ] recorded 4종, 재생 테스트 초록
- [ ] `labeling/README.md` §2가 실제 JSON 경로로 채워졌다
- [ ] ADR-R01(판정 규칙)을 읽었다 — 승인은 PC-4까지

---

## R1 — 수집 (중복 제거 후 실제 문장 2,000개 이상, 출처·게시 시각 필수)

### R1.1 🗂 네이버 뉴스 색인
- status: TODO
- depends: PC-0
- 🧑 태우: `configs/collect_queries.yaml` 검토·승인. 쿼리가 곧 데이터 분포다 — 어떤 쿼리가 어느 기간·행사를 데려오는지 PLAN에서 같이 본다
- 산출: `collect/naver.py`, `cli/fetch_naver.py` — 쿼리 × 정렬(date, sim) × start 페이지를 `data/raw/naver/<run_ts>/<slug>__<sort>__<start>.json`에 기록 형식 그대로. `tests/test_manifest.py`(MANIFEST의 sha256·행 수 검증 — 이후 모든 데이터 Task가 여기에 항목을 더한다)
- 테스트(실데이터): 모든 item의 `pubDate`가 KST로 파싱됨, 링크 중복 제거 후 기사 수, 쿼리별·연도별 기사 수 표(태우 확인용 출력)
- 쿼터: 쿼리 수 × 2 × 11호출 — PLAN에 숫자로. 일 한도 이내

### R1.2 🗂 기사 본문 → 후보 문장
- status: TODO
- depends: R1.1
- 산출: `collect/article.py`, `collect/sentences.py`, `cli/fetch_articles.py` → `data/raw/news/<run_ts>.jsonl` + `<run_ts>.skipped.jsonl`(robots 불허·실패·유료벽, 사유 포함)
- 레코드: `sentence_id, text, context_prev, context_next, article_id, article_text_sha256, source_type="news", source_url, publisher, published_at, fetched_at, query`
- 후보 필터: 통제 단서어(통제·차로·행진·교차로·우회 등 — 목록은 PLAN에서 태우와 확정)
- 감사용 표본: 필터에서 떨어진 문장은 저장하지 않되, 기사당 최대 1문장을 무작위로 `<run_ts>.rejected_sample.jsonl`에 (PC-1에서 놓친 문장을 세는 데만 쓴다)
- 테스트(실데이터): 모든 레코드에 출처 3종, skipped에 robots 사유가 있는 호스트의 URL은 결과에 없음, NFC 정규화됨
- walkthrough: 태우가 기사 3개의 원문과 문장 분리 결과를 눈으로 대조한 기록
- 질문: 문장 분리기 — (a) kss (b) 정규식. 같은 기사 3개로 둘 다 돌려 보고 결정

### R1.3a 🗂 TOPIS 공지
- status: TODO
- depends: R0.3
- 산출: `collect/topis.py`, `cli/fetch_topis.py` → `data/recorded/topis/…`(원문) + `data/raw/official/topis_<run_ts>.jsonl`(문장 레코드, `source_type="topis"`)
- 확인할 것: 과거 공지를 몇 년치까지 주는가 — 응답을 보고 MANIFEST에. 공공누리 2유형(비상업) 표기
- 테스트(재생): 공지 수·날짜 범위·문장 레코드 필수 필드

### R1.3b 🧑🗂 서울경찰청 '오늘의 집회'
- status: TODO
- depends: R0.1
- 🧑 태우: 게시판의 과거 글 보관 범위 확인 → 받을 수 있는 만큼 + **오늘부터 매일** `data/raw/smpa/<YYYYMMDD>.<pdf|hwp|jpg>`. 로그인이 필요하므로 자동화하지 않는다
- 산출: `collect/smpa.py`(pdfplumber 표 → 행), `cli/parse_smpa.py` → `data/raw/official/smpa_<YYYYMMDD>.jsonl` (행마다 장소·행진경로 텍스트를 문장 레코드로, 일시는 `published_at`과 별도 필드로)
- 테스트(실데이터): PDF 3개에서 파싱된 행 수 = 태우가 PDF를 열어 센 수(walkthrough에 기록), 장소 칸이 빈 행 0
- 주의: hwp·jpg는 v0에서 파싱하지 않는다. MANIFEST에 개수만

### R1.3c 🗂 서울시 보도자료 (선택)
- status: TODO
- depends: R1.2
- robots·이용조건을 확인하고 가능하면 R1.2 방식으로 수집. 불가하면 MANIFEST에 불가 사유만

### R1.4 🗂 KLUE NER (exp003 전이용)
- status: TODO
- depends: R0.2
- 산출: `cli/fetch_klue.py` → `data/raw/klue_ner/`(datasets로 받아 저장, HF 데이터셋 revision 기록), MANIFEST 항목(라이선스는 데이터 카드에서 확인)
- 테스트: train/validation 행 수와 태그 목록 — 로드해서 본 값을 테스트에 적는다 (조사 때 본 값은 21,008/5,000, BIO 13개. 다르면 실제 값이 맞다)

### R1.5 🧩 후보 풀·기간 분리
- status: TODO
- depends: R1.2, R1.3a, R1.3b
- 산출: `collect/pool.py`, `cli/build_pool.py`, `cli/pool_peek.py` → `data/interim/pool_v1/{train,val}.jsonl`, `data/interim/pool_v1/sealed/{test,test_ood}.jsonl`, `data/interim/pool_v1/STATS.md`(기간 × 출처 × 월 문장 수 — 숫자만, 문장 없음)
- 처리: NFC·공백 정규화 → 완전 중복 해시 제거 → 문자 5-gram Jaccard ≥ 0.9 근접 중복 그룹 → 그룹 대표(가장 이른 `published_at`) → 기간 배정(`docs/experiments.md` §1) → test·test_ood 문장마다 train과의 최대 유사도 `max_jaccard_train` 기록(novel 슬라이스용)
- 테스트: 풀 안 어떤 두 문장도 Jaccard ≥ 0.9가 아님, 모든 문장에 period, test_ood 기간 문장이 train·val에 없음, 같은 dedupe 그룹이 두 기간에 걸치지 않음
- 질문: 근접 중복 계산 — (a) 전수 비교 (b) MinHash LSH. 풀 크기를 보고 결정
- 이 Task 이후 Claude는 원천 텍스트와 sealed를 열지 않는다 (CLAUDE.md §3·§4)

### PC-1 (태우)
- [ ] STATS.md: 기간별 문장 수가 라벨 배분을 감당하나 (각 기간 ≥ 배분 × 3 권장 — 배분은 `docs/experiments.md` §1)
- [ ] 태우가 터미널에서 직접 `make pool-peek N=30`(train·val 기간 무작위)을 읽고 통제 관련 문장 비율 기록. 70% 미만이면 필터 수정 Task 추가
- [ ] `make pool-peek N=30 REJECTED=1`(감사용 표본, train·val 기간만)을 읽고 놓친 통제 문장 수 기록
- [ ] skipped 사유 분포, robots 불허 호스트 목록 확인

---

## R2 — 지명사전·리졸버 (R1과 독립, PC-0 뒤 아무 때나)

### R2.1 🗂 교차로·횡단보도 사전
- status: TODO
- depends: PC-0
- 실데이터: 서울 열린데이터광장 교차로·횡단보도 위치 데이터 (`docs/data_sources.md` #7 — 데이터셋 ID와 컬럼은 페이지와 파일을 열어 확인)
- 산출: `cli/fetch_seoul_spatial.py`, `gazetteer/build.py` → `data/gazetteer/intersections.parquet`(정규명·구·lng·lat·source_id), `crosswalks.parquet`(crosswalk_id·lng·lat)
- 테스트(실데이터): 파일을 열어 본 컬럼명으로 로드, 좌표가 서울 범위(경도 126.7–127.3, 위도 37.4–37.8), 교차로명에 '세종'이 들어간 행 수 = 파일에서 센 값
- 질문: 같은 이름 교차로가 여러 구에 있을 때 정규형 — (a) 이름+구 (b) 이름만 + 후보 목록

### R2.2 🗂 도로명 사전
- status: TODO
- depends: R2.1
- 질문: 출처 — (a) 도로명주소 도로명코드 전체분 (추천: 정규형 기준은 공식 도로명이어야 한다) (b) 표준노드링크 도로명 (Naru가 쓸 데이터지만 표기가 섞일 수 있다)
- 산출: `data/gazetteer/roads.parquet`(정규명·시군구·코드)
- 테스트: 서울 도로명 수, 파일에서 확인한 이름 몇 개 존재

### R2.3 🗂 장소·주소 리졸버 (카카오 기록)
- status: TODO
- depends: R0.3
- 산출: `gazetteer/kakao.py` — 정규형 이름 → 카카오 키워드/주소 검색 → `data/recorded/kakao/<kind>/<sha1(name)>.json` 캐시(없으면 live 1회, 있으면 재생). 1순위 선택 규칙(서울 범위·카테고리)
- 테스트: R0.3 기록(`숭례문`) 재생 → 좌표가 서울, 장소명 일치
- 확인: 카카오 약관의 검색 결과 저장 범위 (연구용 캐시 허용 여부) → MANIFEST에

### R2.4 🧩 리졸버 + 주석자용 사전 검색표
- status: TODO
- depends: R2.1, R2.2, R2.3
- 산출: `gazetteer/resolver.py` — `resolve(tag, canonical) -> Resolution | None` (lng·lat·source·반경 `CROSSWALK_RADIUS_M = 30` 안 횡단보도 ID). ROAD는 이름 유효성만(좌표 None). `cli/build_gazetteer.py`(make gaz), `cli/gaz_browse.py`(make gaz-browse) → `data/gazetteer/browse.html`(주석자가 교차로·도로 정규형을 검색해 복사하는 표), `cli/gaz_map.py`(make gaz-map)
- 테스트: 사전에서 고른 교차로 5개(이름은 파일에서 복사) → 좌표 일치, 횡단보도 ≥ 1
- 태우가 바꿀 지점: 반경 30m, 동명 처리, 카카오 1순위 규칙

### PC-2 (태우)
- [ ] `make gaz-map` → `reports/pc2_map.html`: 교차로 15 + 카카오 POI 15(무작위). 핀 30개를 위성지도와 대조해 틀린 것 기록. 2개 이상 틀리면 선택 규칙 수정
- [ ] browse.html로 약칭('세종R' 같은)의 정규형을 찾아보고, 걸린 시간을 라벨 가이드에 반영

---

## R3 — 라벨 (사람 500문장 + 교차 50문장)

### R3.1 🧑🧩 라벨 가이드 v1 (파일럿)
- status: TODO
- depends: R0.4, R1.5, R2.4
- 산출: train 기간에서 무작위 20문장 → Label Studio 파일럿 프로젝트 → 태우 + 1명이 각자 라벨 → `cli/compare_annotators.py`(make iaa: 두 사람 Span-F1·Norm-F1 + 불일치 목록) → 불일치를 보며 `docs/labeling_guide.md` §6 열린 질문을 정하고 v1 확정
- 테스트: compare 결과의 불일치 목록이 export의 실제 차이와 일치 (walkthrough에 3건 눈으로 대조)
- 질문(PLAN): 관계 라벨(구간 FROM→TO, 시간↔장소)을 v0에 넣을지 — (a) 안 넣음, 추천: 일정을 지키고 나중에 같은 문장에 추가할 수 있다 (b) 넣음: 라벨 시간 +50% 예상
- 완료: 가이드 상단 `상태: v1 확정`. 이후 바꾸면 v1.1 + 영향받는 라벨 범위 기록

### R3.2 🧩 표본 추출·사전 주석·가져오기
- status: TODO
- depends: R3.1
- 산출: `labeling/sample.py`(기간별 배분·출처 층화·seed 고정, 교차 50은 val·test에서), `labeling/preannotate.py`(train만, 사전 정확 일치 + TIME 정규식, 정규형 미리 채움), `cli/preannotate.py`, `cli/ls_import.py` → Label Studio 본 프로젝트
- 테스트: 배분 수, 사전 주석이 train에만 있음, 교차 50이 val·test에만 있음, `make layers`(labeling이 모델·LLM을 모름)
- 질문: 배분 확정(PC-1 풀 크기 보고), Label Studio 프로젝트 구성 — 1개(주석자 배정) vs 2개(교차 전용 분리)

### R3.3 🧑 라벨링
- status: TODO
- depends: R3.2
- 🧑 팀: 500문장 + 교차 50. 가이드 v1. 막히면 `labeling/issues.md`
- Claude: `cli/ls_progress.py`(make ls-progress — 주석자별 완료·남은 수만, 문장 내용 출력 없음)
- 예상: 문장당 1–1.5분 → 4명이면 1인 2–3시간

### R3.4 🧩 export·검증·분할
- status: TODO
- depends: R3.3
- 산출: `labeling/export.py`(R0.4에서 기록한 실제 구조 기준), `labeling/validate.py`, `labeling/split.py`, `cli/export_labels.py`, `cli/make_split.py`
  - 검증: 모든 region `text[start:end]` 일치, 주석자 ∈ `ANNOTATORS`, 태그 5종, 정규형 비어 있지 않음, ROAD·INTERSECTION 정규형 ∈ 사전 또는 `NOGAZ:` 접두, TIME 정규형이 ISO 구간으로 파싱, `quality=drop` 수 기록
  - 위반은 고치지 않고 목록으로(봉인 분할 항목은 sentence_id·유형만) → issues.md → 사람이 Label Studio에서 수정 → 재export
  - 분할: pool 기간을 그대로 → `data/splits/v1/{train,val}.jsonl`, `data/splits/v1/sealed/{test,test_ood}.jsonl`, `data/splits/v1/SPLIT.md`(수·sha256만), 교차 원본 쌍은 `data/splits/v1/iaa/`
  - 교차 50의 정답: 불일치는 태우가 판정 → 판정본이 정답. 판정 전 원본 쌍은 IAA용으로 보존
- 테스트(실데이터): 검증 규칙 전부 + 누수 0(같은 dedupe 그룹이 두 분할에 없음, 기간 경계). 봉인 분할은 메타(id·날짜·그룹)만 읽는 `load_split_meta`로 검사
- 질문: 판정 방식(태우 단독 vs 둘이 합의)

### PC-3 (태우)
- [ ] IAA(교차 50): 주석자 간 Span-F1·Norm-F1. Norm-F1 < 0.80이면 가이드 v1.1 → 재라벨 범위를 정하고 나서 R4로
- [ ] issues.md 미해결 0
- [ ] SPLIT.md 수 확인, `data_version = v1` 확정
- [ ] `.claude/settings.json` Read 거부에 sealed 경로가 있는지 확인

---

## R4 — 실험 (val로 고르고, test는 R4.7에서 한 번)

### R4.0 🧩 평가기·test 잠금
- status: TODO
- depends: R3.4
- 산출: `metrics/spans.py`(Span-F1 strict, 태그별), `metrics/norm.py`(Norm-F1), `metrics/e2e.py`(Jaccard, 점 P/R@15m — 리졸버 사용), `metrics/bootstrap.py`(기사 단위 클러스터, B=1000, paired Δ), `eval/evaluate.py` + `cli/evaluate.py`(predictions + 정답 → metrics json, results.csv 한 줄, run.json, test 잠금·로그), `io.load_split`의 잠금(`NOTICE_NER_TEST_UNLOCK`), `cli/freeze.py`, `cli/report_table.py`
- 테스트(실데이터):
  - IAA 쌍(주석자 A를 예측, B를 정답)으로 계산한 Span-F1 = 같은 쌍을 문자 단위 BIO로 바꿔 seqeval strict로 계산한 값
  - 정답을 예측으로 넣으면 전 지표 1.0
  - 잠금 없이 `load_split("test")` → 예외. 잠금 경로(재실행 거부, REASON 로그)는 분할 이름과 무관한 코드라 val로 검사 — test를 실제로 열지 않는다
- 첫 공식 숫자: IAA → results.csv에 `exp000_iaa`

### R4.1 🧩 정규화기 (모든 모델 공용)
- status: TODO
- depends: R4.0
- 산출: `normalize/time.py`(TIME 표면형 + published_at + 문맥 → ISO 구간. 규칙마다 근거 train sentence_id), `normalize/place.py`(표면형 → 정규형: train 정답에서 자동 추출한 별칭표 `data/gazetteer/aliases_train.csv` + 사전 정확 일치 + 편집거리 후보)
- 측정: **정답 스팬**을 넣었을 때의 val Norm-F1 = 정규화기 상한 → results.csv `exp000_oracle_norm`
- 테스트: train 정답 TIME에 대한 정규화 정확도(처음 실행해서 본 값을 하한으로 고정). val 수치는 테스트에 넣지 않는다 — 지표로만
- 질문: 편집거리 임계값, 별칭 충돌(같은 표면형이 두 정규형) 처리

### R4.2 🧪 exp001 규칙 기준선
- status: TODO
- depends: R4.1
- 산출: `models/rule.py`(사전·별칭 일치 + TIME 정규식 → predictions), `cli/predict.py`(config의 `system`으로 모델을 고른다 — 이 Task에선 `rule`만), `configs/exp001.yaml` 사전 등록 칸
- 테스트: predictions가 schema 통과, 모든 오프셋 유효
- 실행: val → metrics_val.json, errors_val.jsonl

### R4.3 🧪 exp002 klue/roberta-base (우리 train만)
- status: TODO
- depends: R4.2
- 산출: `models/token_cls.py`(문자 스팬 ↔ BIO 정렬, 학습, 예측 → 문자 스팬), `cli/train.py`, `cli/predict.py`에 `token_cls` 추가
- 테스트: train 전 문장에서 스팬 → BIO → 스팬 왕복이 원래 스팬과 일치(안 되는 스팬은 목록 — 0이 목표), `gpu`: 실제 train 20 step 후 loss 감소
- 학습량 곡선: train 50/100/200/전체 × seed 3 → val (`experiments/exp002/learning_curve.png`). 라벨을 더 할지의 근거
- 질문: 하이퍼파라미터 초안 확정, 문맥 입력 여부

### R4.4 🧪 exp003 KLUE NER 전이
- status: TODO
- depends: R4.3, R1.4
- 1단계 KLUE NER 학습 → 분류 헤드 교체 → 2단계 우리 train (exp002와 같은 설정)
- 테스트: 1단계 헤드 13라벨, 2단계 헤드 11라벨, `gpu` 스모크
- 질문: 2단계 헤드 — (a) 재초기화 (b) KLUE 태그에서 매핑 초기화(LC→장소류, DT·TI→TIME)

### R4.5 🧪 exp004 Claude few-shot (API 기준선)
- status: TODO
- depends: R4.1 (R4.3과 독립)
- 산출: `models/llm_fewshot.py`(tool use 구조화 출력 — `input_schema`로 spans[text, tag, canonical], temperature 0). 호출마다 `data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json`에 기록하고, 기록이 있으면 재생한다 — 같은 config로 다시 돌려도 API를 다시 부르지 않는다. 정렬기(스팬 텍스트 → 문장 내 위치. 못 찾으면 헛것으로 처리하고 개수 보고). `cli/predict.py`에 `llm_fewshot` 추가
- few-shot 예시: train에서 고정 k개(태그 커버리지 기준), id를 config에. 예시 선택에 val을 쓰지 않는다
- 변형: `spans_ours`(LLM 스팬 + 우리 정규화기) / `llm_canonical`(LLM 정규형)
- 비용: 실행일 공식 가격표를 config에 URL·날짜와 함께 복사, usage 토큰으로 계산. PLAN에 val 예상 비용과 상한
- 테스트: recorded 재생으로 파싱·정렬, recorded의 model·prompt_version이 config와 다르면 fail
- 모델: `claude-haiku-5-5`, `claude-sonnet-5-5` (실행 시점에 API 문서에서 ID 확인)

### R4.6 🧪 exp005 로컬 생성형 LLM + LoRA (선택)
- status: TODO
- depends: R4.5, ADR-R02 승인, R0.2 VRAM 기록
- 산출: `models/gen_lora.py`(입력: 문장 + 문맥 + published_at → 출력 JSON spans[text, tag, canonical], QLoRA, 스키마 제약 디코딩), 같은 GPU에서 문장당 지연 p50/p95
- 테스트: 출력이 스키마를 통과하는 비율 1.0, `gpu` 스모크
- 질문: 베이스 모델(ADR-R02), 제약 디코딩 방식 — R0.2 환경을 보고 결정
- 생략 조건: exp003이 val에서 이미 ADR-R01 기준 exp004와 동급이면 태우가 생략 여부를 정한다

### PC-4 (태우) — 동결
- [ ] ADR-R01 승인 (주지표·비교쌍·δ)
- [ ] 실행한 실험마다 사전 등록 커밋이 실행보다 앞선다 (`git log`로 확인)
- [ ] val에서 본 paired Δ의 CI 폭이 δ보다 좁을 것 같은가 — 넓으면 test 문장을 늘릴지 결정
- [ ] 실험마다 직접 `make freeze EXP=…` (FROZEN.json: config sha·commit)

### R4.7 🧪 test 공개 (한 번)
- status: TODO
- depends: PC-4
- Claude: `make test-run EXP=…`를 동결된 실험 전부 → `make report-table`
- 🧑 태우: 그다음에야 `.claude/settings.json`에서 `predictions_test`·`errors_test` Read 거부 두 줄을 지운다 → test 오류 분석 가능 (보고서에 "사후 분석"으로 표시)

---

## R5 — 보고

### R5.1 🧩 보고서
- status: TODO
- depends: R4.7
- 산출: `reports/report.md`(`docs/report_template.md`). 숫자는 `make report-table` 출력만. ADR-R01 판정 문장. "측정하지 않은 것" 필수

### R5.2 🧩 회고 + Naru ADR-007 초안
- status: TODO
- depends: R5.1
- 산출: `reports/postmortem.md`(`docs/postmortem_template.md`), `reports/ADR-007-llm.draft.md`(Naru 저장소에 옮길 초안)

### PC-5 (태우)
- [ ] 판정이 사전 등록 규칙대로 나왔다 (숫자 → 판정 문장)
- [ ] v1으로 갈지 정한다: 관계 라벨, 교사 라벨(ADR-R03), 라벨 증량(학습량 곡선 기울기)
- [ ] Naru 반영: ADR-007, Naru ROADMAP P5 수정
