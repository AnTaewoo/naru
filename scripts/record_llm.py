"""실제 Claude 호출을 기록 — `make record-llm NOTICES=<sentences.jsonl> LIMIT=3` (T4.1).

문장(sentence_id)마다 프롬프트 v<n> + parse_notice tool 로 한 번 호출하고
`data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json` 에 원문을 둔다.
이미 기록된 문장은 건너뛴다(--force 로 다시). 호출은 --limit 까지 (기본 3, 상한 10).
기본 문장은 few-shot 에 없는 경찰청 3행: 出 약칭 / `·` 연속 지점 / 방향어.
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

DEFAULT_IDS = ("smpa-20261107-r06", "smpa-20261109-r01", "smpa-20261109-r02")


def load_sentences(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[str(row["sentence_id"])] = row
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실제 Claude 호출 기록 (재생용)")
    ap.add_argument("--notices", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--ids", default=",".join(DEFAULT_IDS), help="sentence_id 쉼표 구분")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = Settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY 없음 — .env 에 채운다")
    limit = min(args.limit, settings.llm_max_calls_per_run)
    prompt = NoticePrompt.load(settings.prompt_version)
    tool = ToolSpec(TOOL_NAME, TOOL_DESCRIPTION, strict_input_schema())
    client = AnthropicClient(settings, max_calls=limit)
    recorder = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    sentences = load_sentences(args.notices)

    done = 0
    for sid in [s.strip() for s in args.ids.split(",") if s.strip()]:
        if sid not in sentences:
            raise SystemExit(f"{sid}: {args.notices} 에 없다")
        if recorder.exists(sid) and not args.force:
            print(f"{sid}: 이미 기록 — 건너뜀")
            continue
        if done >= limit:
            print(f"상한 {limit}회 — 멈춤")
            break
        env = NoticeEnvelope.from_sentence(sentences[sid])
        messages = prompt.build_messages(env)
        completion = client.complete_tool(prompt.system, messages, tool)
        parsed = NoticeOutput.model_validate(completion.input)  # 스키마 위반이면 여기서 터진다
        rec = recorder.save(sid, prompt.system, messages, tool, completion)
        done += 1
        print(
            f"{recorder.path(sid)}  items={len(parsed.items)} "
            f"kind={[i.kind for i in parsed.items]} impact={[i.impact for i in parsed.items]} "
            f"usage={rec.usage} {rec.elapsed_ms} ms"
        )
    print(f"호출 {done}회, 모델 {settings.llm_model}, 프롬프트 {settings.prompt_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
