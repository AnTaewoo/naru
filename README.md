# Naru (나루) — 통제를 반영하는 보행 우회 내비게이션

마라톤·집회 행진으로 횡단보도가 막히는 날, 통제 공지를 Claude API로 읽어 보행 그래프에 반영하고 지하보도·육교로 건너는 우회 경로와 해제 시각을 안내한다.

구현 코드는 `packages/contracts`(계약)만 있다. 나머지는 Claude Code가 `harness/ROADMAP.md`의 Task마다 태우와 같이 쓴다.

## 구조
```
naru/
├── .claude/                 ── 하네스 (Claude Code)
│   ├── CLAUDE.md            원칙 + 지도 (약 80줄)
│   ├── settings.json        권한 거부(.env, data/raw·recorded, 게이트) + PreToolUse hook
│   ├── hooks/guard.py       harness 밖 새 문서·실데이터 수정·섞인 커밋 차단
│   └── skills/              task-cycle, real-data-testing, walkthrough
├── harness/                 ── 하네스 (작업 기록)
│   ├── ARCHITECTURE.md      레인·클래스·흐름·상태기계 (설계의 진실)
│   ├── ROADMAP.md           P0~P7 Task·PC, ★ = 11/16 경로
│   ├── plans/active|completed/   Task별 PLAN·READ-ALONG
│   ├── progress.md          세션 로그
│   └── gates/check_no_fakes.sh
├── docs/                    ── 프로젝트 문서 (하네스를 지워도 남는다)
│   ├── INTERFACE.md v0.5    AI→BE ClosureCandidate(point/line/segment/zone), BE→FE /route /closures
│   ├── CONVENTIONS.md       레인별 규약 (AI §3 = Claude API 파서·리졸버)
│   ├── decisions/           ADR-001~007 (007 = 공지 파서는 Claude API)
│   └── architecture.png
├── packages/
│   ├── contracts/naru_contracts/   pydantic 계약 — 코드 있음, INTERFACE 예시로 검증됨
│   ├── ai/naru_ai/                 뼈대 (ingest · notice · signal · llm)
│   ├── be/naru_be/                 뼈대 (controllers · views · models)
│   └── fe/                         T5.0에서 create-next-app
├── data/MANIFEST.md  data/raw/  data/recorded/   실데이터 (gitignore)
├── pyproject.toml (uv 워크스페이스)  .importlinter  Makefile  docker-compose.yml  .env.example
└── scripts/                 fetch_* · record_* (Task에서 만든다)
```

## 시작
1. 압축을 풀고 `git init`. `cp .env.example .env`
2. 저장소 루트에서 `claude` 실행. `/hooks`로 guard 등록 확인
3. `harness/ROADMAP.md`의 T0.1을 `GO`로 → **"T0.1 PLAN 써줘"**

## 11/16까지의 경로 (★)
P0 데이터·툴체인 → P1 그래프·인덱스(`from_segment` 포함) → P2 계약 테스트·상태기계·DB → P3 라우팅·API → P4 공지 파서(Claude API)·평가(규칙 vs Claude) → P5 FE·배포. P4는 AI 담당이 P1~P3과 병행할 수 있다.

## 하네스가 막아 주는 것
| 위험 | 장치 |
|---|---|
| 가짜·모킹·건너뛰기 테스트 | `harness/gates/check_no_fakes.sh` → `make check` 실패 |
| AI↔BE import, BE 계층 위반 | `.importlinter` → `make layers` 실패 (6 계약) |
| 실데이터·기록 손 편집, `.env` 열람, 게이트 수정 | `.claude/settings.json` 거부 + hook(Bash 리다이렉션까지) |
| harness 밖 하네스 문서, 코드·하네스 섞인 커밋 | `.claude/hooks/guard.py` |
| 모델이 만든 좌표 | 계약: `PlacePoint`는 리졸버 출력만. Claude 스키마에 좌표 필드 없음 |

## 지우기
`harness/ARCHITECTURE.md`를 `docs/`로 옮길지 정한 뒤 `git rm -r .claude harness`. `Makefile`의 `check-no-fakes`가 `harness/gates/`를 부르므로 같이 고친다.
