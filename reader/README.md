# notice-ner — Naru 통제 공지 파싱 실측 하네스

통제 공지(뉴스·TOPIS·서울시·서울경찰청)에서 **시간·장소를 뽑아 정규형으로 바꾸는 모델**을 실제 데이터로 만들어 잰다.
답할 질문: **로컬 소형 모델 + 사후학습이 Claude API(few-shot)만큼 하나?** 신뢰구간과 함께, 사전에 정한 판정 규칙으로.
결과는 Naru `ADR-007-llm.md`의 근거가 된다.

이 저장소엔 구현 코드가 없다. 원칙(CLAUDE.md), 단계(ROADMAP.md), 문서, 게이트만 있다. 코드는 Claude Code가 Task마다 태우와 같이 쓴다.

## 시작
1. 압축을 풀고 별도 비공개 저장소로: `git init` (Naru 저장소 안에 넣지 않는다 — 상위 CLAUDE.md가 섞인다)
2. `cp .env.example .env` — 키는 R0.3에서 채운다
3. **GPU 서버에서, 저장소 루트에서** `claude` 실행. 학습·추론·Label Studio가 같은 곳에 있어야 하고, `.claude/settings.json`의 경로 규칙은 시작 디렉터리 기준이다
4. `ROADMAP.md`에서 R0.1의 `status: TODO`를 `GO`로 바꾸고: **"R0.1 PLAN 써줘"**

## 태우가 지금 바로 할 일 (오래 걸리거나 매일 해야 하는 것)
- [ ] 서울경찰청 '오늘의 집회' 게시판: 과거 글이 어디까지 남아 있는지 확인하고, **오늘부터 매일** 첨부를 `data/raw/smpa/YYYYMMDD.<확장자>`로 저장. 하루 빠지면 그날 데이터는 영영 없다
- [ ] 네이버 검색 API 키 (developers.naver.com 또는 NCP API 허브 — 발급된 쪽에 맞춰 R0.3에서 엔드포인트 확정)
- [ ] 카카오 REST 키, 서울 열린데이터광장 인증키
- [ ] Anthropic API 키 + 콘솔에서 월 사용 한도
- [ ] 라벨러 확정 (팀원 Label Studio 이메일 → `.env`의 `ANNOTATORS`) — R3 전까지
- [ ] `docs/decisions/ADR-R01-judgement.md` 읽기 — "로컬이 API만큼 한다"를 무슨 숫자로 판정할지. PC-4 전에 승인

## 흐름
```
R0 준비 ─ R1 수집 ─┬─ R3 라벨 ─ R4 실험 ─ R5 보고 ─→ Naru ADR-007
          R2 지명사전 ┘     (val로 고르고, test는 R4.7에서 한 번)
```
| 단계 | 결과물 |
|---|---|
| R0 | 툴체인, GPU 기록, API 응답 기록 4종, Label Studio 실제 export 구조 |
| R1 | 기간별로 나뉜 후보 문장 풀 (뉴스 + 공식 공지), 근접 중복 제거 |
| R2 | 교차로·도로·장소 사전, `resolve(tag, 정규형) → 좌표·횡단보도` |
| R3 | 사람 라벨 500 + 교차 50, 시간 기준 분할 (test·test_ood 봉인) |
| R4 | 평가기 → 정규화기 → exp001 규칙 · exp002 RoBERTa · exp003 KLUE 전이 · exp004 Claude · exp005 로컬 LLM LoRA → test 1회 |
| R5 | 보고서(판정), 회고, Naru ADR-007 초안 |

## 하네스가 막아 주는 것
| 위험 | 장치 |
|---|---|
| 가짜·합성 데이터, 모킹, 테스트 건너뛰기 | `scripts/check_no_fakes.sh` → `make check` 실패 |
| 사전 주석에 LLM·학습 모델 (정답이 특정 시스템 쪽으로 기움) | `.importlinter` → `make layers` 실패 |
| Claude가 정답·원천 데이터·결과 숫자를 손으로 고침 | `.claude/settings.json` Edit 거부 |
| test를 미리 보거나 반복 평가 | sealed 디렉터리 + Read 거부 + `load_split` 잠금 + `test_log.jsonl` + 규칙 |
| 결과를 보고 가설 고쳐 쓰기 | 사전 등록 커밋이 실행보다 앞서야 함 (PC-4에서 `git log`로 확인) |
| 숫자를 손으로 옮기다 틀림 | `make report-table` 출력만 붙인다 |

settings.json의 거부는 Claude Code 도구와 `cat`·`sed`·리다이렉션까지 막지만 파이썬 프로세스가 여는 파일은 못 막는다. 그래서 봉인은 규칙 + 코드 잠금 + 로그로 겹쳐 둔다.

## 데이터 보관
`data/`, `labeling/ls-data/`는 git에 올리지 않는다. 라벨은 팀의 핵심 자산이니 `labeling/ls-data/`(Label Studio DB)와 `data/labeled/`를 비공개 저장소에 주기적으로 복사한다.

## 파일 지도
`CLAUDE.md` §9.
