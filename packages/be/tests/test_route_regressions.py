"""T5.5 — 라우터 정확성 회귀 3개 (ADR-011 A·그래프 밖).

좌표·시각은 태우가 2026-11-08 실서버(naru.antaewoo.com)에 직접 보낸 요청이고,
"이전" 값은 같은 날 공개 API 응답이다.

create_app(naru_test) 에 코스 상태(course_world, 04:00 기준 전부 scheduled)와 기록된 공지 배치
(recorded candidates/notice 최신 — 11/7 r01 12:00~16:00 확신도 0.85, r04 15:00~16:00 0.75 후보 셋)를
CandidateIntake 로 넣고 GET /route 를 부른다.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from conftest import CourseWorld
from flask.testing import FlaskClient

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import (
    CandidateBatch,
    ErrorBody,
    FeatureCollection,
    LegKind,
    RouteResponse,
    Status,
)

BE_DIR = Path(__file__).resolve().parents[1]
JAMSIL = ("37.5133,127.0980", "37.5145,127.1035")  # ① 잠실 — 이전: 16,942 m·14,118 s
SEJONG = ("37.56368,126.97230", "37.56368,126.98193")  # ② 세종대로 건너기 — 이전: 871 s, 피한 곳 0
GWANGHWAMUN = ("37.57148,126.97475", "37.57148,126.97982")  # ③ 광화문 — 이전·이후 같아야 한다


@pytest.fixture(scope="module")
def client(course_world: CourseWorld, recorded_dir: Path) -> Iterator[FlaskClient]:
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
    notice = sorted((recorded_dir / "candidates" / "notice").glob("*.json"))[-1]
    batch = CandidateBatch.model_validate(json.loads(notice.read_text("utf-8")))
    assert {c.candidate_id for c in batch.candidates} >= {
        "smpa-20261107-r01-i1-seg1",
        "smpa-20261107-r04-i1-seg2",
    }
    models.intake.accept(batch)
    yield app.test_client()
    models.repo.truncate()


def route(client: FlaskClient, od: tuple[str, str], at: str) -> RouteResponse:
    resp = client.get("/route", query_string={"from": od[0], "to": od[1], "depart_at": at})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return RouteResponse.model_validate(resp.get_json())


def test_1_out_of_coverage(client: FlaskClient) -> None:
    q = {"from": JAMSIL[0], "to": JAMSIL[1], "depart_at": "2026-03-15T10:00:00+09:00"}
    resp = client.get("/route", query_string=q)
    assert resp.status_code == 422
    err = ErrorBody.model_validate(resp.get_json()).error
    assert (err.code, err.field) == ("out_of_coverage", "from")
    resp = client.get("/route", query_string={**q, "from": GWANGHWAMUN[0]})  # 도착만 밖
    assert ErrorBody.model_validate(resp.get_json()).error.field == "to"


def test_2_scheduled_rally_inside_window_detours(client: FlaskClient) -> None:
    body = route(client, SEJONG, "2026-11-07T15:00:00+09:00")
    assert body.avoided, "11/7 15:00 집회(공지 창 안)를 피하지 않았다"
    assert {a.status for a in body.avoided} == {Status.scheduled}
    assert body.route.coordinates != body.baseline.route.coordinates
    assert body.duration_s > body.baseline.duration_s  # 페널티라 돌아가는 길이 더 길다
    # 피한 횡단보도는 그 시각 /closures 의 11/7 집회 횡단보도다
    fc = FeatureCollection.model_validate(
        client.get(
            "/closures",
            query_string={
                "bbox": "126.965,37.555,126.990,37.580",
                "at": "2026-11-07T15:00:00+09:00",
            },
        ).get_json()
    )
    rally = {
        f.properties.crosswalk_id
        for f in fc.features
        if f.properties.window["start"] is not None and f.properties.window["start"].day == 7
    }
    assert {a.crosswalk_id for a in body.avoided} <= rally
    # 같은 길 11:00 — r01(12:00~)·r04(15:00~) 시작 전이라 창 밖 → 원래 길 그대로
    early = route(client, SEJONG, "2026-11-07T11:00:00+09:00")
    assert early.avoided == []
    assert early.route.coordinates == early.baseline.route.coordinates


def test_3_gwanghwamun_underpass_unchanged(client: FlaskClient) -> None:
    body = route(client, GWANGHWAMUN, "2026-03-15T07:45:00+09:00")
    names = {leg.name for leg in body.legs if leg.kind is LegKind.underpass}
    assert names == {"광화문(세종문화회관) 지하보도"}
    # 2026-11-08 실서버 응답과 같다: 795.9 m, 확인 2곳
    assert 790 < body.distance_m < 800
    assert {(a.crosswalk_id, a.status) for a in body.avoided} == {
        ("06-0000046713", Status.confirmed),
        ("06-0000023200", Status.confirmed),
    }
