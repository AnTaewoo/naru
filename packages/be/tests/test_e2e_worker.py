"""T4.4 e2e — AI 워커 → 실제 Flask 앱(httpx WSGITransport, 소켓 없는 HTTP 왕복) → MySQL → /closures.

AI 와 BE 가 한 프로세스에 함께 올라오는 유일한 테스트 (패키지끼리는 import 안 한다 — 경계는 HTTP).
입력: 기록된 LLM 응답(recorded/llm 의 sentences 5문장, 재생만) + 카카오 기록 + 코스 GPX·시각표.
기대값은 2026-11-08 notice_v2 기록으로 확인한 값: 공지 후보 7(광화문 r01 1 + r04 3 + 여의도 3),
횡단보도 37(여의도 3건은 데모 범위 종로·중구 밖이라 0), /closures 광화문 12:30 → 13, 15:30 → 37.
T6.1: 기록 돌발(OA-13315 2026-11-07 15:40, 53건) → 집회 후보 9 → 같은 횡단보도·겹치는 시각의
공지 후보에 topis_incident 근거, 받은 시각 = data_as_of, --loop 는 실패한 소스만 따로 센다
(닫힌 포트로 실제 연결 거부).
"""

import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from flask import Flask

from naru_ai.config import Settings as AISettings
from naru_ai.publish import CandidatePublisher, PublishError
from naru_ai.worker import IngestWorker
from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import ClosureEventsResponse, FeatureCollection, Status

BE_DIR = Path(__file__).resolve().parents[1]
TOKEN = "naru-e2e-token"
GWANGHWAMUN = "126.965,37.555,126.990,37.580"
ACCINFO_1107 = "data/recorded/incident/20261107T154053_AccInfo.json"  # 11/7 15:40 수신, 53건


@pytest.fixture(scope="module")
def app() -> Iterator[Flask]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")
    app = create_app(Settings(DATABASE_URL=base.test_database_url, internal_token=TOKEN))
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    yield app
    models.repo.truncate()


@pytest.fixture(scope="module")
def worker(app: Flask) -> IngestWorker:
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.test")
    publisher = CandidatePublisher("http://naru.test", TOKEN, client=http, backoff_s=0.0)
    return IngestWorker(AISettings(), publisher)  # client 없음 → 공지는 기록 재생만


def notice_features(app: Flask, at: str) -> list[dict[str, object]]:
    resp = app.test_client().get("/closures", query_string={"bbox": GWANGHWAMUN, "at": at})
    fc = FeatureCollection.model_validate(resp.get_json())
    return [
        f.properties.model_dump()
        for f in fc.features
        if any(e["kind"] == "notice" for e in (f.properties.evidence or []))
    ]


def test_worker_once_publishes_course_and_notices(app: Flask, worker: IngestWorker) -> None:
    models: NaruModels = app.extensions["naru"]
    responses = worker.run_once()
    by_producer = {r.batch_id.split("-")[0]: r for r in responses}
    assert set(by_producer) == {"course", "notice"}
    assert by_producer["course"].accepted == 16  # 시각표 16구간 (T2.2)
    assert by_producer["course"].crosswalks_updated == 183  # 15 m 버퍼 안 (T3.4b)
    notice = by_producer["notice"]
    assert notice.accepted == 7 and notice.review_required == 0
    assert notice.crosswalks_updated == 37  # 광화문 r01 13 + r04 24. 여의도는 데모 범위 밖 → 0
    assert models.repo.count() == 183 + 37
    # 12:30 — 동화면세점 앞 → 종로1R → 동화면세점 앞 (12:00~16:00) 만. 공지만으론 scheduled
    at_1230 = notice_features(app, "2026-11-07T12:30:00+09:00")
    assert len(at_1230) == 13
    assert {p["status"] for p in at_1230} == {Status.scheduled}
    assert all("동화면세점 앞" in str(p["reason"]) for p in at_1230)
    # 15:30 — 시의회~숭례문R → 광화문·고용노동청 (15:00~16:00) 까지 겹친다
    at_1530 = notice_features(app, "2026-11-07T15:30:00+09:00")
    assert len(at_1530) == 37
    assert any("숭례문R" in str(p["reason"]) for p in at_1530)
    # 재실행: 같은 batch_id → BE 가 멱등 처리, 행 수 그대로
    again = worker.run_once()
    assert [(r.batch_id, r.accepted) for r in again] == [
        (r.batch_id, r.accepted) for r in responses
    ]
    assert models.repo.count() == 183 + 37


def test_publisher_rejects_without_token(app: Flask) -> None:
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.test")
    with pytest.raises(ValueError):
        CandidatePublisher("http://naru.test", "", client=http)
    bad = CandidatePublisher("http://naru.test", "wrong", client=http, backoff_s=0.0)
    worker = IngestWorker(AISettings(), bad)
    batch = worker.course_batch()
    assert batch is not None
    with pytest.raises(PublishError, match="401"):  # 4xx 는 재시도 없이 바로 실패
        bad.publish(batch)


def _worker(app: Flask, **ai: str) -> tuple[IngestWorker, CandidatePublisher]:
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.test")
    publisher = CandidatePublisher("http://naru.test", TOKEN, client=http, backoff_s=0.0)
    return IngestWorker(AISettings(**ai), publisher), publisher


def _features(app: Flask, at: str) -> list[dict[str, object]]:
    resp = app.test_client().get("/closures", query_string={"bbox": GWANGHWAMUN, "at": at})
    fc = FeatureCollection.model_validate(resp.get_json())
    return [f.properties.model_dump() for f in fc.features]


