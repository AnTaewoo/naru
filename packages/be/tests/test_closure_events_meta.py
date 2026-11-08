"""T5.9 — GET /closures/events 의 사건 칸(type·source·summary·notice)과 data_as_of.

INTERFACE §3.1 v0.12, ADR-012. 기록된 코스·공지 배치(recorded candidates/course·notice 최신)를
실제 경로(CandidateIntake)로 naru_test 에 넣는다. 기대값은 그 배치를 열어 확인한 값:
공지 r04 는 구간 3개·50,000명·태평로(게시 2026-11-06 18:00), r01 은 동화면세점 앞 고리
(종로1가사거리 경유)·세종대로, 코스는 시각표 게시 3/12 16:07.
"""

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import CandidateBatch, ClosureEventsResponse, ClosureType, Source

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]


def latest(recorded_dir: Path, source: str) -> CandidateBatch:
    path = sorted((recorded_dir / "candidates" / source).glob("*.json"))[-1]
    return CandidateBatch.model_validate(json.loads(path.read_text("utf-8")))


@pytest.fixture(scope="module")
def events(recorded_dir: Path) -> Iterator[ClosureEventsResponse]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")
    app = create_app(Settings(DATABASE_URL=base.test_database_url))
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    models.intake.accept(latest(recorded_dir, "course"))
    models.intake.accept(latest(recorded_dir, "notice"))
    resp = app.test_client().get("/closures/events")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    yield ClosureEventsResponse.model_validate(resp.get_json())
    models.repo.truncate()


def by_start(r: ClosureEventsResponse, start: datetime, prefix: str) -> list[object]:
    return [e for e in r.events if e.window.start == start and e.reason.startswith(prefix)]


def test_notice_event_carries_parser_summary_and_notice(events: ClosureEventsResponse) -> None:
    (rally,) = by_start(events, datetime(2026, 11, 7, 15, 0, tzinfo=KST), "15:00~16:00 시의회")
    assert (rally.type, rally.source) == (ClosureType.march, Source.smpa)
    assert rally.summary is not None
    assert [(s.from_, s.to) for s in rally.summary.segments] == [
        ("시의회", "숭례문오거리"),
        ("숭례문오거리", "광화문"),
        ("숭례문오거리", "고용노동청"),
    ]
    assert (rally.summary.reported_people, rally.summary.roads) == (50000, ["태평로"])
    assert rally.notice is not None and rally.notice.sentence_id == "smpa-20261107-r04"
    assert rally.notice.published_at == datetime(2026, 11, 6, 18, 0, tzinfo=KST)
    (loop,) = by_start(events, datetime(2026, 11, 7, 12, 0, tzinfo=KST), "12:00~16:00 동화면세점")
    assert loop.summary is not None
    assert [(s.from_, s.to, s.via) for s in loop.summary.segments] == [
        ("동화면세점 앞", "동화면세점 앞", ["종로1가사거리"])
    ]
    assert loop.summary.roads == ["세종대로"]


def test_course_event_has_no_summary(events: ClosureEventsResponse) -> None:
    (seg1,) = by_start(events, datetime(2026, 3, 15, 7, 20, tzinfo=KST), "marathon 1구간")
    assert (seg1.type, seg1.source, seg1.summary, seg1.notice) == (
        ClosureType.marathon,
        Source.course,
        None,
        None,
    )


def test_data_as_of_is_latest_evidence_per_source(events: ClosureEventsResponse) -> None:
    asof = events.data_as_of
    assert asof.smpa == datetime(2026, 11, 6, 18, 0, tzinfo=KST)  # 서울경찰청 공지 게시
    assert asof.course == datetime(2026, 3, 12, 16, 7, tzinfo=KST)  # 서울마라톤 시각표 게시
    assert asof.topis_incident is None and asof.topis_notice is None  # 아직 수집 안 함 (T6.1·T6.2)
