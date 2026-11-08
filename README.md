# Naru (나루) — 통제를 반영하는 보행 우회 내비게이션

마라톤·집회 행진으로 횡단보도가 막히는 날, 통제 공지를 Claude API로 읽어 보행 그래프에 반영하고 지하보도·육교로 건너는 우회 경로와 해제 시각을 안내한다.

구현 코드는 `packages/contracts`(계약)만 있다. 나머지는 Claude Code가 `harness/ROADMAP.md`의 Task마다 태우와 같이 쓴다.

## 구조
```
naru/
├── .claude/                 ── 하네스 (Claude Code)
│   ├── CLAUDE.md            원칙 + 지도 (약 90줄)
│   ├── settings.json        권한 거부(.env, data/raw·recorded, 게이트) + PreToolUse hook
│   ├── hooks/guard.py       harness 밖 새 문서·실데이터 수정·섞인 커밋·main 커밋·새 브랜치 차단
│   └── skills/              task-cycle, real-data-testing
├── harness/                 ── 하네스 (작업 기록)
│   ├── ARCHITECTURE.md      레인·클래스·흐름·상태기계 (설계의 진실)
│   ├── ROADMAP.md           P0~P7 Task·PC, ★ = 11/16 경로
│   ├── plans/active|completed/   Task별 시작 메모 (3줄)
│   ├── progress.md          세션 로그
│   └── gates/check_no_fakes.sh
├── docs/                    ── 프로젝트 문서 (하네스를 지워도 남는다)
│   ├── INTERFACE.md v0.5    AI→BE ClosureCandidate(point/line/segment/zone), BE→FE /route /closures
│   ├── CONVENTIONS.md       레인별 규약 (AI §3 = Claude API 파서·리졸버)
│   ├── decisions/           ADR-001~007 (007 = 공지 파서는 Claude API)
│   ├── mockups/             FE 화면 목업 3장 (html, 데이터는 예시)
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
1. `develop` 브랜치에서 압축을 풀어 덮어쓴다. `cp .env.example .env` 후 키 채우기
2. 저장소 루트에서 `claude` 실행. `/hooks`로 guard 등록 확인
3. 하네스가 git에 없으면 `git add .claude harness docs && git commit -m "harness: 하네스 v1"`
4. **"T0.1 시작"** — 끝나면 보고가 오고, **"다음"** 하면 다음 Task로

## 진행 방식
Task 하나 끝 → 보고(한 것 / 파일 / 확인한 방법 / 직접 확인 명령 / 정한 것) → 멈춤 → 태우 "다음" → 다음 Task.
중간 승인·퀴즈 없음. 되돌리기 어려운 결정(계약 변경, 유료 호출, 데이터 삭제)만 묻는다. 멈추고 싶으면 "잠깐", 바꾸고 싶으면 "고쳐 …", 순서 바꾸려면 "T2.3 먼저".

## 11/16까지의 경로 (★)
P0 데이터·툴체인 → P1 그래프·인덱스(`from_segment` 포함) → P2 계약 테스트·상태기계·DB → P3 라우팅·API → P4 공지 파서(Claude API)·평가(규칙 vs Claude) → P5 FE·배포. P4는 AI 담당이 P1~P3과 병행할 수 있다.

## 운영 (홈서버 시연, T5.3)
`make serve` 하나로 띄운다. 개발(`make dev`, 5000·3000)과 같은 체크아웃에서 함께 돈다 — 포트와 Next 빌드 폴더(`packages/fe/dist`)가 따로다.

1. 순서: MySQL·마이그레이션 → Next 빌드 → gunicorn `127.0.0.1:5050`(workers 2·threads 4) → AI 워커 1회(코스·공지 기록 재생, 외부 API 호출 없음) → Next `127.0.0.1:3050`
2. 포트를 바꾸려면 `make serve SERVE_BE_PORT=… SERVE_FE_PORT=…`. 둘 다 127.0.0.1 에만 열린다
3. 공개 주소는 **https://naru.antaewoo.com** (DNS 2026-11-08). nginx 가 FE 포트 하나만 프록시한다. Flask 와 `/internal/*` 은 밖에 열지 않는다(Next rewrites 도 `/api/internal/*` 을 넘기지 않는다)
   ```nginx
   server {
       listen 80;
       server_name naru.antaewoo.com;
       location / { return 301 https://$host$request_uri; }
   }
   server {
       listen 443 ssl;
       server_name naru.antaewoo.com;
       ssl_certificate     /etc/letsencrypt/live/<인증서 이름>/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/<인증서 이름>/privkey.pem;
       location /api/internal/ { return 404; }
       location / {
           proxy_pass http://127.0.0.1:3050;
           proxy_http_version 1.1;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
   인증서가 이름을 나열한 형식이면 `naru.antaewoo.com` 을 더해 다시 받는다: `certbot certonly --nginx --cert-name <인증서 이름> -d <기존 이름 전부> -d naru.antaewoo.com` 뒤 nginx 다시 읽기
4. 계속 띄워 두기: tmux 나 systemd 사용자 서비스에서 `make serve`. 코드를 바꾸면 다시 `make serve`(빌드부터 한다)
5. 확인: `NARU_FE_ORIGIN=http://127.0.0.1:3050 NARU_CHROME_PATH=/usr/local/bin/google-chrome pnpm -C packages/fe e2e` (10 passed)
6. 시연 주소: `/?t=2026-03-15T07:45:00+09:00&from=37.5709686446227,126.9779039768265&to=37.5650416322942,126.976542945622`. 고지는 `/licenses`

## 하네스가 막아 주는 것
| 위험 | 장치 |
|---|---|
| 가짜·모킹·건너뛰기 테스트 | `harness/gates/check_no_fakes.sh` → `make check` 실패 |
| AI↔BE import, BE 계층 위반 | `.importlinter` → `make layers` 실패 (6 계약) |
| 실데이터·기록 손 편집, `.env` 열람, 게이트 수정 | `.claude/settings.json` 거부 + hook(Bash 리다이렉션까지) |
| harness 밖 하네스 문서, 코드·하네스 섞인 커밋, main 커밋·push, 새 브랜치 | `.claude/hooks/guard.py` |
| 모델이 만든 좌표 | 계약: `PlacePoint`는 리졸버 출력만. Claude 스키마에 좌표 필드 없음 |

## 지우기
`harness/ARCHITECTURE.md`를 `docs/`로 옮길지 정한 뒤 `git rm -r .claude harness`. `Makefile`의 `check-no-fakes`가 `harness/gates/`를 부르므로 같이 고친다.
