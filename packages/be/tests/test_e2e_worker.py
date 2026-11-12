"""T4.4 e2e — AI 워커 → 실제 Flask 앱(httpx WSGITransport, 소켓 없는 HTTP 왕복) → MySQL → /closures.

AI 와 BE 가 한 프로세스에 함께 올라오는 유일한 테스트 (패키지끼리는 import 안 한다 — 경계는 HTTP).
입력: 기록된 LLM 응답(recorded/llm 의 sentences 5문장, 재생만) + 카카오 기록 + 코스 GPX·시각표.
기대값은 2026-11-08 notice_v2 기록으로 확인한 값: 공지 후보 7(광화문 r01 1 + r04 3 + 여의도 3),
횡단보도 40(서울 전체 T6.9 — 여의도 3건이 붙는다), /closures 광화문 12:30 → 13, 15:30 → 37.
T6.1: 기록 돌발(OA-13315 2026-11-07 15:40, 53건) → 집회 후보 9 → 같은 횡단보도·겹치는 시각의
공지 후보에 topis_incident 근거, 받은 시각 = data_as_of, --loop 는 실패한 소스만 따로 센다
(닫힌 포트로 실제 연결 거부).
"""

import logging
import shutil
import time
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import shapely
import shapely.geometry
from alembic import command
from alembic.config import Config
from flask import Flask

from naru_ai.config import Settings as AISettings
from naru_ai.publish import CandidatePublisher, PublishError
from naru_ai.worker import IngestWorker
from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import (
    ClosureEvent,
    ClosureEventsResponse,
    FeatureCollection,
    Source,
    Status,
)

