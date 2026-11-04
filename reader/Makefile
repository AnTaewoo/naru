# notice-ner — 명령 설명은 CLAUDE.md §6
# 아직 만들지 않은 CLI를 부르면 "아직 없음 — R?.?"로 실패한다. 해당 Task에서 CLI가 생기면 그대로 동작한다.
SHELL := /bin/bash
PY    := uv run python -m
EXP   ?=
SPLIT ?= val
VER   ?= v1
N     ?= 30

need          = @test -f src/notice_ner/cli/$(1).py || { echo "아직 없음 — $(2)에서 만든다 (src/notice_ner/cli/$(1).py)"; exit 1; }
need_exp      = @test -n "$(EXP)" || { echo "EXP=exp00N 이 필요하다"; exit 1; }
no_test_split = @case "$(SPLIT)" in *test*) echo "test·test_ood는 make test-run 으로만 연다 (R4.7)"; exit 1;; esac

.PHONY: setup check check-gpu lint type layers check-no-fakes test ls-up ls-down \
        record fetch parse-smpa pool pool-peek gaz gaz-browse gaz-map iaa preannotate ls-import ls-progress \
        export split train predict eval report-table freeze test-run

## ── 준비 ─────────────────────────────────────────────
setup:
	uv sync --all-groups
	@test -f .env || { echo ".env 없음 — cp .env.example .env 후 키를 채운다 (R0.3)"; exit 1; }

## ── Gate ─────────────────────────────────────────────
check: lint type layers check-no-fakes test

lint:
	uv run ruff check .
	uv run ruff format --check .

type:
	uv run mypy --strict src

layers:
	uv run lint-imports

check-no-fakes:
	@bash scripts/check_no_fakes.sh

# pytest 종료 코드 5 = 테스트 0개. R0.1(뼈대만 있는 상태)에서만 정상이다
test:
	@uv run pytest -q -m "not gpu"; ec=$$?; \
	if [ $$ec -eq 5 ]; then echo "⚠ 테스트 0개 — R0.1 상태에서만 정상이다"; exit 0; fi; exit $$ec

check-gpu:
	uv run pytest -q -m gpu

## ── Label Studio ─────────────────────────────────────
ls-up:
	docker compose up -d label-studio

ls-down:
	docker compose down

## ── R0~R3: 데이터 ────────────────────────────────────
record:
	$(call need,record,R0.3)
	@test -n "$(API)" || { echo "API=naver|kakao|topis|anthropic"; exit 1; }
	$(PY) notice_ner.cli.record --api $(API)

fetch:
	@test -n "$(SRC)" || { echo "SRC=naver|articles|topis|klue|seoul_spatial|roads"; exit 1; }
	$(call need,fetch_$(SRC),R1.x·R2.x)
	$(PY) notice_ner.cli.fetch_$(SRC)

parse-smpa:
	$(call need,parse_smpa,R1.3b)
	$(PY) notice_ner.cli.parse_smpa

pool:
	$(call need,build_pool,R1.5)
	$(PY) notice_ner.cli.build_pool --version $(VER)

pool-peek:
	$(call need,pool_peek,R1.5)
	$(PY) notice_ner.cli.pool_peek --version $(VER) -n $(N) $(if $(REJECTED),--rejected,)

gaz:
	$(call need,build_gazetteer,R2.4)
	$(PY) notice_ner.cli.build_gazetteer

gaz-browse:
	$(call need,gaz_browse,R2.4)
	$(PY) notice_ner.cli.gaz_browse

gaz-map:
	$(call need,gaz_map,R2.4)
	$(PY) notice_ner.cli.gaz_map

iaa:
	$(call need,compare_annotators,R3.1)
	$(PY) notice_ner.cli.compare_annotators $(if $(PROJECT),--project $(PROJECT),)

preannotate:
	$(call need,preannotate,R3.2)
	$(PY) notice_ner.cli.preannotate --version $(VER)

ls-import:
	$(call need,ls_import,R3.2)
	$(PY) notice_ner.cli.ls_import --version $(VER)

ls-progress:
	$(call need,ls_progress,R3.3)
	$(PY) notice_ner.cli.ls_progress

export:
	$(call need,export_labels,R3.4)
	$(PY) notice_ner.cli.export_labels

split:
	$(call need,make_split,R3.4)
	$(PY) notice_ner.cli.make_split --version $(VER)

## ── R4: 실험 (val만) ─────────────────────────────────
train:
	$(need_exp)
	$(call need,train,R4.3)
	$(PY) notice_ner.cli.train --config configs/$(EXP).yaml

predict:
	$(need_exp)
	$(no_test_split)
	$(call need,predict,R4.2)
	$(PY) notice_ner.cli.predict --config configs/$(EXP).yaml --split $(SPLIT)

eval:
	$(need_exp)
	$(no_test_split)
	$(call need,evaluate,R4.0)
	$(PY) notice_ner.cli.evaluate --exp $(EXP) --split $(SPLIT)

report-table:
	$(call need,report_table,R4.0)
	$(PY) notice_ner.cli.report_table

## ── PC-4 · R4.7: 동결과 test (한 번) ────────────────
# freeze는 태우가 터미널에서 직접 실행한다 (CLAUDE.md §1.8)
freeze:
	$(need_exp)
	$(call need,freeze,R4.0)
	$(PY) notice_ner.cli.freeze --exp $(EXP)

test-run:
	$(need_exp)
	$(call need,evaluate,R4.0)
	@test -f experiments/$(EXP)/FROZEN.json || { echo "동결 안 됨 — 태우가 make freeze EXP=$(EXP) (PC-4)"; exit 1; }
	@if [ -f experiments/$(EXP)/metrics_test.json ] && [ -z "$(REASON)" ]; then \
	  echo "이미 test 평가됨 — 다시 하려면 REASON=\"사유\" (test_log.jsonl과 보고서에 남는다)"; exit 1; fi
	NOTICE_NER_TEST_UNLOCK=$(EXP) $(PY) notice_ner.cli.predict --config configs/$(EXP).yaml --split test,test_ood
	NOTICE_NER_TEST_UNLOCK=$(EXP) $(PY) notice_ner.cli.evaluate --exp $(EXP) --split test,test_ood $(if $(REASON),--rerun-reason "$(REASON)",)
