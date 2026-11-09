"""IngestWorker — 코스·공지·돌발·TOPIS 공지·경찰청 PDF → 후보 → BE (ARCHITECTURE AI, T4.4·T6).

    uv run python -m naru_ai.worker --once          # 코스·공지 1회 (시연, make dev 로 BE 띄운 뒤)
    uv run python -m naru_ai.worker --loop          # 소스별: 코스 1회 · 공지·돌발 5분 · 버스 60초
    uv run python -m naru_ai.worker --loop --live   # 운영: + TOPIS 공지 10분, 새 글은 Claude 로
    uv run python -m naru_ai.worker --once --live   # 기록 없는 공지 문장을 Claude 로 (상한 안에서)

공지는 기본적으로 기록된 LLM 응답(data/recorded/llm)만 재생한다 — 키 없이도 돈다. 돌발은
NARU_INCIDENT_SOURCE=live 면 OA-13315 를 불러 원문을 기록하고, 아니면 기록을 재생한다. 버스는
전면 통제(공지 lanes.scope full·one_side_full)·마라톤 창에만 근처 노선 위치를 받아 기록만 한다 —
NARU_BUS_RECORD_ONLY=1(기본)이면 BE 로 안 보낸다(ADR-013 보류, NARU_BUS_SOURCE, 하루 상한).
TOPIS 공지(T6.4)는 NARU_TOPIS_SOURCE=live 면 NoticeList 를 10분마다 불러 기록하고,
기록 없는 글(새 글·고친 글)은 --live 일 때만 Claude 로 — 한 번 NARU_LLM_MAX_CALLS ·
하루 NARU_LLM_DAILY_CAP (ADR-011 D). 경찰청 '오늘의 주요집회' PDF(T6.6)는 태우가 smpa/inbox/ 에
넣으면 1분 안에 같은 방식으로 읽어 보내고 smpa/<집회 날짜>.pdf 로 옮긴다(SmpaInbox).
batch_id 는 내용(돌발은 원문) 해시라 같은 배치를 다시 보내도 BE 가 멱등 처리한다.
--loop 는 소스마다 따로 돈다 — 한 소스가 실패해도 다른 소스는 계속, 연속 3회 실패면 ERROR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from naru_ai.config import Settings
from naru_ai.ingest.course import CourseIngestor
from naru_ai.ingest.incident import IncidentIngestor, parse_accinfo
from naru_ai.ingest.topis_api import IncidentFeed, LinkBook, SeoulOpenApi
from naru_ai.llm.client import AnthropicClient, LLMRefusalError, LLMTruncatedError
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.log import configure_logging
from naru_ai.notice.candidates import CandidateBuilder, full_closure_stems
from naru_ai.notice.gazetteer import Gazetteer
from naru_ai.notice.parser import NoticeParser, ParsedNotice
from naru_ai.notice.resolver import KakaoRecords, Resolver
from naru_ai.notice.smpa_inbox import SmpaInbox
from naru_ai.notice.source import NoticeSentence
from naru_ai.notice.topis_feed import TopisNotices, post_sentences
from naru_ai.publish import CandidatePublisher, PublishError
from naru_ai.signal.bus_feed import BusApi, RoutePaths
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
COVERAGE_TTL_S = 600.0  # BE 범위를 다시 보는 간격 (T6.9)
# BE 가 배치에서 새로 만드는 것의 판 — 바꾸면 같은 후보도 새 배치라 다시 접수된다.
# t7.2: 사건 통제 구역(area)은 접수 때 만든다 — 배포 전에 받은 배치에도 구역이 생기게
INTAKE_VERSION = "t7.2"
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


@dataclass
class _Parsed:
    """_parse_notices 결과 — 후보와 문장 ID(파싱함·기다림), live·건너뜀 수."""

    candidates: list[ClosureCandidate] = field(default_factory=list)
    parsed: list[str] = field(default_factory=list)
    waiting: list[str] = field(default_factory=list)
    live: int = 0
    skipped: int = 0

    def counts(self) -> dict[str, int]:
        return {
            "live": self.live,
            "waiting": len(self.waiting),
            "skipped": self.skipped,
            "candidates": len(self.candidates),
        }


def live_budget(max_calls: int, daily_cap: int, saved_today: int) -> int:
    """한 번에 live 로 파싱할 수 — 한 번 상한과 하루 남은 수 중 작은 쪽, 음수면 0 (ADR-011 D)."""
    return max(0, min(max_calls, daily_cap - saved_today))


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
        self.client = client
        self._coverage: str | None = None  # BE 범위 — batch_id 에 섞는다(_scoped)
        self._coverage_at = 0.0
        self.parse_failed: set[str] = set()  # 이 프로세스에서 다시 안 부를 문장(버전) — TOPIS·smpa
        # 전면 통제 공지의 (발췌, 시작) — BE 사건(reason, 시작)과 같다. 버스 기록 대상
        # (ADR-013 보류)
        self.full_closures: set[tuple[str, datetime]] = set()
        self.live_budget = client.max_calls if client is not None else 0
        live_seoul = "live" in (settings.incident_source, settings.topis_source)
        seoul = (
            SeoulOpenApi(
                settings.seoul_opendata_key.get_secret_value(), recorded, settings.seoul_api_url
            )
            if live_seoul
            else None
        )
        api = seoul if settings.incident_source == "live" else None
        self.incidents = IncidentFeed(recorded, api, settings.incident_record)
        self.topis = TopisNotices(
            recorded,
            seoul if settings.topis_source == "live" else None,
            settings.topis_record,
            settings.topis_size,
        )
        self.smpa = SmpaInbox(settings.smpa_dir or raw / "notices" / "smpa")
        links = LinkBook(recorded / "links", api.fetch_link if api is not None else None)
        self.incident_ingestor = IncidentIngestor(links)
        bus_key = settings.data_go_kr_key.get_secret_value()
        if settings.bus_source == "live" and not bus_key:
            raise ValueError("DATA_GO_KR_KEY 없음 — 버스 live 를 쓸 수 없다")
        live_bus = settings.bus_source == "live"
        route_key = settings.data_go_kr_route_key.get_secret_value() or bus_key
        self.bus = BusPoller(
            RouteStops.load(_latest(raw, "bus_routes_*") / "OA-1095.xlsx"),
            BusApi(recorded, bus_key if live_bus else None, until=settings.bus_record_until),
            publisher.events,
            publisher.closures,
            lambda: self.full_closures,
            RoutePaths(raw, route_key if live_bus else None),
            per_event=settings.bus_routes_per_event,
            daily_cap=settings.bus_daily_cap,
        )
        self.sources = [
            _Source("course", None, lambda _: self._send(self.course_batch())),
            _Source(
                "notice",
                settings.notice_interval_s,
                lambda _: self._send(self.notice_batch(live=False)),
            ),
            _Source(
                "incident",
                settings.incident_interval_s,
                lambda _: self._send(self.incident_batch()),
            ),
            _Source(
                "topis", settings.topis_interval_s, lambda now: self._send(self.topis_batch(now))
            ),
            _Source("smpa", settings.smpa_interval_s, self.smpa_round),
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

    def notice_batch(self, live: bool = True) -> CandidateBatch | None:
        """sentences.jsonl(T0.5) 공지. live=False(--loop)면 재생만 — 옛 문장에 상한을 안 쓴다."""
        if not self.sentences_path.exists():
            log.warning("sentences missing", extra={"path": str(self.sentences_path)})
            return None
        rows: dict[str, dict[str, object]] = {}
        inbox = self.smpa.archived_dates()  # 경찰청 PDF inbox 가 읽은 날짜는 그쪽이 보낸다 (T6.9)
        for line in self.sentences_path.read_text("utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("source_type") == "smpa" and row.get("event_date") in inbox:
                    continue
                rows[str(row["sentence_id"])] = row
        recorded = [sid for sid in rows if self.recorder.exists(sid)]
        budget = self.live_budget if live else 0
        fresh = [sid for sid in rows if not self.recorder.exists(sid)][:budget]
        candidates: list[ClosureCandidate] = []
        for sid in [*recorded, *fresh]:
            parsed = self.parser.parse(NoticeEnvelope.from_sentence(rows[sid]))
            candidates.extend(self._built(parsed, self.builder.build(parsed)))
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

    def topis_batch(self, now: datetime | None = None) -> CandidateBatch | None:
        """TOPIS 통제·버스 공지(T6.4) — 볼 글을 파싱해 후보로 (_parse_notices)."""
        now = now or datetime.now(UTC)
        feed = self.topis.fetch()
        sentences = post_sentences(feed.raw, feed.received_at, now)
        ref = feed.path.as_posix()
        got = self._parse_notices(sentences, {s.sentence_id: ref for s in sentences}, now)
        log.info(
            "topis notices",
            extra={"posts": len(sentences), **got.counts(), "record": feed.path.name},
        )
        return self._notice_batch("topis", got)

    def smpa_round(self, now: datetime) -> list[Response]:
        """경찰청 PDF inbox (T6.6) — 볼 PDF 의 행 → 후보 → BE. inbox PDF 는 남은 행이 없고 보낸
        뒤에만 옮긴다(보내다 실패하면 그대로 두고 다음 번). 같은 날짜의 더 새 PDF 가 있으면 바로."""
        scan = self.smpa.scan(now)
        for path in scan.duplicates:
            self.smpa.set_aside(path, now)
        sentences = [s for pdf in scan.publish for s in pdf.sentences]
        refs = {s.sentence_id: pdf.dest.as_posix() for pdf in scan.publish for s in pdf.sentences}
        got = self._parse_notices(sentences, refs, now)
        log.info(
            "smpa notices",
            extra={
                "pdfs": [p.dest.name for p in scan.publish],
                "rows": len(sentences),
                **got.counts(),
                "inbox": len(scan.inbox),
                "duplicates": len(scan.duplicates),
            },
        )
        responses = self._send(self._notice_batch("smpa", got))
        for pdf in scan.inbox:
            ids = [s.sentence_id for s in pdf.sentences]
            if pdf in scan.publish and any(i in got.waiting for i in ids):
                continue  # 남은 행은 다음 번 live — 다 읽은 뒤 옮긴다
            self.smpa.archive(pdf, now, [i for i in ids if i in self.parse_failed])
        return responses

    def _parse_notices(
        self, sentences: list[NoticeSentence], refs: dict[str, str], now: datetime
    ) -> _Parsed:
        """문장 → 후보. 기록이 있으면 재생, 없으면 live: 한 번 max_calls 까지, 하루
        NARU_LLM_DAILY_CAP 까지(ADR-011 D), 남은 문장은 다음 번(waiting). 문장 하나가 실패하면
        (응답 검증·시각 형식·거절·잘림) 그 문장만 빼고 이 프로세스에서는 다시 안 부른다 — 기록이 안
        남는 거절·잘림을 다시 사지 않게. 고친 글·PDF 는 새 ID 다."""
        budget = self._live_budget(now)
        got = _Parsed()
        for s in sentences:
            if s.sentence_id in self.parse_failed:
                got.skipped += 1
                continue
            if not self.recorder.exists(s.sentence_id):
                if budget <= got.live:
                    got.waiting.append(s.sentence_id)
                    continue
                got.live += 1
            try:
                parsed = self.parser.parse(NoticeEnvelope.from_sentence(s.to_json()))
                got.candidates.extend(
                    self._built(parsed, self.builder.build(parsed, refs[s.sentence_id]))
                )
            except (ValueError, LLMRefusalError, LLMTruncatedError) as e:  # ValidationError 포함
                self.parse_failed.add(s.sentence_id)
                got.skipped += 1
                log.warning(
                    "notice sentence skipped",
                    extra={"sentence_id": s.sentence_id, "error": str(e)[:300]},
                )
                continue
            got.parsed.append(s.sentence_id)
        return got

    def _notice_batch(self, prefix: str, got: _Parsed) -> CandidateBatch | None:
        if not got.candidates:
            return None
        # 후보 ID 에는 글 버전이 없어(고친 글이 덮는다) 버전 붙은 문장 ID 를 같이 넣는다 —
        # 고친 글이 같은 후보 ID 를 내도 새 배치가 되게 (BE 는 같은 batch_id 를 건너뛴다)
        parts = [*got.parsed, *(c.candidate_id for c in got.candidates)]
        parts += [self.recorder.model, self.recorder.prompt_version]
        return CandidateBatch(
            batch_id=_batch_id(prefix, parts),
            produced_at=datetime.now(UTC),
            producer="notice",
            candidates=got.candidates,
        )

    def _live_budget(self, now: datetime) -> int:
        """이번에 live 로 파싱할 수 있는 수 (클라이언트가 없으면 0)."""
        if self.client is None:
            return 0
        self.client.calls = 0  # 한 번(10분)마다 새로 센다. 하루 상한은 오늘 남긴 기록 수로
        saved = self.recorder.saved_today(now)
        return live_budget(self.client.max_calls, self.settings.llm_daily_cap, saved)

    def _built(
        self, parsed: ParsedNotice, candidates: list[ClosureCandidate]
    ) -> list[ClosureCandidate]:
        """전면 통제(lanes.scope full·one_side_full) item 의 후보를 버스 기록 대상으로 적는다."""
        stems = full_closure_stems(parsed)
        for c in candidates:
            if stems and c.candidate_id.startswith(stems) and c.notice_ref and c.window.start:
                self.full_closures.add((c.notice_ref.excerpt, c.window.start))
        return candidates

    # --- 실행 ---------------------------------------------------------------------
    def _publish(self, batch: CandidateBatch) -> CandidateBatchResponse:
        response = self.publisher.publish(self._scoped(batch))
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

    def _scoped(self, batch: CandidateBatch) -> CandidateBatch:
        """batch_id 에 BE 범위(coverage)와 접수 판(INTAKE_VERSION)을 섞는다 — 범위가 바뀌면(T6.9
        서울 전체)·판이 바뀌면(T7.2 구역) 같은 후보도 새 배치라 BE 가 다시 접수한다. 둘 다 같으면
        그대로 멱등. 범위는 10분마다."""
        now = time.monotonic()
        if self._coverage is None or now - self._coverage_at > COVERAGE_TTL_S:
            try:
                box = self.publisher.events().coverage
            except httpx.HTTPError as e:  # BE 가 없으면 보내지도 못한다 — 같은 실패로
                raise PublishError(f"BE 범위를 못 받음: {e!r}") from e
            self._coverage, self._coverage_at = ",".join(f"{v:.5f}" for v in box), now
        prefix = batch.batch_id.split("-")[0]
        scoped = _batch_id(prefix, [batch.batch_id, self._coverage, INTAKE_VERSION])
        return batch.model_copy(update={"batch_id": scoped})

    def bus_round(self, now: datetime) -> list[Response]:
        """창 안 전면 통제·마라톤의 근처 노선 위치를 부른다(원문 기록). 기록만이면(기본) 여기서
        끝 — BE 로 안 보낸다. 볼 노선이 없으면 부르지 않는다."""
        batches = self.bus.batches(now)
        if self.settings.bus_record_only:
            return []
        return [self.publisher.publish_bus(b) for b in batches]

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
    exit_on_sigterm()
    worker.run_forever()
    return 0


def exit_on_sigterm() -> None:
    """systemd 가 멈출 때(SIGTERM) 정상 종료 0 — 아니면 uv 가 1 을 돌려 실패로 찍힌다(11/9)."""

    def stop(signum: int, _frame: object) -> None:
        log.info("worker stopping", extra={"signal": signum})
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)


if __name__ == "__main__":
    raise SystemExit(main())
