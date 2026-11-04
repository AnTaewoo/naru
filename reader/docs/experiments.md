# experiments.md — 실험 프로토콜 v0

대회처럼 한다. val은 공개 리더보드, test는 비공개 리더보드다. 비공개는 마지막(R4.7)에 한 번만 열린다.
바꾸려면 ADR. 절차는 `.claude/skills/experiment-protocol/SKILL.md`.

## 1. 분할 — `published_at`(KST) 기준

| split | 기간 | 용도 | 라벨 배분(초안, R3.2에서 확정) |
|---|---|---|---|
| `train` | ~ 2025-06-30, test_ood 기간 제외 | 학습, 사전 주석, 별칭 추출, 규칙 근거 | 300 |
| `val` | 2025-07-01 ~ 2025-12-31 | 튜닝·선택·오류 분석 | 60 |
| `test` | 2026-01-01 ~ | R4.7에서 1회. 주판정 | 100 |
| `test_ood` | 2024-12-01 ~ 2025-04-30 | R4.7에서 1회. 대규모 집회가 이어진 기간 — 장소·규모 분포가 평소와 다르다. train에서 뺀다 | 40 |

- **시간 분할인 이유**: Naru는 과거 공지로 학습해 미래 공지를 읽는다. 무작위 분할은 같은 행사·같은 날 기사가 train과 test에 흩어져 점수를 부풀린다.
- **교차 주석 50**: val·test에서 뽑는다 (사전 주석 없이 단 문장이어야 사람 간 일치도가 정직하다).
- **근접 중복**: 문자 5-gram Jaccard ≥ 0.9는 같은 그룹, 그룹 대표 하나만 풀에 남긴다 (R1.5). 한 그룹이 두 분할에 걸치면 안 된다.
- **슬라이스** (test·test_ood 안에서 따로 보고):
  - `novel`: train과 최대 Jaccard < 0.7인 문장. 해마다 비슷한 마라톤 공지 문구 때문에 점수가 부풀었는지 본다
  - `official`(topis·smpa·seoul_press) vs `news`: **Naru 실서비스 입력은 official 쪽이다.** 학습 데이터 대부분은 news일 것이라 이 차이가 중요하다
- 배분은 PC-1의 기간별 풀 크기를 보고 R3.2에서 확정한다. test 100문장이면 paired Δ의 95% CI 폭이 대략 ±0.03~0.05로 예상된다. PC-4에서 val의 CI 폭을 보고 test를 늘릴지 정한다.

## 2. 사전 등록 (🧪 Task PLAN 아래, 실행 전, 수정 금지)
```
## 사전 등록
- 가설: KLUE NER 1단계가 장소·시간 개념을 미리 배워, train이 적을 때 exp002보다 낫다
- 비교: exp002 (val, 같은 seed 3개)
- 주지표: val Norm-F1 / 보조: Span-F1, 태그별 F1, 학습량 곡선
- 기대: train 100문장에서 +0.05 이상, 전체 300에선 +0.02 이내
- 판정 규칙: 전체 train에서 paired Δ의 CI 하한 > 0 → R4.7에 exp003을 로컬 대표로
- 틀리면: 1단계 에폭·헤드 초기화 중 하나만 바꿔 1회 재시도, 그래도면 exp002를 대표로
- 시도 상한: 5회 (config 커밋 수로 센다)
- 등록: 2026-11-xx HH:MM, 커밋 <hash>
```
- config의 `hypothesis`·`expected`·`decision_rule` 칸에도 같은 내용을 쓰고 커밋한다. 이 커밋이 실행 커밋보다 앞서야 한다 (PC-4에서 `git log`로 확인).
- val을 보고 설정을 바꾸는 건 허용이다 (그게 val의 용도). 대신 시도마다 config 커밋, 시도 수를 RESULT에 쓴다. results.csv엔 모든 시도가 남는다.

## 3. 지표 정의
`G`는 정답 집합, `P`는 예측 집합. 모든 F1은 micro: `P = |G∩P|/|P|`, `R = |G∩P|/|G|`, `F1 = 2PR/(P+R)`. 분모가 0이면 그 값은 정의하지 않고 개수와 함께 보고한다.

### 3.1 Span-F1 (strict)
- 원소: `(sentence_id, tag, start, end)`. 태그와 양 끝이 모두 같아야 정답
- 태그별 F1은 태그로 거른 부분집합에서
- 같은 값을 문자 단위 BIO + seqeval strict로도 계산해 일치를 확인한다 (R4.0 테스트)

