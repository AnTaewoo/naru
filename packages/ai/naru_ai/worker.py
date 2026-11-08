"""IngestWorker — 코스·공지·TOPIS 돌발을 후보로 만들어 BE 에 보낸다 (ARCHITECTURE AI, T4.4·T6.1).

    uv run python -m naru_ai.worker --once          # 코스·공지 1회 (시연, make dev 로 BE 띄운 뒤)
    uv run python -m naru_ai.worker --loop          # 소스별: 코스 1회 · 공지·돌발 5분 · 버스 60초
    uv run python -m naru_ai.worker --once --live   # 기록 없는 공지 문장을 Claude 로 (상한 안에서)

공지는 기본적으로 기록된 LLM 응답(data/recorded/llm)만 재생한다 — 키 없이도 돈다. 돌발은
NARU_INCIDENT_SOURCE=live 면 OA-13315 를 불러 원문을 기록하고, 아니면 기록을 재생한다. 버스(T6.2)는
공지 통제 창에만 근처 노선 위치를 받아 POST /internal/bus-positions (NARU_BUS_SOURCE, 하루 상한).
batch_id 는 내용(돌발은 원문) 해시라 같은 배치를 다시 보내도 BE 가 멱등 처리한다.
--loop 는 소스마다 따로 돈다 — 한 소스가 실패해도 다른 소스는 계속, 연속 3회 실패면 ERROR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from naru_ai.config import Settings
from naru_ai.ingest.course import CourseIngestor
from naru_ai.ingest.incident import IncidentIngestor, parse_accinfo
from naru_ai.ingest.topis_api import IncidentFeed, LinkBook, SeoulOpenApi
from naru_ai.llm.client import AnthropicClient
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.log import configure_logging
from naru_ai.notice.candidates import CandidateBuilder
from naru_ai.notice.gazetteer import Gazetteer
from naru_ai.notice.parser import NoticeParser
from naru_ai.notice.resolver import KakaoRecords, Resolver
from naru_ai.publish import CandidatePublisher
from naru_ai.signal.bus_feed import BusApi
from naru_ai.signal.bus_poller import BusPoller, RouteStops
from naru_contracts import (
    BusPositionBatchResponse,
    CandidateBatch,
    CandidateBatchResponse,
    ClosureCandidate,
)

log = logging.getLogger(__name__)


def _latest(parent: Path, pattern: str) -> Path:
    dirs = sorted(p for p in parent.glob(pattern) if p.is_dir())
    if not dirs:
        raise FileNotFoundError(f"실데이터 없음: {parent}/{pattern} — make fetch 먼저")
    return dirs[-1]


FAIL_ALERT = 3  # 한 소스가 연속으로 이만큼 실패하면 ERROR (T6.1)
Response = CandidateBatchResponse | BusPositionBatchResponse


@dataclass
class _Source:
    """--loop 의 소스 하나 — run(now) 가 만들고 보내 응답을 돌려준다. every_s None = 성공까지만."""

    name: str
    every_s: int | None
    run: Callable[[datetime], list[Response]]
    next_at: datetime | None = None
    failures: int = 0
    done: bool = False


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
        api = (
            SeoulOpenApi(
                settings.seoul_opendata_key.get_secret_value(), recorded, settings.seoul_api_url
            )
            if settings.incident_source == "live"
            else None
        )
        self.incidents = IncidentFeed(recorded, api, settings.incident_record)
        links = LinkBook(recorded / "links", api.fetch_link if api is not None else None)
        self.incident_ingestor = IncidentIngestor(links)
        bus_key = settings.data_go_kr_key.get_secret_value()
        if settings.bus_source == "live" and not bus_key:
            raise ValueError("DATA_GO_KR_KEY 없음 — 버스 live 를 쓸 수 없다")
        self.bus = BusPoller(
            RouteStops.load(_latest(raw, "bus_routes_*") / "OA-1095.xlsx"),
            BusApi(recorded, bus_key if settings.bus_source == "live" else None),
            publisher.events,
            publisher.closures,
            settings.bus_routes_per_event,
            settings.bus_daily_cap,
        )
        self.sources = [
            _Source("course", None, lambda _: self._send(self.course_batch())),
            _Source(
                "notice", settings.notice_interval_s, lambda _: self._send(self.notice_batch())
            ),
            _Source(
                "incident",
                settings.incident_interval_s,
                lambda _: self._send(self.incident_batch()),
            ),
            _Source("bus", settings.bus_interval_s, self.bus_round),
        ]

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

    def incident_batch(self) -> CandidateBatch:
        """TOPIS 돌발 — 범위 안 집회가 없어도 빈 배치를 보낸다(수신 시각이 data_as_of 가 된다)."""
        feed = self.incidents.fetch()
        rows = parse_accinfo(feed.raw)
        candidates = self.incident_ingestor.build(rows, feed.path.as_posix(), feed.received_at)
        log.info(
            "incidents",
            extra={"rows": len(rows), "candidates": len(candidates), "record": feed.path.name},
        )
        return CandidateBatch(
            batch_id=_batch_id("incident", [feed.raw]),  # 원문 해시 — 같은 내용이면 BE 가 멱등
            produced_at=datetime.now(UTC),
            producer="incident",
            candidates=candidates,
        )

    # --- 실행 ---------------------------------------------------------------------
    def _publish(self, batch: CandidateBatch) -> CandidateBatchResponse:
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
        return response

    def _send(self, batch: CandidateBatch | None) -> list[Response]:
        return [] if batch is None else [self._publish(batch)]

    def bus_round(self, now: datetime) -> list[Response]:
        """창 안 공지 통제의 근처 노선 위치 → BE (T6.2). 볼 노선이 없으면 부르지 않는다."""
        return [self.publisher.publish_bus(b) for b in self.bus.batches(now)]

    def run_once(self, include_course: bool = True) -> list[CandidateBatchResponse]:
        batches = [self.course_batch()] if include_course else []
        batches.append(self.notice_batch())
        return [self._publish(b) for b in batches if b is not None]

    def tick(self, now: datetime) -> list[Response]:
        """--loop 한 바퀴: 때가 된 소스만 돌린다. 실패는 그 소스에만 남기고 다음 소스로 간다."""
        out: list[Response] = []
        for src in self.sources:
            if src.done or (src.next_at is not None and now < src.next_at):
                continue
            retry_s = src.every_s or self.settings.notice_interval_s
            try:
                out.extend(src.run(now))
            except Exception as exc:  # 한 소스의 실패가 다른 소스를 막지 않는다 (T6.1)
                src.failures += 1
                level = logging.ERROR if src.failures >= FAIL_ALERT else logging.WARNING
                log.log(
                    level,
                    "source failed",
                    extra={"source": src.name, "failures": src.failures, "error": repr(exc)},
                )
                src.next_at = now + timedelta(seconds=retry_s)
                continue
            src.failures = 0
            src.done = src.every_s is None
            src.next_at = now + timedelta(seconds=retry_s)
        return out

    def run_forever(self) -> None:
        while True:
            self.tick(datetime.now(UTC))
            now = datetime.now(UTC)
            waits = [
                (s.next_at - now).total_seconds()
                for s in self.sources
                if not s.done and s.next_at is not None
            ]
            time.sleep(min(60.0, max(1.0, min(waits, default=60.0))))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Naru AI 워커 — 코스·공지·돌발 후보를 BE 로")
    ap.add_argument("--once", action="store_true", help="코스·공지 1회 (시연)")
    ap.add_argument("--loop", action="store_true", help="소스별 주기 실행 (운영, 기본값)")
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
