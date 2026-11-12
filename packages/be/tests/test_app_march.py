"""T7.16 — 행진 키프레임 API·행진 비용 라우팅 (실제 Flask 앱 + MySQL naru_test).

접수: 기록 공지 배치(notice_batch) — 11/7 r01 고리(50,000명, 12:00~16:00)는 대상, r04 는 갈라져
대상 아님. 사건 id 는 기록 응답 closure_events_catalog_1107_1530.json 과 같다:
r01 be5f89a4ebf3 · r04 2e930ec6deeb.
기대값은 test_march(프로필·P 손계산)와 같다.
"""

from __future__ import annotations

import gzip
import statistics
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from flask.testing import FlaskClient

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import CandidateBatch, ErrorBody, MarchResponse, RouteResponse, Status

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]
R01, R04 = "be5f89a4ebf3", "2e930ec6deeb"
KYOBO = "37.5709686446227,126.9779039768265"  # 카카오 '광화문교보빌딩' (lat,lng)
DAEHANMUN = "37.5650416322942,126.976542945622"
SEJONG = {"06-0000036391", "06-0000023206", "06-0000029520"}  # 고리 경로 s 185·205·225


@pytest.fixture(scope="module")
def app(notice_batch: CandidateBatch) -> Iterator[Flask]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")  # 0007 closure_events.march
    app = create_app(Settings(DATABASE_URL=base.test_database_url))
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    models.intake.accept(notice_batch)
    yield app
    models.repo.truncate()


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_march_keyframes_r01(app: Flask, client: FlaskClient) -> None:
    models: NaruModels = app.extensions["naru"]
    stored = models.repo.march_of(R01)
    assert stored is not None and len(stored.profile.s) == 13
    assert stored.profile.length_m == pytest.approx(1453.4, abs=1)
    resp = client.get(f"/closures/events/{R01}/march")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = MarchResponse.model_validate(resp.get_json())
    assert body.event_id == R01 and body.step_s == 60
    assert (body.window.start, body.window.end) == (
        datetime(2026, 11, 7, 12, 0, tzinfo=KST),
        datetime(2026, 11, 7, 16, 0, tzinfo=KST),
    )
    assert len(body.keyframes) == 241 and set(body.crosswalk_points) == set(stored.profile.s)
    first, last = body.keyframes[0], body.keyframes[-1]
    assert first.t == body.window.start and last.t == body.window.end
    assert all(first.crosswalks[cid] == 1.0 for cid in SEJONG)  # s < 선행 300 → 시작부터 막힘
    assert first.crosswalks["06-0000002104"] == 0.2  # 종로구청입구 s 1,036 → 하한
    assert len(first.samples) == 21 and first.radius_m == 0.0
    assert all(sum(len(s) for s in f.samples) <= 600 for f in body.keyframes)
    # 크기 — 4시간 241 키프레임 (보고용: gzip 전후)
    raw = resp.get_data()
    assert len(gzip.compress(raw)) < len(raw)
    # from·to 로 자른다, ETag 로 304
    part = client.get(
        f"/closures/events/{R01}/march",
        query_string={"from": "2026-11-07T15:30:00+09:00", "to": "2026-11-07T17:00:00+09:00"},
    )
    assert len(MarchResponse.model_validate(part.get_json()).keyframes) == 31
    again = client.get(
        f"/closures/events/{R01}/march", headers={"If-None-Match": resp.headers["ETag"]}
    )
    assert again.status_code == 304


def test_march_not_modeled_and_errors(app: Flask, client: FlaskClient) -> None:
    models: NaruModels = app.extensions["naru"]
    assert models.repo.march_of(R04) is None  # 갈라진 행진 — 구역은 있어도 프로필은 없다
    resp = client.get(f"/closures/events/{R04}/march")
    assert resp.status_code == 404
    err = ErrorBody.model_validate(resp.get_json()).error
    assert (err.code, err.field) == ("not_modeled", "event_id")
    assert client.get("/closures/events/000000000000/march").status_code == 404  # 없는 사건도 같다
    bad = client.get(f"/closures/events/{R01}/march", query_string={"from": "2026-11-07T12:00:00"})
    assert bad.status_code == 400
    assert ErrorBody.model_validate(bad.get_json()).error.field == "from"


def route(client: FlaskClient, at: str) -> RouteResponse:
    q = {"from": KYOBO, "to": DAEHANMUN, "depart_at": at}
    resp = client.get("/route", query_string=q)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return RouteResponse.model_validate(resp.get_json())


def test_route_blocks_march_whole_window(client: FlaskClient) -> None:
    # 12:00 시작·15:30 — 창 안 예정은 전 구역 +300초(태우 11/12, 군집은 표시만) → 세종대로사거리
    # 셋을 피해 돌아간다(816 m), 피한 곳 셋 scheduled. 군집 위치와 상관없이 같은 길
    start = route(client, "2026-11-07T12:00:00+09:00")
    assert {a.crosswalk_id for a in start.avoided} == SEJONG
    assert {a.status for a in start.avoided} == {Status.scheduled}
    # 15:30 — 군집은 고리를 거의 다 돌았지만 세종대로사거리 셋은 여전히 피한다(같은 시각 11/7 다른
    # 통제 — r04 시의회~숭례문R 등 — 횡단보도도 더 피한다)
    late_in = route(client, "2026-11-07T15:30:00+09:00")
    assert {a.crosswalk_id for a in late_in.avoided} >= SEJONG
    # 16:01 — 창 밖, 기준 경로(808 m)
    after = route(client, "2026-11-07T16:01:00+09:00")
    assert after.avoided == [] and after.distance_m < start.distance_m
    # 11:30 — 창 전(옛 규칙도 보통)
    before = route(client, "2026-11-07T11:30:00+09:00")
    assert before.avoided == [] and before.distance_m == after.distance_m


def test_route_latency_with_march(client: FlaskClient) -> None:
    """/route p50/p95 — 행진 사건이 있어도 T6.9(p95 5.1 ms)에서 크게 늘지 않는다."""
    route(client, "2026-11-07T13:00:00+09:00")  # 예열
    took: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        route(client, "2026-11-07T13:00:00+09:00")
        took.append((time.perf_counter() - t0) * 1000)
    p50, p95 = statistics.median(took), sorted(took)[int(len(took) * 0.95) - 1]
    print(f"\n/route 행진 13:00 p50 {p50:.1f} ms p95 {p95:.1f} ms")
    assert p95 < 500  # 느슨한 상한 — 숫자는 보고에
