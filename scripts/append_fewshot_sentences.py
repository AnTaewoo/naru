"""프롬프트 few-shot 문장을 sentences.jsonl 에 추가 (T4.3 재평가, 태우 지시 2026-11-08).

notice_v2.md 의 `입력 {...}` 봉투(실제 공지 원문)를 읽어, 태우가 준 notices_v2 id 순서대로
sentences.jsonl 에 행을 더한다. 이미 있는 sentence_id 는 건너뛴다(멱등). 원문은 봉투 그대로.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ENVELOPE = re.compile(r"^입력 `(\{.*\})`\s*$")
SOURCE_URL = {  # sentences.jsonl 의 기존 행과 같은 출처 URL. news 는 봉투에 없어 빈 문자열
    "smpa": "https://www.smpa.go.kr/user/nd54882.do",
    "topis": "https://topis.seoul.go.kr/notice/openNoticeList.do",
}
DEFAULT_IDS = "N001,N006,N009,N011,N045,N049,N059,N067,N070,N099,N100"  # E1~E11 (태우, 2026-11-08)
# 봉투에 없던 출처 URL — 태우가 notices_v2 에서 확인해 준 값 (2026-11-08). 같은 기사 두 문장
FEWSHOT_SOURCE_URLS = {
    "N099": "https://www.econovill.com/news/articleView.html?idxno=756361",
    "N100": "https://www.econovill.com/news/articleView.html?idxno=756361",
}


def envelopes(prompt: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for line in prompt.read_text("utf-8").splitlines():
        m = ENVELOPE.match(line.strip())
        if m:
            out.append(json.loads(m.group(1)))
    return out


def fill_source_urls(sentences: Path) -> int:
    """이미 들어간 few-shot 행 중 source_url 이 빈 것을 FEWSHOT_SOURCE_URLS 로 채운다 (멱등)."""
    lines = sentences.read_text("utf-8").splitlines()
    out: list[str] = []
    filled = 0
    for line in lines:
        if line.strip():
            row = json.loads(line)
            url = FEWSHOT_SOURCE_URLS.get(row["sentence_id"])
            if url and not row.get("source_url"):
                row["source_url"] = url
                filled += 1
                line = json.dumps(row, ensure_ascii=False)
        out.append(line)
    if filled:
        sentences.write_text("\n".join(out) + "\n", "utf-8")
    return filled


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="few-shot 문장 → sentences.jsonl")
    ap.add_argument(
        "--prompt", type=Path, default=Path("packages/ai/naru_ai/llm/prompts/notice_v2.md")
    )
    ap.add_argument("--sentences", type=Path, default=Path("data/raw/notices/sentences.jsonl"))
    ap.add_argument("--ids", default=DEFAULT_IDS)
    args = ap.parse_args(argv)
    ids = [s.strip() for s in args.ids.split(",") if s.strip()]
    envs = envelopes(args.prompt)
    if len(envs) != len(ids):
        raise SystemExit(f"봉투 {len(envs)}개 ≠ id {len(ids)}개 — 예시 수와 id 목록이 다르다")
    existing = {
        json.loads(line)["sentence_id"]
        for line in args.sentences.read_text("utf-8").splitlines()
        if line.strip()
    }
    now = datetime.now(KST).isoformat(timespec="seconds")
    filled = fill_source_urls(args.sentences)
    added = 0
    with args.sentences.open("a", encoding="utf-8") as f:
        for n, (sid, env) in enumerate(zip(ids, envs, strict=True), start=1):
            if sid in existing:
                print(f"{sid}: 이미 있음 — 건너뜀")
                continue
            source = str(env["source"])
            row = {
                "sentence_id": sid,
                "notice_id": sid,
                "text": env["text"],
                "context_prev": None,
                "context_next": None,
                "source_type": source,
                "source_url": FEWSHOT_SOURCE_URLS.get(sid, SOURCE_URL.get(source, "")),
                "published_at": env["published_at"],
                "fetched_at": now,
                "event_date": env.get("event_date"),
                "fields": {"fewshot": f"E{n}", "prompt": args.prompt.stem},
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            added += 1
            print(f"{sid}: 추가 — {str(env['text'])[:60]}")
    print(f"추가 {added}행, 출처 URL 보강 {filled}행 → {args.sentences}")
    meta_path = args.sentences.with_name("sentences_meta.json")
    if meta_path.exists():
        meta = json.loads(meta_path.read_text("utf-8"))
        lines = args.sentences.read_text("utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line.strip()]
        meta["total"] = len(rows)
        meta["fewshot"] = {
            "prompt": args.prompt.stem,
            "sentences": sum(1 for r in rows if (r.get("fields") or {}).get("fewshot")),
            "note": "프롬프트 예시 원문(봉투 그대로). news 2행 출처 URL 은 태우 확인",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"meta total {meta['total']}, fewshot {meta['fewshot']['sentences']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
