"""T3.4a — create_app(naru_test).test_client(): 실제 도보망·실제 MySQL 로 GET /route, GET /closures.

코스 후보 상태(04:00 기준, 전부 scheduled)를 저장해 두고 시각별로 묻는다. 기대값은 T3.1~T3.3.
T5.4 — GET /closures/events (INTERFACE §3.1, ADR-010): 저장한 상태를 테스트가 직접
(reason, window) 로 묶은 것과 비교한다.
"""

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
from naru_contracts import (
    ClosureEventsResponse,
    ClosureState,
    ErrorBody,
    FeatureCollection,
    RouteResponse,
    Status,
)

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]
KYOBO = "37.5709686446227,126.9779039768265"  # 카카오 24020019 (lat,lng)
DAEHANMUN = "37.5650416322942,126.976542945622"  # 카카오 17582477
GWANGHWAMUN = "126.965,37.555,126.990,37.580"  # bbox minLng,minLat,maxLng,maxLat


def route_q(depart_at: str, src: str = KYOBO) -> dict[str, str]:
    return {"from": src, "to": DAEHANMUN, "depart_at": depart_at}


def closures_q(at: str, bbox: str = GWANGHWAMUN) -> dict[str, str]:
    return {"bbox": bbox, "at": at}


@pytest.fixture(scope="module")
def app(course_world: CourseWorld) -> Iterator[Flask]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")
    app = create_app(Settings(DATABASE_URL=base.test_database_url))
    models: NaruModels = app.extensions["naru"]
    assert models.settings.database_url == base.test_database_url
    models.repo.truncate()
    for candidate_id, states in course_world.by_candidate.items():
        models.repo.upsert_many(states, candidate_id)
    assert models.repo.count() == len(course_world.states)
    yield app
    models.repo.truncate()


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_route_during_closure(client: FlaskClient) -> None:
    resp = client.get("/route", query_string=route_q("2026-03-15T07:45:00+09:00"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = RouteResponse.model_validate(resp.get_json())
    assert "underpass" in {leg.kind.value for leg in body.legs}
    assert 835 < body.distance_m < 845 and 800 < body.baseline.distance_m < 830
    avoided = {a.crosswalk_id: a for a in body.avoided}
    assert {"06-0000023206", "06-0000036391"} <= set(avoided)
    assert avoided["06-0000023206"].status is Status.confirmed
    assert avoided["06-0000023206"].until == datetime(2026, 3, 15, 8, 8, tzinfo=KST)
    assert "지하보도" in resp.get_data(as_text=True)  # 한글 이스케이프 안 함 (ensure_ascii=False)
    # 통제 끝난 뒤: path == baseline
    resp = client.get("/route", query_string=route_q("2026-03-15T13:30:00+09:00"))
    body = RouteResponse.model_validate(resp.get_json())
    assert body.avoided == [] and body.distance_m == body.baseline.distance_m


def test_closures_restated_at_time(client: FlaskClient) -> None:
    resp = client.get("/closures", query_string=closures_q("2026-03-15T07:45:00+09:00"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    fc = FeatureCollection.model_validate(resp.get_json())
    by_id = {f.properties.crosswalk_id: f.properties for f in fc.features}
    # 저장은 scheduled 였지만 07:45 엔 1구간(07:20~08:08)이 confirmed 로 재판정된다
    assert by_id["06-0000023206"].status is Status.confirmed
    assert by_id["06-0000023206"].window["start"] == datetime(2026, 3, 15, 7, 20, tzinfo=KST)
    assert all(f.geometry.type == "Point" for f in fc.features)
    # 07:45 엔 진행 중(confirmed)과 08:45 안에 시작할 구간(scheduled)이 같이 나온다 (+60분 지평)
    assert {p.status for p in by_id.values()} == {Status.confirmed, Status.scheduled}
    # 07:00: 출발지 구간(05:00~)은 confirmed, 1구간(07:20~)은 scheduled — /route 와 같은 지평
    resp = client.get("/closures", query_string=closures_q("2026-03-15T07:00:00+09:00"))
    props = [f["properties"] for f in resp.get_json()["features"]]
    st = {p["crosswalk_id"]: p["status"] for p in props}
    assert st["06-0000036391"] == "confirmed" and st["06-0000023206"] == "scheduled"
    # 03:59: 아무것도 60분 안에 시작하지 않는다 (출발지 구간 05:00)
    resp = client.get("/closures", query_string=closures_q("2026-03-15T03:59:00+09:00"))
    assert resp.get_json()["features"] == []
    # 통제 전부 끝난 뒤 (종료+30분 지남) → 없음
    resp = client.get("/closures", query_string=closures_q("2026-03-15T13:30:00+09:00"))
    assert resp.get_json() == {"type": "FeatureCollection", "features": []}


def test_errors_follow_interface_section_6(client: FlaskClient) -> None:
    # 오프셋 없는 depart_at → 400 invalid_query, field depart_at
    resp = client.get("/route", query_string=route_q("2026-03-15T07:45:00"))
    assert resp.status_code == 400
    err = ErrorBody.model_validate(resp.get_json()).error
    assert err.code == "invalid_query" and err.field == "depart_at"
    # from 형식 오류 (Model 의 InvalidQueryError) → 400 field from
    resp = client.get("/route", query_string=route_q("2026-03-15T07:45:00+09:00", src="37.57"))
    assert resp.status_code == 400
    assert ErrorBody.model_validate(resp.get_json()).error.field == "from"
    # 필수 파라미터 없음 → 400, bbox 원소 수 틀림 → 400 field bbox
    assert client.get("/route").status_code == 400
    resp = client.get("/closures", query_string=closures_q("2026-03-15T07:45:00+09:00", "1,2,3"))
    assert resp.status_code == 400
    assert ErrorBody.model_validate(resp.get_json()).error.field == "bbox"
    # 없는 경로 → 404 not_found
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert ErrorBody.model_validate(resp.get_json()).error.code == "not_found"


EventKey = tuple[str, datetime | None, datetime | None]


def expected_events(
    states: list[ClosureState], bbox: str | None = None
) -> dict[EventKey, list[ClosureState]]:
    """입력 상태를 (reason, window) 로 직접 묶는다 — /closures/events 의 기대값.

    bbox 면 그 안의 상태만.
    """
    w, s, e, n = (float(x) for x in bbox.split(",")) if bbox else (-180.0, -90.0, 180.0, 90.0)
    groups: dict[EventKey, list[ClosureState]] = {}
    for st in states:
        if w <= st.lng <= e and s <= st.lat <= n:
            groups.setdefault((st.reason, st.window.start, st.window.end), []).append(st)
    return groups


def test_closure_events_group_by_reason_window(
    client: FlaskClient, course_world: CourseWorld
) -> None:  # §3.1, ADR-010
    resp = client.get("/closures/events")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = ClosureEventsResponse.model_validate(resp.get_json())  # 시작 늦은 순도 검증된다
    got = {(ev.reason, ev.window.start, ev.window.end): ev for ev in body.events}
    groups = expected_events(course_world.states)
    assert set(got) == set(groups)
    for key, states in groups.items():
        ev = got[key]
        assert ev.crosswalks == len({st.crosswalk_id for st in states})
        lngs, lats = [st.lng for st in states], [st.lat for st in states]
        assert ev.bbox == pytest.approx((min(lngs), min(lats), max(lngs), max(lats)), abs=1e-7)
        assert ev.approx is False
    # 1구간 — 개발 DB 를 같은 키로 SELECT 한 값과 같다 (2026-11-08): 횡단보도 6곳, 07:20~08:08
    seg1 = got[
        (
            "marathon 1구간 세종대로 사거리~숭례문 오거리",
            datetime(2026, 3, 15, 7, 20, tzinfo=KST),
            datetime(2026, 3, 15, 8, 8, tzinfo=KST),
        )
    ]
    assert seg1.crosswalks == 6
    assert resp.get_json()["events"][0]["window"]["start"].endswith("+09:00")
    # coverage (v0.10) — 보행망 bbox: recorded 출발·도착(교보빌딩·대한문)은 안,
    # 잠실(태우 실서버 요청)은 밖
    w, s, e, n = body.coverage
    for lat, lng in (map(float, KYOBO.split(",")), map(float, DAEHANMUN.split(","))):
        assert w <= lng <= e and s <= lat <= n
    assert not (w <= 127.0980 <= e and s <= 37.5133 <= n)
    assert "세종대로" in resp.get_data(as_text=True)  # 한글 그대로


def test_closure_events_bbox_and_errors(client: FlaskClient, course_world: CourseWorld) -> None:
    resp = client.get("/closures/events", query_string={"bbox": GWANGHWAMUN})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    inside = ClosureEventsResponse.model_validate(resp.get_json()).events
    groups = expected_events(course_world.states, GWANGHWAMUN)
    assert {(ev.reason, ev.window.start, ev.window.end) for ev in inside} == set(groups)
    counts = {(ev.reason, ev.window.start): ev.crosswalks for ev in inside}
    for (reason, start, _), states in groups.items():
        assert counts[(reason, start)] == len({st.crosswalk_id for st in states})
    # bbox 는 상태를 먼저 거른다 — 광화문 밖으로 이어지는 구간은 개수가 준다
    everything = ClosureEventsResponse.model_validate(client.get("/closures/events").get_json())
    full = {(ev.reason, ev.window.start): ev.crosswalks for ev in everything.events}
    assert any(n < full[key] for key, n in counts.items())
    # bbox 원소 수 틀림 → 400 field bbox (INTERFACE §6)
    resp = client.get("/closures/events", query_string={"bbox": "1,2,3"})
    assert resp.status_code == 400
    assert ErrorBody.model_validate(resp.get_json()).error.field == "bbox"
