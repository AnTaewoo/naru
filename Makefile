# Naru — 명령 설명은 .claude/CLAUDE.md §4
.PHONY: setup check layers check-no-fakes lint type test fe-check schema dev dev-be serve fetch record record-llm record-candidates record-naru-api

setup:
	uv sync --all-groups
	@if [ -f packages/fe/package.json ]; then pnpm -C packages/fe install; fi
	docker compose up -d mysql
	@test -f .env || (echo ".env 없음 — cp .env.example .env 후 키 채우기" && exit 1)

# Gate. 이게 초록이어야 커밋한다
check: lint type layers check-no-fakes test fe-check
	@echo "✅ Gate 통과"

lint:
	uv run ruff check packages scripts
	uv run ruff format --check packages scripts

type:
	uv run mypy --strict packages/contracts/naru_contracts packages/ai/naru_ai packages/be/naru_be

# AI↔BE 독립, contracts leaf, BE MVC 계층 — .importlinter
layers:
	uv run lint-imports

check-no-fakes:
	@bash harness/gates/check_no_fakes.sh

# pytest 종료 코드 5 = 테스트 0개. T0.1(뼈대만)에서만 정상
test:
	@uv run pytest; ec=$$?; if [ $$ec -eq 5 ]; then echo "⚠ 테스트 0개 — T0.1 상태에서만 정상"; exit 0; fi; exit $$ec

fe-check:
	@if [ -f packages/fe/package.json ]; then pnpm -C packages/fe check; else echo "FE 없음 (T5.0 전)"; fi

# naru_contracts → packages/fe/src/types/contracts.d.ts (T2.1에서 스크립트 생성)
schema:
	@test -f scripts/export_schema.py || { echo "아직 없음 — T2.1"; exit 1; }
	uv run python scripts/export_schema.py

# Flask :5000 + Next.js :3000 (T3.4·T5.0). AI 워커는 따로: uv run python -m naru_ai.worker --once
dev:
	@trap 'kill 0' EXIT; uv run flask --app naru_be.app run --port 5000 & pnpm -C packages/fe dev

dev-be:
	uv run flask --app naru_be.app run --port 5000

# 시연 운영 (홈서버, T5.3). make dev(5000·3000)와 같은 체크아웃에서 함께 돈다 — 포트와 Next 빌드 폴더(dist)가 따로.
# MySQL → 마이그레이션 → Next 빌드 → gunicorn(127.0.0.1) → 워커 1회(기록 재생, 외부 API 호출 없음) → Next standalone(127.0.0.1).
# 공개는 nginx 가 SERVE_FE_PORT 하나만 프록시한다 — Flask·/internal 은 밖에 열지 않는다 (README "운영")
SERVE_BE_PORT ?= 5050
SERVE_FE_PORT ?= 3050
SERVE_CHECK = http://127.0.0.1:$(SERVE_BE_PORT)/closures?bbox=126.965,37.555,126.990,37.580&at=2026-03-15T07:45:00%2B09:00
serve:
	docker compose up -d mysql
	uv run alembic -c packages/be/alembic.ini upgrade head
	cd packages/fe && NARU_NEXT_DIST_DIR=dist NARU_API_ORIGIN=http://127.0.0.1:$(SERVE_BE_PORT) pnpm build
	rm -rf packages/fe/dist/standalone/dist/static && cp -r packages/fe/dist/static packages/fe/dist/standalone/dist/static
	@trap 'kill 0' EXIT; \
	uv run gunicorn --workers 2 --threads 4 --bind 127.0.0.1:$(SERVE_BE_PORT) 'naru_be.app:create_app()' & \
	curl -sf --retry 90 --retry-connrefused --retry-delay 2 -o /dev/null '$(SERVE_CHECK)' && \
	NARU_BE_URL=http://127.0.0.1:$(SERVE_BE_PORT) uv run python -m naru_ai.worker --once && \
	PORT=$(SERVE_FE_PORT) HOSTNAME=127.0.0.1 node packages/fe/dist/standalone/server.js

fetch:
	@test -n "$(SRC)" || { echo "SRC=seoul_spatial|nodelink|course|station"; exit 1; }
	@test -f scripts/fetch_$(SRC).py || { echo "아직 없음 — P0에서 scripts/fetch_$(SRC).py를 만든다"; exit 1; }
	uv run python scripts/fetch_$(SRC).py

record:
	@test -n "$(API)" || { echo "API=bus|incident|rtd|kakao"; exit 1; }
	@test -f scripts/record_api.py || { echo "아직 없음 — T0.7"; exit 1; }
	uv run python scripts/record_api.py --api $(API)

# 실제 Claude 호출을 기록한다 (T4.1). NOTICES=문장 jsonl, LIMIT=상한
record-llm:
	@test -f scripts/record_llm.py || { echo "아직 없음 — T4.1"; exit 1; }
	uv run python scripts/record_llm.py --notices $(or $(NOTICES),data/raw/notices/sentences.jsonl) --limit $(or $(LIMIT),3)

# 실제 AI 실행 결과를 BE 테스트 입력으로 (T2.2, T4.2)
record-candidates:
	@test -n "$(SOURCE)" || { echo "SOURCE=course|notice|bus"; exit 1; }
	@test -f scripts/record_candidates.py || { echo "아직 없음 — T2.2"; exit 1; }
	uv run python scripts/record_candidates.py --source $(SOURCE)

# 로컬 Flask 응답을 FE 테스트 입력으로 (T3.4)
record-naru-api:
	@test -f scripts/record_naru_api.py || { echo "아직 없음 — T3.4"; exit 1; }
	uv run python scripts/record_naru_api.py
