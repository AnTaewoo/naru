"""AI 실행 결과를 BE 테스트 입력으로 기록 — `make record-candidates SOURCE=course|notice|bus`.

실제 입력(GPX·시각표·기록된 공지)으로 Ingestor를 돌려 `data/recorded/candidates/<source>/<ts>.json`
에 CandidateBatch(JSON) 그대로 둔다. BE 테스트는 naru_ai 를 import 하지 않고 이 파일을 읽는다
(real-data-testing §4.2, T2.2·T4.2).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from naru_ai.config import Settings
from naru_ai.ingest.course import CourseIngestor
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.notice.candidates import CandidateBuilder
from naru_ai.notice.gazetteer import Gazetteer
from naru_ai.notice.parser import NoticeParser
from naru_ai.notice.resolver import KakaoRecords, Resolver
from naru_contracts import CandidateBatch, ClosureCandidate

KST = timezone(timedelta(hours=9))


def course_batch(raw: Path, produced_at: datetime) -> CandidateBatch:
    course = raw / "course"
    candidates = CourseIngestor().ingest(
        gpx=course / "seoul_marathon_2026.gpx",
        timetable=course / "seoul_marathon_2026_timetable.json",
        gpx_10km=course / "seoul_marathon_2026_10km.gpx",
    )
    return CandidateBatch(
        batch_id=f"course-{produced_at:%Y%m%d-%H%M%S}",
        produced_at=produced_at,
        producer="course",
        candidates=candidates,
    )


def notice_batch(raw: Path, recorded: Path, produced_at: datetime) -> CandidateBatch:
    """기록된 LLM 응답(재생) → 리졸버(교차로 사전 + 카카오 기록) → 후보. live 호출 없음 (T4.2)."""
    settings = Settings(NARU_DATA_DIR=raw.parent)
    recorder = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    ids = recorder.list_ids()
    if not ids:
        raise SystemExit(f"LLM 기록 없음: {recorder.dir} — make record-llm 먼저")
    rows: dict[str, dict[str, object]] = {}
    for line in (raw / "notices" / "sentences.jsonl").read_text("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[str(row["sentence_id"])] = row
    spatial = sorted(raw.glob("seoul_spatial_*"))[-1]
    nodelink = sorted(raw.glob("nodelink_seoul_*"))[-1]
    gazetteer = Gazetteer.load(spatial / "OA-23081.xlsx", nodelink / "link.gpkg")
    builder = CandidateBuilder(Resolver(gazetteer, KakaoRecords(recorded)))
    parser = NoticeParser(settings, recorder)
    candidates: list[ClosureCandidate] = []
    for sid in ids:
        parsed = parser.parse(NoticeEnvelope.from_sentence(rows[sid]))
        built = builder.build(parsed)
        print(f"{sid}: items {len(parsed.items)}, dropped {parsed.dropped_spans}, n={len(built)}")
        candidates.extend(built)
    return CandidateBatch(
        batch_id=f"notice-{produced_at:%Y%m%d-%H%M%S}",
        produced_at=produced_at,
        producer="notice",
        candidates=candidates,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 후보 기록 (BE 테스트 입력)")
    ap.add_argument("--source", required=True, choices=["course", "notice", "bus"])
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--recorded", type=Path, default=Path("data/recorded"))
    args = ap.parse_args(argv)
    produced_at = datetime.now(KST)
    if args.source == "course":
        batch = course_batch(args.raw, produced_at)
    elif args.source == "notice":
        batch = notice_batch(args.raw, args.recorded, produced_at)
    else:
        raise SystemExit(f"{args.source}: 아직 없음 — bus는 P6")
    out = args.recorded / "candidates" / args.source / f"{produced_at:%Y%m%dT%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(batch.model_dump(mode="json"), ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    print(f"{out} — 후보 {len(batch.candidates)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