### 3.2 Norm-F1
- 원소: `(sentence_id, tag, canonical)`. 한 문장 안 중복은 하나로
- canonical 비교: NFC + 공백 하나로 접기 후 완전 일치. TIME은 ISO 구간을 파싱해 분 단위로 다시 써서 비교
- 경계가 틀려도 정규형이 맞으면 정답 — Naru가 쓰는 건 정규형이다

### 3.3 E2E v0 (점 기반)
- 문장마다 `C_G = ⋃ crosswalks(resolve(t, c))`, `(t, c) ∈ G_s`, `t ∈ {INTERSECTION, POI, ADDRESS}`. `C_P`도 같게
- `Jaccard_s = |C_G ∩ C_P| / |C_G ∪ C_P|`. 둘 다 비면 그 문장은 빼고 뺀 수를 보고
- 지표 = 문장 평균
- 점 P/R@15m: 정답 지점 중 15m 안에 예측 지점이 있는 비율(R), 반대(P)
- `CROSSWALK_RADIUS_M = 30`, `POINT_TOL_M = 15` — 태우가 바꿀 수 있는 상수 (`notice_ner.metrics.e2e`)

### 3.4 비용·지연
- API: usage 토큰 × config의 가격(출처 URL·확인일) → 1,000문장당 USD. 지연은 순차 호출 벽시계 시간 p50/p95
- 로컬: 같은 GPU, batch 1, 워밍업 10문장 뒤 p50/p95. 비용은 USD로 바꾸지 않고 하드웨어와 시간으로 적는다

### 3.5 신뢰구간
- **기사(article_id) 단위 클러스터 부트스트랩.** 같은 기사의 문장들은 서로 닮아서, 문장 단위로 뽑으면 CI가 실제보다 좁아진다. 공식 공지는 공지 1건(smpa는 하루치 문서)이 한 클러스터
- B = 1000, seed 13, percentile 95%
- **paired**: 두 시스템에 같은 재표본을 써서 Δ 분포를 만든다. "A가 B보다 낫다"는 Δ의 CI가 0을 넘을 때만
- seed가 여럿인 실험: 재표본마다 seed별 지표를 계산해 평균 → CI는 데이터 변동, seed 표준편차는 따로

### 3.6 IAA (사람 간 일치도)
- 교차 50의 판정 전 원본 쌍으로 Span-F1·Norm-F1 (F1은 대칭이라 누가 정답이어도 같다)
- 시스템 점수의 참고 상한. 시스템이 IAA를 넘으면 라벨 노이즈를 외웠거나 가이드가 모호하다는 신호

## 4. test 잠금
- `notice_ner.io.load_split("test" | "test_ood")`는 `NOTICE_NER_TEST_UNLOCK=<exp_id>`일 때만 연다. `make test-run`만 이 변수를 설정한다
- `make test-run`은 `experiments/<id>/FROZEN.json`(태우가 `make freeze`로 만든 것)이 없으면 거부하고, FROZEN의 config sha와 현재 config가 다르면 거부한다
- `metrics_test.json`이 이미 있으면 거부. `REASON="..."`이 있으면 실행하고 `test_log.jsonl`에 사유·커밋·시각을 남긴다. 보고서에 재실행 횟수를 쓴다
- 분할 무결성 테스트는 `load_split_meta`(id·날짜·dedupe 그룹만, 문장·라벨 없음)로 봉인 분할을 검사한다
- Claude는 sealed 경로와 test 산출물을 어떤 방법으로도 열지 않는다 (CLAUDE.md §3.3)

## 5. 기록 — `experiments/<exp_id>/`

| 파일 | 내용 | 누가 쓰나 |
|---|---|---|
| `config.yaml` | 실행에 쓴 config 복사 | train/predict |
| `run.json` | commit, config sha256, data_version, seed, 시작·끝, GPU·드라이버 | train/predict/eval |
| `predictions_<split>.jsonl` | §PROBLEM 5 형식 | predict |
| `metrics_<split>.json` | 전 지표 + CI + 태그별 + 슬라이스 | eval |
| `errors_val.jsonl` | 유형(경계·태그·놓침·헛것·정규형)별 오류 | eval (val만) |
| `FROZEN.json` | config sha, commit, 시각 | `make freeze` (태우) |
| `test_log.jsonl` | test 평가 기록, 재실행 사유 | eval |

`results.csv`: 평가 1회 = 1줄 (`exp_id, variant, seed, split, …`). eval만 덧붙인다. 지우지 않는다 — 실패한 시도도 결과다.

## 6. 판정 — ADR-R01
주판정은 test의 주지표 paired Δ(로컬 대표 − API 대표)와 95% CI로 한다. 비교쌍·δ·판정 문장은 `docs/decisions/ADR-R01-judgement.md`. PC-4에서 승인된 판으로만 판정한다.