BE_DIR = Path(__file__).resolve().parents[1]
TOKEN = "naru-e2e-token"
GWANGHWAMUN = "126.965,37.555,126.990,37.580"
ACCINFO_1107 = "data/recorded/incident/20261107T154053_AccInfo.json"  # 11/7 15:40 수신, 53건
# 11/8 19:20 NoticeList — 볼 글 6건, 기록 재생으로 후보 0 (test_topis_feed). 운영 워커가 같은 폴더에
# 새 기록을 쌓으므로 '가장 최근'이 아니라 이 파일로 고정
TOPIS_1108 = "data/recorded/topis_notice/20261108T192013.json"
# TOPIS 통제지도 목록 11/9 08:37(T6.5, 6행) — 운영 워커가 같은 폴더에 새 목록을 쌓으므로 고정
TOPIS_MAP_1109 = "data/recorded/topis_web/20261109T083719_selectAccAllListASC.json"  # T6.5, 6행
# 버스 기록 재생은 T6.2 기록(11/7·11/8)까지만 — 운영 워커가 11/9 11:04 부터 bus/notice·incident 에
# 새 기록을 쌓는다. '가장 최근 기록' 재생이면 기대값이 날마다 바뀐다 (T6.9)
BUS_UNTIL = "2026-11-08T23:59:59+09:00"
# 서울경찰청 '오늘의 주요집회' 실제 PDF 3개(태우 2026-11-07 받음) — T6.6 은 임시 폴더로 복사
SMPA_RAW = Path("data/raw/notices/smpa")
SMPA_PDFS = [f"2611{d}) 오늘의 주요집회.pdf" for d in ("07(토", "08(일", "09(월")]


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
def quiet(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """운영 워커와 떨어진 설정 — 버스는 BUS_UNTIL 까지의 기록, 경찰청 inbox 는 빈 임시 폴더
    (운영 inbox 가 오늘 PDF 를 옮겨 두면 그날 sentences.jsonl 공지를 건너뛴다, T6.9)"""
    return {
        "NARU_BUS_RECORD_UNTIL": BUS_UNTIL,
        "NARU_SMPA_DIR": str(tmp_path_factory.mktemp("smpa")),
        "NARU_TOPIS_MAP_RECORD": TOPIS_MAP_1109,
    }


@pytest.fixture(scope="module")
def worker(app: Flask, quiet: dict[str, str]) -> IngestWorker:
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.test")
    publisher = CandidatePublisher("http://naru.test", TOKEN, client=http, backoff_s=0.0)
    return IngestWorker(AISettings(**quiet), publisher)  # client 없음 → 공지는 기록 재생만


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
    # 15 m 버퍼 안 — 서울 전체(T6.9)라 16구간 전부(test_app_candidates), 종로·중구 땐 183
    assert by_producer["course"].crosswalks_updated == 470
    notice = by_producer["notice"]
    assert notice.accepted == 7 and notice.review_required == 0
    # 광화문 r01 13 + r04 24, 서울 전체로 늘어난 3: 11/7 r06 의사당역 1 · 11/9 r01 여의도 2.
    # 11/9 r02 는 출발점(국회의사당역 2번출구) 하나라 30 m 안 횡단보도가 없어 0
    assert notice.crosswalks_updated == 40
    assert models.repo.count() == 470 + 40
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
    assert models.repo.count() == 470 + 40


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


def _worker(
    app: Flask, quiet: dict[str, str], **ai: str
) -> tuple[IngestWorker, CandidatePublisher]:
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.test")
    publisher = CandidatePublisher("http://naru.test", TOKEN, client=http, backoff_s=0.0)
    return IngestWorker(AISettings(**{**quiet, **ai}), publisher), publisher


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


def test_incidents_link_to_notices_on_same_crosswalks(
    app: Flask, quiet: dict[str, str], worker: IngestWorker
) -> None:
    worker.run_once()  # 코스·공지 (이미 있으면 멱등)
    w, publisher = _worker(app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1107)
    batch = w.incident_batch()
    assert batch.producer == "incident" and len(batch.candidates) == 9
    r = publisher.publish(batch)
    # 15 m 선 버퍼: 세종대로 시청역→숭례문 링크 4곳 두 번(07:00~16:00·15:00~17:00), 숭례문→시청역
    # 4곳(1109106), 사직로 경복궁역→사직공원 2곳 두 번 = 16. 서울 전체(T6.9)로 서초 1108983 9곳·
    # 여의대로 1108989 1곳이 더해져 26 (서초역 1109004·국회 1109079 는 링크 15 m 안 횡단보도 0)
    assert (r.accepted, r.review_required, r.crosswalks_updated) == (9, 0, 26)
    own, linked = _linked_at_1530(app)
    assert len(own) == 16 and {p["status"] for p in own} == {Status.confirmed}
    # r04 seg2(숭례문R → 광화문, 14곳)·seg1 끝점(2곳)이 돌발 링크 횡단보도(23254·40204·45236,
    # 숭례문 앞)와 겹쳐 후보 전체에 근거가 붙는다. seg3(→ 고용노동청 8곳)·r01(동화면세점 고리
    # 13곳)은 안 겹친다
    assert len(linked) == 16
    assert all("시의회~숭례문R" in str(p["reason"]) for p in linked)
    # r04 확신도 0.75 < 0.8 — 실제 근거가 붙어도 '예정' 그대로 (README 상태 표)
    assert {(p["status"], p["confidence"]) for p in linked} == {(Status.scheduled, 0.75)}


def test_notice_after_incident_gets_the_same_evidence(
    app: Flask, quiet: dict[str, str], worker: IngestWorker
) -> None:
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    w, publisher = _worker(app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1107)
    publisher.publish(w.incident_batch())  # 돌발이 먼저
    worker.run_once()  # 공지가 뒤에 와도 같은 근거가 붙는다
    own, linked = _linked_at_1530(app)
    assert (len(own), len(linked)) == (16, 16)


def _incident_as_of(app: Flask) -> datetime | None:
    resp = app.test_client().get("/closures/events")
    return ClosureEventsResponse.model_validate(resp.get_json()).data_as_of.topis_incident


def test_incident_receipt_is_data_as_of(app: Flask, quiet: dict[str, str]) -> None:
    w, publisher = _worker(app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1107)
    batch = w.incident_batch()
    publisher.publish(batch)
    first = _incident_as_of(app)
    time.sleep(1.1)  # 받은 시각은 초 단위로 저장
    again = publisher.publish(batch)  # 같은 원문 → 같은 batch_id — 멱등, 받은 시각만 새로
    second = _incident_as_of(app)
    assert again.batch_id == batch.batch_id and again.accepted == 9
    assert first is not None and second is not None and second > first
    assert abs((datetime.now(UTC) - second).total_seconds()) < 5


def test_loop_counts_failures_per_source(
    app: Flask, quiet: dict[str, str], caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    # 돌발만 live 로, 열린데이터광장 주소는 닫힌 포트 — 실제 연결 거부. 코스·공지는 실제 앱으로 간다
    # TOPIS 공지(T6.4)는 기록 재생 — 후보가 없어 아무것도 안 보내고 실패도 없다. 경찰청 PDF
    # inbox(T6.6)는 빈 임시 폴더 — 운영 inbox 의 PDF 를 테스트가 옮기면 안 된다. TOPIS 통제지도
    # (T7.3)는 기록 재생(quiet 의 11/9 목록) — 예정 집회 둘이 배치 하나, 10분마다(같은 내용이라
    # BE 멱등)
    loop, _ = _worker(
        app,
        quiet,
        NARU_INCIDENT_SOURCE="live",
        SEOUL_OPENDATA_KEY="naru-e2e-key",
        NARU_SEOUL_API_URL="http://127.0.0.1:9",
        NARU_TOPIS_RECORD=TOPIS_1108,
        NARU_SMPA_DIR=str(tmp_path / "smpa"),
    )
    t0 = datetime(2026, 11, 8, 9, 0, tzinfo=UTC)
    with caplog.at_level(logging.WARNING, logger="naru_ai.worker"):
        first = loop.tick(t0)
        early = loop.tick(t0 + timedelta(minutes=1))  # 아직 5분이 안 됐다
        second = loop.tick(t0 + timedelta(minutes=5))
        third = loop.tick(t0 + timedelta(minutes=10))
    assert [r.batch_id.split("-")[0] for r in first] == ["course", "notice", "topismap"]
    assert early == []
    assert [r.batch_id.split("-")[0] for r in second] == ["notice"]  # 코스는 1회
    assert [r.batch_id.split("-")[0] for r in third] == ["notice", "topismap"]
    fails = [r for r in caplog.records if r.getMessage() == "source failed"]
    assert [(r.levelname, r.__dict__["source"], r.__dict__["failures"]) for r in fails] == [
        ("WARNING", "incident", 1),
        ("WARNING", "incident", 2),
        ("ERROR", "incident", 3),  # 연속 3회
    ]


KST = timezone(timedelta(hours=9))


SEJONG_TOPIS = (
    "11/7(토) 도심 대규모 집회 대비 시내버스 정류소 임시폐쇄 및 무정차 안내"  # TOPIS 6300 제목
)


def test_bus_records_full_closures_only(
    app: Flask, quiet: dict[str, str], worker: IngestWorker
) -> None:
    """ADR-013 보류(태우 2026-11-09) — 버스는 전면 통제·마라톤만 기록하고 BE 로는 안 보낸다.
    11/7 공지 r01·r04·r06(차로 언급 없음)·TOPIS 돌발은 대상이 아니고, TOPIS 6300('숭례문R~대한문R
    왕복 전차로' — 파싱 lanes.scope full·one_side_full)만."""
    models: NaruModels = app.extensions["naru"]
    worker.run_once()  # 코스·공지 (이미 있으면 멱등)
    assert worker.full_closures == set()  # r01·r04·r06 은 차로 범위 없음(기록된 파싱)
    models.bus_intake.repo.truncate()
    w, publisher = _worker(
        app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1107, NARU_TOPIS_RECORD=TOPIS_1108
    )
    publisher.publish(w.incident_batch())
    batch = w.topis_batch(datetime(2026, 11, 7, 9, 0, tzinfo=KST))
    assert batch is not None
    publisher.publish(batch)
    assert [(r.split("\n")[0], at.hour) for r, at in w.full_closures] == [(SEJONG_TOPIS, 5)]
    at = datetime(2026, 11, 7, 15, 30, tzinfo=KST)
    # 6300 횡단보도 100 m 안 정류소가 많은 노선(raw OA-1095) 402·종로09·종로11
    targets = w.bus.targets(at)
    assert [(t.key[0].split("\n")[0], t.marathon, t.routes) for t in targets] == [
        (SEJONG_TOPIS, False, ("100100063", "100900003", "100900007"))
    ]
    # 기록 재생(11/8 18:38 까지): 종로09 5대·종로11 4대. 402 는 기록이 없어 건너뛴다(지어내지 않음)
    assert [(b.route_id, len(b.positions)) for b in w.bus.batches(at)] == [
        ("100900003", 5),
        ("100900007", 4),
    ]
    assert w.bus_round(at) == [] and models.bus_intake.repo.count() == 0  # 기록만(기본)
    # 17:40 — 6300 끝(17:00)+30분이 지나 창 밖
    assert w.bus.targets(datetime(2026, 11, 7, 17, 40, tzinfo=KST)) == []


def test_bus_records_marathon_sections(
    app: Flask, quiet: dict[str, str], worker: IngestWorker
) -> None:
    """3/15 07:45 — 시작 1시간 전 ~ 끝 30분 뒤인 마라톤 구간 11개(시작 가까운 순)의 근처 노선.
    NARU_BUS_RECORD_ONLY=0 이면 BE bus_positions 에만 쌓이고 통제 상태는 그대로."""
    models: NaruModels = app.extensions["naru"]
    worker.run_once()
    w, _ = _worker(app, quiet)
    at = datetime(2026, 3, 15, 7, 45, tzinfo=KST)
    targets = w.bus.targets(at)
    assert len(targets) == 11 and all(t.marathon for t in targets)
    assert [t.key[0] for t in targets[:2]] == [
        "marathon 3구간 시청 삼거리~고산자교~무교동 사거리",  # 07:44 시작
        "marathon 13구간 가락시장역 사거리~석촌역~잠실역 사거리",  # 07:35
    ]
    watched = w.bus.watched(at)
    assert len(watched) == 20 and {kind for _, kind in watched} == {"marathon"}
    # 기록 재생: 11/8 기록이 있는 5노선만 — 종로09 5·종로11 4·260 17·270 18·160 20 대
    expect = [("100900003", 5), ("100900007", 4), ("100100042", 17), ("100100046", 18)]
    expect.append(("100100033", 20))
    assert [(b.route_id, len(b.positions)) for b in w.bus.batches(at)] == expect
    models.bus_intake.repo.truncate()
    closures = models.repo.count()
    sending, _ = _worker(app, quiet, NARU_BUS_RECORD_ONLY="0")
    out = sending.bus_round(at)
    assert [(r.batch_id.split("-")[1], r.accepted) for r in out] == expect
    assert models.bus_intake.repo.count() == 64 and models.repo.count() == closures


def test_bus_targets_logged_on_change_and_every_10_minutes(
    app: Flask, quiet: dict[str, str], worker: IngestWorker, caplog: pytest.LogCaptureFixture
) -> None:
    """태우 11/9 — 버스 소스가 쉬는 건지 고장인지 로그로: 대상 수가 바뀔 때 + 10분에 한 번."""
    worker.run_once()
    w, _ = _worker(app, quiet)
    # 07:30~07:45 는 같은 11구간(6구간 08:46 시작은 07:46 부터 창 안). 17:45 는 다 끝남
    at = datetime(2026, 3, 15, 7, 30, tzinfo=KST)
    with caplog.at_level(logging.INFO, logger="naru_ai.signal.bus_poller"):
        for minutes in (0, 1, 10, 615):  # 07:30 · 07:31(그대로) · 07:40(10분) · 17:45(창 밖)
            w.bus_round(at + timedelta(minutes=minutes))
    lines = [r.__dict__ for r in caplog.records if r.getMessage() == "bus targets"]
    counts = [(x["marathon_events"], x["full_events"], x["routes"]) for x in lines]
    assert counts == [(11, 0, 20), (11, 0, 20), (0, 0, 0)]


ACCINFO_1109 = "data/recorded/incident/20261109T145523_AccInfo.json"  # 11/9 14:55 — 1109233·1109234


def _load_nov7(app: Flask, quiet: dict[str, str], at: str) -> ClosureEventsResponse:
    """11/7 기록(코스·공지 r01·r04·r06·돌발 15:40·TOPIS 6300)을 새로 싣고 그 시각 사건 (v0.14)."""
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    w, publisher = _worker(
        app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1107, NARU_TOPIS_RECORD=TOPIS_1108
    )
    w.run_once()
    publisher.publish(w.incident_batch())
    batch = w.topis_batch(datetime(2026, 11, 7, 9, 0, tzinfo=KST))
    assert batch is not None
    publisher.publish(batch)
    resp = app.test_client().get("/closures/events", query_string={"at": at})
    return ClosureEventsResponse.model_validate(resp.get_json())


def test_live_events_on_nov7(app: Flask, quiet: dict[str, str]) -> None:
    """T7.1 (ADR-014 A) — 11/7 15:30 지금 지도: [15:30, 11/9 00:00] 과 겹치는 사건 11.
    TOPIS 돌발 집회 7(0.9)·TOPIS 공지 6300(0.8, 같은 횡단보도 돌발 근거) 통제 중, 경찰청 공지
    r01(0.85)·r04(0.75)·r06(0.85)는 공지뿐이라 예정. 3/15 코스는 창 밖. 다시 실어도 id 그대로."""
    body = _load_nov7(app, quiet, "2026-11-07T15:30:00+09:00")
    got = Counter((e.source, e.status) for e in body.events)
    assert got == {
        (Source.incident, Status.confirmed): 7,
        (Source.topis, Status.confirmed): 1,
        (Source.smpa, Status.scheduled): 3,
    }
    r04 = next(e for e in body.events if e.reason.startswith("15:00~16:00 시의회~숭례문R"))
    assert (r04.id, r04.confidence) == ("2e930ec6deeb", 0.75)  # INTERFACE §3.1 예시와 같은 사건
    again = _load_nov7(app, quiet, "2026-11-07T15:30:00+09:00")
    assert sorted(e.id for e in again.events) == sorted(e.id for e in body.events)


def _crosswalk_points(app: Flask, ev: ClosureEvent, at: str) -> list[tuple[float, float]]:
    """그 사건 횡단보도 점 (/closures, 같은 reason)."""
    w, s, e, n = ev.bbox
    bbox = f"{w - 0.0005},{s - 0.0005},{e + 0.0005},{n + 0.0005}"
    fc = FeatureCollection.model_validate(
        app.test_client().get("/closures", query_string={"bbox": bbox, "at": at}).get_json()
    )
    pts = {
        (float(f.geometry.coordinates[0]), float(f.geometry.coordinates[1]))
        for f in fc.features
        if f.properties.reason == ev.reason and f.geometry.type == "Point"
    }
    return sorted(pts)


def _shape(ev: ClosureEvent) -> shapely.Geometry:
    assert ev.area is not None and ev.centroid is not None
    return shapely.geometry.shape(ev.area.model_dump(mode="json"))


def test_event_areas(app: Flask, quiet: dict[str, str]) -> None:
    """T7.2 (ADR-014 A) — 사건 구역 = 그 사건 후보가 횡단보도를 고른 모양(점 30 m·선 15 m·구간
    도로 경로 + 등급 버퍼)의 union, 2 m 단순화 + 2 m 여유, EPSG:4326. 사건마다 구역이 있고,
    횡단보도는 다 그 안, 중심은 구역 안(마라톤 구간처럼 휜 선도). 11/7 TOPIS 6300 은 구간 +
    숭례문 점 둘이 한 구역."""
    at = "2026-11-07T15:30:00+09:00"
    body = _load_nov7(app, quiet, at)
    assert len(body.events) == 11
    for ev in body.events:
        area = _shape(ev)
        pts = _crosswalk_points(app, ev, at)
        assert len(pts) == ev.crosswalks, ev.reason
        assert all(area.buffer(1e-6).contains(shapely.Point(p)) for p in pts), ev.reason
        assert area.contains(shapely.Point(ev.centroid)), ev.reason
    t6300 = next(e for e in body.events if e.source is Source.topis)
    # 구간(숭례문오거리→세종대로사거리) 6곳 + 숭례문 점 둘의 2곳 — 숭례문 2곳이 겹쳐 서로 다른 7곳
    assert t6300.crosswalks == 7 and t6300.area is not None and t6300.area.type == "Polygon"
    # 3/15 07:45 — 마라톤 16구간(코스 선 15 m)도 구역·중심
    seoul = app.test_client().get(
        "/closures/events", query_string={"at": "2026-03-15T07:45:00+09:00"}
    )
    course = ClosureEventsResponse.model_validate(seoul.get_json()).events
    assert len(course) == 16 and all(e.area is not None and e.centroid is not None for e in course)


def test_event_area_of_incident_line(app: Flask, quiet: dict[str, str]) -> None:
    """11/9 TOPIS 돌발 1109233 '국회대로 국회의사당앞→서강대교남단'(링크 선 15 m) — 횡단보도
    6곳이 구역 안."""
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    w, publisher = _worker(app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1109)
    publisher.publish(w.incident_batch())
    at = "2026-11-09T12:00:00+09:00"
    resp = app.test_client().get("/closures/events", query_string={"at": at})
    events = ClosureEventsResponse.model_validate(resp.get_json()).events
    ev = next(e for e in events if e.reason == "rally 국회대로 국회의사당앞→서강대교남단")
    area = _shape(ev)
    pts = _crosswalk_points(app, ev, at)
    assert len(pts) == ev.crosswalks == 6
    assert all(area.buffer(1e-6).contains(shapely.Point(p)) for p in pts)


def test_topis_map_scheduled_then_confirmed(app: Flask, quiet: dict[str, str]) -> None:
    """T7.3 (ADR-014 B) — TOPIS 통제지도 11/9 08:37 목록의 예정 집회 둘. 1109233
    (국회의사당앞~효자동삼거리 9.5 km 행진, 통제 도로 19 링크)은 시작 전 10:30 에 예정 0.85·
    횡단보도 75곳 — 아침에 경찰청 공지로는 0곳이던 행진이다. OA-13315 돌발 1109233(국회대로 한
    링크)이 오면 같은 횡단보도라 T6.1 연결로 12:00 통제 중. 1109234(강남대로, 통제 도로를 아직 안
    받아 대표 링크)는 14:00 전이라 예정."""
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    w, publisher = _worker(
        app, quiet, NARU_TOPIS_MAP_RECORD=TOPIS_MAP_1109, NARU_INCIDENT_RECORD=ACCINFO_1109
    )
    batch = w.topis_map_batch()
    assert batch is not None and [c.candidate_id for c in batch.candidates] == [
        "topismap-1109233-0",
        "topismap-1109234-0",
    ]
    publisher.publish(batch)

    def events(at: str) -> list[ClosureEvent]:
        resp = app.test_client().get("/closures/events", query_string={"at": at})
        return ClosureEventsResponse.model_validate(resp.get_json()).events

    before = events("2026-11-09T10:30:00+09:00")
    got = sorted((e.status.value, e.confidence, e.crosswalks) for e in before)
    assert got == [("scheduled", 0.85, 5), ("scheduled", 0.85, 75)]
    march = next(e for e in before if e.crosswalks == 75)
    assert march.source is Source.topis
    assert march.districts == ["마포구", "서대문구", "영등포구", "종로구"]
    publisher.publish(w.incident_batch())  # 돌발 1109233(11:00~15:30)·1109234(14:00~)
    after = {e.id: e for e in events("2026-11-09T12:00:00+09:00")}
    assert after[march.id].status is Status.confirmed  # 지도 예정 행진 전체가 통제 중
    rally = next(e for e in before if e.crosswalks == 5)
    assert after[rally.id].status is Status.scheduled


def test_bus_positions_need_token(app: Flask) -> None:
    resp = app.test_client().post("/internal/bus-positions", json={})
    assert resp.status_code == 401


def _refs(p: dict[str, object]) -> list[str]:
    evidence = p["evidence"]
    assert isinstance(evidence, list)
    return [str(e["ref"]) for e in evidence if isinstance(e, dict)]


def test_topis_notice_confirmed_by_incident(app: Flask, quiet: dict[str, str]) -> None:
    # T6.4: TOPIS 공지 6300(11/7 도심 집회, 창 05:00~17:00, 0.8) — 11/7 09:00 에 볼 글 중 후보가
    # 나오는 유일한 글(test_topis_feed). 같은 날 돌발과 같은 횡단보도·겹치는 시각이라 돌발 근거가
    # 붙고, 0.8 이상이라 창이 시작되면 '통제 중' (README 상태 표)
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    w, publisher = _worker(
        app, quiet, NARU_INCIDENT_RECORD=ACCINFO_1107, NARU_TOPIS_RECORD=TOPIS_1108
    )
    publisher.publish(w.incident_batch())
    batch = w.topis_batch(datetime(2026, 11, 7, 9, 0, tzinfo=KST))
    assert batch is not None
    r = publisher.publish(batch)
    # seg2 숭례문오거리→세종대로사거리 6곳 + 숭례문 점 둘(seg1·seg3 끝점, 30 m) 2곳씩
    assert (r.accepted, r.review_required, r.crosswalks_updated) == (3, 0, 10)

    def mine(at: str) -> list[dict[str, object]]:
        return [p for p in _features(app, at) if any("#topis-6300-" in ref for ref in _refs(p))]

    # OA-23081 교차로명 — 숭례문(23254·23247)·삼성본관(45236)·시청(40204)·덕수궁앞(40206)·
    # 프레스센터(42121)·세종대로사거리(23206): 세종대로
    crosswalks = {f"06-00000{n}" for n in (23254, 23247, 45236, 40204, 40206, 42121, 23206)}
    early, noon = mine("2026-11-07T04:30:00+09:00"), mine("2026-11-07T12:00:00+09:00")
    assert len(noon) == 10 and {str(p["crosswalk_id"]) for p in noon} == crosswalks
    assert {p["status"] for p in early} == {Status.scheduled}  # 창 05:00 전
    assert {(p["status"], p["confidence"]) for p in noon} == {(Status.confirmed, 0.8)}
    assert all(_kinds(p) == {"notice", "topis_incident"} for p in noon)


def test_smpa_inbox_pdfs_to_closures_then_archived(
    app: Flask, quiet: dict[str, str], tmp_path: Path
) -> None:
    # T6.6: 태우가 inbox 에 넣은 실제 PDF 3개(11/7 6행·11/8 3행·11/9 4행, 기준 작성 11/6
    # 18:00) — 행은 기록 notice_v2 smpa-<날짜>-r<행>-u202611061800 13건 재생 → 후보 10(0.7 미만
    # 2: 11/7 r05 0.65·11/8 r03 0.45). 보낸 뒤 <날짜>.pdf 로 옮기고, 옮긴 PDF 는 그날까지 다시
    # 본다(같은 배치)
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    smpa = tmp_path / "smpa"
    (smpa / "inbox").mkdir(parents=True)
    for name in SMPA_PDFS:
        shutil.copy2(SMPA_RAW / name, smpa / "inbox" / name)
    w, _ = _worker(app, quiet, NARU_SMPA_DIR=str(smpa))
    eve = datetime(2026, 11, 6, 20, 0, tzinfo=KST)
    first = w.smpa_round(eve)
    # 광화문 38(r01 13·r04 24·r05 1) + 서울 전체(T6.9)로 4: 11/7 r02 강남역 끝점 1·r06 1·11/9 r01 2
    assert [(r.accepted, r.review_required, r.crosswalks_updated) for r in first] == [(10, 2, 42)]
    assert sorted(p.name for p in smpa.glob("*.pdf")) == [f"2026110{d}.pdf" for d in (7, 8, 9)]
    assert not list((smpa / "inbox").glob("*.pdf"))
    assert len((smpa / "inbox_manifest.jsonl").read_text("utf-8").splitlines()) == 3
    again = w.smpa_round(eve)
    assert [r.batch_id for r in again] == [r.batch_id for r in first] and models.repo.count() == 42
    # 11/7 15:30 — r01 동화면세점 고리 13·r04 시의회~숭례문R 24(공지 e2e 와 같은 후보 ID·
    # 횡단보도 수) + r05 내자R~사직공원 의 끝점(사직공원) 1. 서초·여의도 행은 그래프 밖이라 0
    at = _features(app, "2026-11-07T15:30:00+09:00")
    rows = {ref.split("#")[1] for p in at for ref in _refs(p) if "#smpa-" in ref}
    assert len(at) == 38 and rows == {f"smpa-20261107-r0{i}-u202611061800" for i in (1, 4, 5)}
