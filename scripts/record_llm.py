"""실제 Claude 호출을 기록 — `make record-llm NOTICES=<jsonl> LIMIT=3` (T4.1·T4.3).

입력 세 가지: sentences.jsonl(T0.5), cases_v1.jsonl(T0.6 라벨 — case_id 가 sentence_id), 또는
--csv data/recorded/syntitan/agent_questions.csv(합성, 견고성용 — source news, 게시 시각은 고정값).
문장마다 프롬프트 v<n> + parse_notice tool 로 한 번 호출하고
`data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json` 에 원문을 둔다.
이미 기록된 문장은 건너뛴다(--force 로 다시). 호출은 --limit 까지. 설정 상한(Task당 10회)을 넘기려면
--max-calls 를 명시한다 — 평가 세트 전체 기록(T4.3)처럼 한 번만 하는 일에.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from naru_ai.config import Settings
from naru_ai.llm.client import AnthropicClient, ToolSpec
from naru_ai.llm.notice_schema import TOOL_DESCRIPTION, TOOL_NAME, NoticeOutput, strict_input_schema
from naru_ai.llm.prompt import NoticeEnvelope, NoticePrompt
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.notice.eval_cases import load_cases, load_synthetic

DEFAULT_IDS = ("smpa-20261107-r06", "smpa-20261109-r01", "smpa-20261109-r02")
SYNTHETIC_PUBLISHED_AT = "2026-11-07T00:00:00+09:00"  # scripts/eval_notice.py 와 같은 값


def load_envelopes(notices: Path | None, csv_path: Path | None) -> dict[str, NoticeEnvelope]:
    out: dict[str, NoticeEnvelope] = {}
    if notices is not None:
        first = next((line for line in notices.read_text("utf-8").splitlines() if line.strip()), "")
        if '"case_id"' in first:
            for case in load_cases(notices):
                out[case.case_id] = case.envelope()
        else:
            for line in notices.read_text("utf-8").splitlines():
                if line.strip():
                    env = NoticeEnvelope.from_sentence(json.loads(line))
                    out[env.sentence_id] = env
    if csv_path is not None:
        for env in load_synthetic(csv_path, SYNTHETIC_PUBLISHED_AT):
            out[env.sentence_id] = env
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실제 Claude 호출 기록 (재생용)")
    ap.add_argument("--notices", type=Path, default=None, help="sentences.jsonl / cases_v1.jsonl")
    ap.add_argument("--csv", type=Path, default=None, help="syntitan agent_questions.csv")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--max-calls", type=int, default=None, help="설정 상한(10) 대신 — 평가 세트용")
    ap.add_argument("--ids", default="", help="쉼표 구분 id. all = 전부. 비면 기본 3문장")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.notices is None and args.csv is None:
        raise SystemExit("--notices 또는 --csv 가 필요하다")

    settings = Settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY 없음 — .env 에 채운다")
    cap = args.max_calls or settings.llm_max_calls_per_run
    limit = min(args.limit, cap)
    prompt = NoticePrompt.load(settings.prompt_version)
    tool = ToolSpec(TOOL_NAME, TOOL_DESCRIPTION, strict_input_schema())
    client = AnthropicClient(settings, max_calls=limit)
    recorder = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    envelopes = load_envelopes(args.notices, args.csv)
    if args.ids == "all":
        ids = list(envelopes)
    elif args.ids:
        ids = [s.strip() for s in args.ids.split(",") if s.strip()]
    else:
        ids = list(DEFAULT_IDS)

    done = 0
    usage_in = usage_out = 0
    for sid in ids:
        if sid not in envelopes:
            raise SystemExit(f"{sid}: 입력에 없다")
        if recorder.exists(sid) and not args.force:
            print(f"{sid}: 이미 기록 — 건너뜀")
            continue
        if done >= limit:
            print(f"상한 {limit}회 — 멈춤")
            break
        env = envelopes[sid]
        messages = prompt.build_messages(env)
        completion = client.complete_tool(prompt.system, messages, tool)
        parsed = NoticeOutput.model_validate(completion.input)  # 스키마 위반이면 여기서 터진다
        rec = recorder.save(sid, prompt.system, messages, tool, completion)
        done += 1
        usage_in += int(str(rec.usage.get("input_tokens", 0)))
        usage_out += int(str(rec.usage.get("output_tokens", 0)))
        print(
            f"{sid}: items={len(parsed.items)} kind={[i.kind for i in parsed.items]} "
            f"impact={[i.impact for i in parsed.items]} {rec.elapsed_ms} ms"
        )
    print(
        f"호출 {done}회 (input {usage_in} / output {usage_out} 토큰, 캐시 제외), "
        f"모델 {settings.llm_model}, 프롬프트 {settings.prompt_version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
