"""T7.17 — 공개 GeoJSON 피드 GET /closures/feed (실제 Flask 앱 + MySQL naru_test).

접수: 코스 상태(course_world, 3/15) + 기록 공지 배치(notice_batch — 11/7 r01 행진 모델 대상).
기대값은 같은 저장소·엔진 조회(active_at·events)와 맞춘다 — 피드는 새 판정이 아니라 같은 조회의
다른 표현. 11/7 13:00 에 걸린 사건은 r01 하나(12:00~16:00): 횡단보도 13, 세종대로사거리 P 1.0·
종로구청입구 0.2(test_march).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from conftest import CourseWorld
from flask import Flask
from flask.testing import FlaskClient

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_be.models.domain.feed import RateLimiter
from naru_contracts import CandidateBatch, ErrorBody, FeedCollection, Status

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]
WORLD = (-180.0, -90.0, 180.0, 90.0)
R01 = "be5f89a4ebf3"


@pytest.fixture(scope="module")
def app(course_world: CourseWorld, notice_batch: CandidateBatch) -> Iterator[Flask]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")
    app = create_app(Settings(DATABASE_URL=base.test_database_url))
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    for candidate_id, states in course_world.by_candidate.items():
        models.repo.upsert_many(states, candidate_id)
    models.intake.accept(notice_batch)
    yield app
    models.repo.truncate()


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def feed(client: FlaskClient, at: str) -> tuple[FeedCollection, dict[str, str]]:
    resp = client.get("/closures/feed", query_string={"at": at})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return FeedCollection.model_validate(resp.get_json()), dict(resp.headers)


def test_feed_march_day(app: Flask, client: FlaskClient) -> None:
    at = "2026-11-07T13:00:30+09:00"
    fc, headers = feed(client, at)
    assert fc.at == datetime(2026, 11, 7, 13, 0, tzinfo=KST)  # 분 단위로 내림
    assert fc.generated_at.utcoffset() is not None and "OA-23081" in fc.attribution
    kinds = [f.properties.kind for f in fc.features]
    assert kinds.count("area") == 1 and kinds.count("march_path") == 1
    crosswalks = [f for f in fc.features if f.properties.kind == "crosswalk"]
    assert len(crosswalks) == 13 and {f.properties.event_id for f in crosswalks} == {R01}
    by_id = {f.properties.crosswalk_id: f.properties for f in crosswalks}
    sejong, jongno = by_id["06-0000036391"], by_id["06-0000002104"]
    assert (sejong.name, sejong.status, sejong.p) == ("세종대로사거리", Status.scheduled, 1.0)
    assert (jongno.name, jongno.p) == ("종로구청입구", 0.2)
    assert sejong.type == "march" and sejong.source == "smpa" and sejong.confidence == 0.85
    assert sejong.start == datetime(2026, 11, 7, 12, 0, tzinfo=KST)
    path = next(f for f in fc.features if f.properties.kind == "march_path")
    models: NaruModels = app.extensions["naru"]
    stored = models.repo.march_of(R01)
    assert stored is not None and path.geometry.type == "LineString"
    assert len(path.geometry.coordinates) == len(stored.profile.path)
    assert headers["Cache-Control"] == "public, max-age=60"
    assert headers["Access-Control-Allow-Origin"] == "*"
    # 같은 분이면 캐시 — 같은 ETag, If-None-Match 면 304
    again = client.get("/closures/feed", query_string={"at": "2026-11-07T13:00:59+09:00"})
    assert again.headers["ETag"] == headers["ETag"]
    not_modified = client.get(
        "/closures/feed", query_string={"at": at}, headers={"If-None-Match": headers["ETag"]}
    )
    assert not_modified.status_code == 304


def test_feed_marathon_matches_closures(app: Flask, client: FlaskClient) -> None:
    """3/15 07:45 — 피드의 (사건, 횡단보도)는 /closures 가 보는 상태 전부와 같고, 판정도 같다."""
    models: NaruModels = app.extensions["naru"]
    at = datetime(2026, 3, 15, 7, 45, tzinfo=KST)
    fc, _ = feed(client, at.isoformat())
    states = models.engine.restate(models.repo.active_at(at, WORLD), at)
    pairs = {(st.reason, st.crosswalk_id) for st in states}
    got = {
        (f.properties.event, f.properties.crosswalk_id)
        for f in fc.features
        if f.properties.kind == "crosswalk"
    }
    assert got == pairs and len(pairs) > 100
    worst = {}
    for st in states:
        key = (st.reason, st.crosswalk_id)
        worst[key] = st.status if key not in worst or st.status is Status.confirmed else worst[key]
    for f in fc.features:
        if f.properties.kind == "crosswalk":
            assert f.properties.status is worst[(f.properties.event, f.properties.crosswalk_id)]
            assert f.properties.p is None  # 마라톤은 행진 모델 대상이 아니다
    # 1구간 세종대로사거리 — 07:45 통제 중 (test_routers)
    leg1 = next(
        f.properties
        for f in fc.features
        if f.properties.crosswalk_id == "06-0000023206" and "1구간" in f.properties.event
    )
    assert leg1.status is Status.confirmed and leg1.event_id == "adaea2f4cc02"
    # 사건 수 = /closures/events?at= 의 사건 수
    events = client.get(
        "/closures/events",
        query_string={"at": at.isoformat(), "from": at.isoformat(), "to": at.isoformat()},
    ).get_json()["events"]
    assert {f.properties.event_id for f in fc.features} == {e["id"] for e in events}


def test_feed_errors_and_rate_limit(client: FlaskClient) -> None:
    bad = client.get("/closures/feed", query_string={"at": "2026-11-07T13:00:00"})
    assert bad.status_code == 400
    assert ErrorBody.model_validate(bad.get_json()).error.field == "at"
    assert client.get("/closures/feed").status_code == 200  # at 없으면 지금
    # 다른 IP 로 61번째 — 429 rate_limited (토큰 통 60/분)
    env = {"REMOTE_ADDR": "203.0.113.7"}
    for _ in range(60):
        assert client.get("/closures/feed", environ_base=env).status_code == 200
    limited = client.get("/closures/feed", environ_base=env)
    assert limited.status_code == 429
    assert ErrorBody.model_validate(limited.get_json()).error.code == "rate_limited"
    # X-Forwarded-For 첫 값이 열쇠 (nginx 뒤)
    other = client.get("/closures/feed", headers={"X-Forwarded-For": "198.51.100.3, 10.0.0.1"})
    assert other.status_code == 200
    # 토큰 통: 1초 뒤 1개 보충
    rl = RateLimiter(60)
    for _ in range(60):
        assert rl.allow("k", 0.0)
    assert not rl.allow("k", 0.0) and rl.allow("k", 1.0) and not rl.allow("k", 1.0)
