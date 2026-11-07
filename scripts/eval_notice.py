"""공지 파서 평가 — 규칙 기준선 vs Claude(기록 재생). `uv run python scripts/eval_notice.py` (T4.3).

입력 ① 라벨 cases_v1.jsonl(34건) ② syntitan agent_questions.csv(163건, 합성).
Claude 쪽은 recorded/llm 재생만 — 기록이 없는 케이스는 오류로 센다 (먼저 `make record-llm` 로 기록).
결과: docs/eval/notice_<YYYYMMDD>.md + 표준출력.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from naru_ai.config import Settings
from naru_ai.llm.notice_schema import NoticeOutput
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.notice.eval import evaluate, robustness
from naru_ai.notice.eval_cases import load_cases, load_synthetic
from naru_ai.notice.eval_report import markdown_report, summarize
from naru_ai.notice.parser import NoticeParser
from naru_ai.notice.rule_baseline import RuleBaseline

KST = timezone(timedelta(hours=9))
SYNTHETIC_PUBLISHED_AT = (
    "2026-11-07T00:00:00+09:00"  # 합성 입력엔 게시 시각이 없다 — 기록 봉투와 같아야 한다
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공지 파서 평가 (재생만)")
    ap.add_argument("--cases", type=Path, default=Path("data/raw/notices/cases_v1.jsonl"))
    ap.add_argument(
        "--synthetic", type=Path, default=Path("data/recorded/syntitan/agent_questions.csv")
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    settings = Settings()
    recorder = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    parser = NoticeParser(settings, recorder)  # client 없음 → 기록 재생만
    baseline = RuleBaseline()

    def claude(env: NoticeEnvelope) -> NoticeOutput:
        parsed = parser.parse(env)
        return NoticeOutput(items=[pi.item for pi in parsed.items])

    cases = load_cases(args.cases)
    results = {
        "규칙 기준선": evaluate(cases, baseline.parse),
        f"Claude {settings.llm_model} / {settings.prompt_version}": evaluate(cases, claude),
    }
    accuracy = {name: (summarize(r), r) for name, r in results.items()}
    synthetic = load_synthetic(args.synthetic, SYNTHETIC_PUBLISHED_AT)
    robust = {"규칙 기준선": robustness(synthetic, baseline.parse)}
    notes_extra: list[str] = []
    if any(recorder.exists(env.sentence_id) for env in synthetic):
        robust[f"Claude {settings.llm_model}"] = robustness(synthetic, claude)
    else:
        notes_extra.append(
            f"합성 163건은 {settings.prompt_version} 으로 미기록 — Claude 견고성 행 없음 "
            "(이전 프롬프트 결과는 docs/eval/ 의 이전 표)"
        )

    today = datetime.now(KST)
    report = markdown_report(
        f"공지 파서 평가 {today:%Y-%m-%d}",
        accuracy,
        robust,
        notes=[
            f"정확도 케이스 {len(cases)}건, 견고성 입력 {len(synthetic)}건. Claude 는 기록 재생",
            "통과 기준: items 수 + impact·kind·segments(from/to/via 순서, 정규형 또는 원문)"
            "·window(분, approx ±10분)·toward·points. road·impact_reason 은 참고",
            "거절 케이스(expected items 0)는 예측에 blocks/unknown item 이 없으면 통과",
            "오류 = 기록 없음·스키마 위반·응답 거부",
            *notes_extra,
        ],
    )
    out = args.out or Path("docs/eval") / f"notice_{today:%Y%m%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, "utf-8")
    print(report)
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
