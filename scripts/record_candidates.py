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

from naru_ai.ingest.course import CourseIngestor
from naru_contracts import CandidateBatch

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 후보 기록 (BE 테스트 입력)")
    ap.add_argument("--source", required=True, choices=["course", "notice", "bus"])
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--recorded", type=Path, default=Path("data/recorded"))
    args = ap.parse_args(argv)
    produced_at = datetime.now(KST)
    if args.source != "course":
        raise SystemExit(f"{args.source}: 아직 없음 — notice는 T4.2, bus는 P6")
    batch = course_batch(args.raw, produced_at)
    out = args.recorded / "candidates" / args.source / f"{produced_at:%Y%m%dT%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(batch.model_dump(mode="json"), ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    print(f"{out} — 후보 {len(batch.candidates)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