def _kinds(p: dict[str, object]) -> set[str]:
    return {str(e["kind"]) for e in p["evidence"] or []}  # type: ignore[attr-defined]


def _linked_at_1530(app: Flask) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """11/7 15:30 광화문 — (돌발 자기 통제, 돌발 근거가 붙은 공지 통제)."""
    at = _features(app, "2026-11-07T15:30:00+09:00")
    own = [p for p in at if "notice" not in _kinds(p) and "topis_incident" in _kinds(p)]
    notice = [p for p in at if "notice" in _kinds(p)]
    assert len(notice) == 37  # r01 13 + r04 24 (test_worker_once_… 와 같다)
    return own, [p for p in notice if "topis_incident" in _kinds(p)]


def test_incidents_link_to_notices_on_same_crosswalks(app: Flask, worker: IngestWorker) -> None:
    worker.run_once()  # 코스·공지 (이미 있으면 멱등)
    w, publisher = _worker(app, NARU_INCIDENT_RECORD=ACCINFO_1107)
    batch = w.incident_batch()
    assert batch.producer == "incident" and len(batch.candidates) == 9
    r = publisher.publish(batch)
    # 15 m 선 버퍼: 세종대로 시청역→숭례문 링크 4곳 두 번(07:00~16:00·15:00~17:00), 숭례문→시청역
    # 4곳(1109106), 사직로 경복궁역→사직공원 2곳 두 번. 서초·여의도·국회는 그래프 밖이라 0
    assert (r.accepted, r.review_required, r.crosswalks_updated) == (9, 0, 16)
    own, linked = _linked_at_1530(app)
    assert len(own) == 16 and {p["status"] for p in own} == {Status.confirmed}
    # r04 seg2(숭례문R → 광화문, 14곳)·seg1 끝점(2곳)이 돌발 링크 횡단보도(23254·40204·45236,
    # 숭례문 앞)와 겹쳐 후보 전체에 근거가 붙는다. seg3(→ 고용노동청 8곳)·r01(동화면세점 고리
    # 13곳)은 안 겹친다
    assert len(linked) == 16
    assert all("시의회~숭례문R" in str(p["reason"]) for p in linked)
    # r04 확신도 0.75 < 0.8 — 실제 근거가 붙어도 '예정' 그대로 (README 상태 표)
    assert {(p["status"], p["confidence"]) for p in linked} == {(Status.scheduled, 0.75)}


def test_notice_after_incident_gets_the_same_evidence(app: Flask, worker: IngestWorker) -> None:
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    w, publisher = _worker(app, NARU_INCIDENT_RECORD=ACCINFO_1107)
    publisher.publish(w.incident_batch())  # 돌발이 먼저
    worker.run_once()  # 공지가 뒤에 와도 같은 근거가 붙는다
    own, linked = _linked_at_1530(app)
    assert (len(own), len(linked)) == (16, 16)


def _incident_as_of(app: Flask) -> datetime | None:
    resp = app.test_client().get("/closures/events")
    return ClosureEventsResponse.model_validate(resp.get_json()).data_as_of.topis_incident


def test_incident_receipt_is_data_as_of(app: Flask) -> None:
    w, publisher = _worker(app, NARU_INCIDENT_RECORD=ACCINFO_1107)
    batch = w.incident_batch()
    publisher.publish(batch)
    first = _incident_as_of(app)
    time.sleep(1.1)  # 받은 시각은 초 단위로 저장
    again = publisher.publish(batch)  # 같은 원문 → 같은 batch_id — 멱등, 받은 시각만 새로
    second = _incident_as_of(app)
    assert again.batch_id == batch.batch_id and again.accepted == 9
    assert first is not None and second is not None and second > first
    assert abs((datetime.now(UTC) - second).total_seconds()) < 5


def test_loop_counts_failures_per_source(app: Flask, caplog: pytest.LogCaptureFixture) -> None:
    # 돌발만 live 로, 열린데이터광장 주소는 닫힌 포트 — 실제 연결 거부. 코스·공지는 실제 앱으로 간다
    loop, _ = _worker(
        app,
        NARU_INCIDENT_SOURCE="live",
        SEOUL_OPENDATA_KEY="naru-e2e-key",
        NARU_SEOUL_API_URL="http://127.0.0.1:9",
    )
    t0 = datetime(2026, 11, 8, 9, 0, tzinfo=UTC)
    with caplog.at_level(logging.WARNING, logger="naru_ai.worker"):
        first = loop.tick(t0)
        early = loop.tick(t0 + timedelta(minutes=1))  # 아직 5분이 안 됐다
        second = loop.tick(t0 + timedelta(minutes=5))
        third = loop.tick(t0 + timedelta(minutes=10))
    assert [r.batch_id.split("-")[0] for r in first] == ["course", "notice"]
    assert early == []
    assert [r.batch_id.split("-")[0] for r in second] == ["notice"]  # 코스는 1회
    assert [r.batch_id.split("-")[0] for r in third] == ["notice"]
    fails = [r for r in caplog.records if r.getMessage() == "source failed"]
    assert [(r.levelname, r.__dict__["source"], r.__dict__["failures"]) for r in fails] == [
        ("WARNING", "incident", 1),
        ("WARNING", "incident", 2),
        ("ERROR", "incident", 3),  # 연속 3회
    ]
