"""IngestWorker — 코스 1회 + 공지(5분)를 후보로 만들어 BE 에 보낸다 (ARCHITECTURE AI, T4.4).

    uv run python -m naru_ai.worker --once          # 시연용 1회 (make dev 로 BE 띄운 뒤)
    uv run python -m naru_ai.worker                 # 코스 1회, 공지 5분마다
    uv run python -m naru_ai.worker --once --live   # 기록 없는 공지 문장을 Claude 로 (상한 안에서)

공지는 기본적으로 기록된 LLM 응답(data/recorded/llm)만 재생한다 — 키 없이도 돈다. batch_id 는
내용 해시라 같은 배치를 다시 보내도 BE 가 멱등 처리한다. 돌발·버스·혼잡은 P6(해커톤 이후).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from naru_ai.config import Settings
from naru_ai.ingest.course import CourseIngestor
from naru_ai.llm.client import AnthropicClient
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.log import configure_logging
from naru_ai.notice.candidates import CandidateBuilder
from naru_ai.notice.gazetteer import Gazetteer
from naru_ai.notice.parser import NoticeParser
from naru_ai.notice.resolver import KakaoRecords, Resolver
from naru_ai.publish import CandidatePublisher
from naru_contracts import CandidateBatch, CandidateBatchResponse, ClosureCandidate

log = logging.getLogger(__name__)


def _latest(parent: Path, pattern: str) -> Path:
    dirs = sorted(p for p in parent.glob(pattern) if p.is_dir())
    if not dirs:
        raise FileNotFoundError(f"실데이터 없음: {parent}/{pattern} — make fetch 먼저")
    return dirs[-1]


def _batch_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha1("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


class IngestWorker:
    def __init__(
        self,
        settings: Settings,
        publisher: CandidatePublisher,
        client: AnthropicClient | None = None,
    ) -> None:
        self.settings = settings
        self.publisher = publisher
        raw = settings.data_dir / "raw"
        recorded = settings.data_dir / "recorded"
        self.course_dir = raw / "course"
        self.sentences_path = raw / "notices" / "sentences.jsonl"
        gazetteer = Gazetteer.load(
            _latest(raw, "seoul_spatial_*") / "OA-23081.xlsx",
            _latest(raw, "nodelink_seoul_*") / "link.gpkg",
            raw / "gazetteer" / "aliases.csv",
        )
        self.recorder = LLMRecorder(
            settings.recorded_llm_dir, settings.llm_model, settings.prompt_version
        )
        self.parser = NoticeParser(settings, self.recorder, client=client)
        self.builder = CandidateBuilder(Resolver(gazetteer, KakaoRecords(recorded)))
        self.live_budget = client.max_calls if client is not None else 0

    # --- 배치 ---------------------------------------------------------------------
    def course_batch(self) -> CandidateBatch | None:
        gpx = self.course_dir / "seoul_marathon_2026.gpx"
        timetable = self.course_dir / "seoul_marathon_2026_timetable.json"
        if not gpx.exists() or not timetable.exists():
            log.warning("course data missing", extra={"dir": str(self.course_dir)})
            return None
        gpx_10km = self.course_dir / "seoul_marathon_2026_10km.gpx"
        candidates = CourseIngestor().ingest(
            gpx, timetable, gpx_10km if gpx_10km.exists() else None
        )
        digest = hashlib.sha1(gpx.read_bytes() + timetable.read_bytes()).hexdigest()[:12]
        return CandidateBatch(
            batch_id=f"course-{digest}",
            produced_at=datetime.now(UTC),
            producer="course",
            candidates=candidates,
        )

    def notice_batch(self) -> CandidateBatch | None:
        if not self.sentences_path.exists():
            log.warning("sentences missing", extra={"path": str(self.sentences_path)})
            return None
        rows: dict[str, dict[str, object]] = {}
        for line in self.sentences_path.read_text("utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[str(row["sentence_id"])] = row
        recorded = [sid for sid in rows if self.recorder.exists(sid)]
        fresh = [sid for sid in rows if not self.recorder.exists(sid)][: self.live_budget]
        candidates: list[ClosureCandidate] = []
        for sid in [*recorded, *fresh]:
            parsed = self.parser.parse(NoticeEnvelope.from_sentence(rows[sid]))
            candidates.extend(self.builder.build(parsed))
        log.info(
            "notices parsed",
            extra={"recorded": len(recorded), "live": len(fresh), "candidates": len(candidates)},
        )
        if not candidates:
            return None
        return CandidateBatch(
            batch_id=_batch_id(
                "notice",
                [
                    *(c.candidate_id for c in candidates),
                    self.recorder.model,
                    self.recorder.prompt_version,
                ],
            ),
            produced_at=datetime.now(UTC),
            producer="notice",
            candidates=candidates,
        )

    # --- 실행 ---------------------------------------------------------------------
    def run_once(self, include_course: bool = True) -> list[CandidateBatchResponse]:
        out: list[CandidateBatchResponse] = []
        batches = [self.course_batch()] if include_course else []
        batches.append(self.notice_batch())
        for batch in batches:
            if batch is None:
                continue
            response = self.publisher.publish(batch)
            log.info(
                "batch published",
                extra={
                    "batch_id": response.batch_id,
                    "accepted": response.accepted,
                    "review_required": response.review_required,
                    "crosswalks_updated": response.crosswalks_updated,
                },
            )
            out.append(response)
        return out

    def run_forever(self) -> None:
        self.run_once(include_course=True)
        while True:
            time.sleep(self.settings.notice_interval_s)
            self.run_once(include_course=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Naru AI 워커 — 코스·공지 후보를 BE 로")
    ap.add_argument("--once", action="store_true", help="1회 실행 (시연)")
    ap.add_argument(
        "--live", action="store_true", help="기록 없는 공지 문장을 Claude 로 (상한 안에서)"
    )
    args = ap.parse_args(argv)
    configure_logging()
    settings = Settings()
    publisher = CandidatePublisher(settings.be_url, settings.internal_token)
    client = AnthropicClient(settings) if args.live else None
    worker = IngestWorker(settings, publisher, client)
    if args.once:
        responses = worker.run_once()
        for r in responses:
            print(f"{r.batch_id}: accepted {r.accepted}, crosswalks {r.crosswalks_updated}")
        return 0 if responses else 1
    worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
