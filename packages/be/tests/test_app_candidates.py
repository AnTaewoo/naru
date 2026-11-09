"""T3.4b — POST /internal/candidates: 토큰, 기록된 코스 배치 → 202 → /route 가 피함, 재전송 멱등.

실제 MySQL(naru_test) + 실제 도보망. 배치는 data/recorded/candidates/course/ 최신 파일 (T2.2 기록).
30 m 규칙의 거리 함수는 카카오 기록 좌표로 확인한다 (2026-11-07 측정: 대한문 12.1 m, 덕수궁 70.7 m).
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from flask.testing import FlaskClient

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import CandidateBatch, CandidateBatchResponse, ErrorBody, RouteResponse, Status

BE_DIR = Path(__file__).resolve().parents[1]
TOKEN = "naru-test-token"  # 테스트 앱 설정값. 실제 운영 토큰은 .env NARU_INTERNAL_TOKEN
HEADERS = {"X-Naru-Internal-Token": TOKEN}
KYOBO = "37.5709686446227,126.9779039768265"
DAEHANMUN = "37.5650416322942,126.976542945622"


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
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture(scope="module")
def course_batch(recorded_dir: Path) -> dict[str, object]:
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    assert files, "기록 없음: make record-candidates SOURCE=course 먼저"
    body: dict[str, object] = json.loads(files[-1].read_text("utf-8"))
    assert len(CandidateBatch.model_validate(body).candidates) == 16
    return body


def test_token_required(client: FlaskClient, course_batch: dict[str, object]) -> None:
    resp = client.post("/internal/candidates", json=course_batch)
    assert resp.status_code == 401
    assert ErrorBody.model_validate(resp.get_json()).error.code == "unauthorized"
    resp = client.post(
        "/internal/candidates", json=course_batch, headers={"X-Naru-Internal-Token": "wrong"}
    )
    assert resp.status_code == 401
    # 토큰이 비어 있는 앱은 전부 401 (운영에서 실수로 토큰 없이 띄우면 받지 않는다)
    assert Settings(internal_token="").internal_token == ""


def test_batch_accepted_then_route_avoids(
    app: Flask, client: FlaskClient, course_batch: dict[str, object]
) -> None:
    models: NaruModels = app.extensions["naru"]
    resp = client.post("/internal/candidates", json=course_batch, headers=HEADERS)
    assert resp.status_code == 202, resp.get_data(as_text=True)
    body = CandidateBatchResponse.model_validate(resp.get_json())
    assert body.batch_id == course_batch["batch_id"]
    assert body.accepted == 16 and body.review_required == 0
    # 16구간 15 m 버퍼 안 — T6.9 서울 전체: 구간 0~15 가 5·6·58·69·61·54·10·33·15·86·8·9·23·23·9·1
    # (T6.7 측정, 종로·중구였을 땐 앞 5구간만 183)
    assert body.crosswalks_updated == models.repo.count() == 470
    # 적재는 지금(2026-11, 창 지남) 기준이라 저장 status 는 released 지만, 3/15 07:45 로 물으면
    # 창으로 다시 판정해 confirmed → 라우터가 피한다 (status_of_state: 실측 해제만 고정)
    route = client.get(
        "/route",
        query_string={"from": KYOBO, "to": DAEHANMUN, "depart_at": "2026-03-15T07:45:00+09:00"},
    )
    rr = RouteResponse.model_validate(route.get_json())
    assert {a.crosswalk_id for a in rr.avoided} >= {"06-0000023206", "06-0000036391"}
    assert all(a.status is Status.confirmed for a in rr.avoided)
    assert "underpass" in {leg.kind.value for leg in rr.legs}
    # 같은 batch_id 재전송 → 같은 응답, 행 수 그대로 (INTERFACE §1.1 멱등)
    again = client.post("/internal/candidates", json=course_batch, headers=HEADERS)
    assert again.status_code == 202 and again.get_json() == resp.get_json()
    assert models.repo.count() == 470
    assert models.repo.batch_result(str(course_batch["batch_id"])) is not None


def test_invalid_batch_and_road_distance(app: Flask, client: FlaskClient) -> None:
    resp = client.post("/internal/candidates", json={"batch_id": "x"}, headers=HEADERS)
    assert resp.status_code == 400
    err = ErrorBody.model_validate(resp.get_json()).error
    assert err.code == "invalid_query" and err.field in {"produced_at", "producer", "candidates"}
    resp = client.post("/internal/candidates", data="not json", headers=HEADERS)
    assert resp.status_code in (400, 415)
    assert ErrorBody.model_validate(resp.get_json()).error.code == "invalid_query"
    # ADR-008 30 m 규칙의 거리 — 카카오 기록: 대한문(17582477) 12.1 m, 덕수궁(10305191) 70.7 m
    road = app.extensions["naru"].road_graph
    assert 11 < road.nearest_link_distance_m(126.976542945622, 37.5650416322942) < 13
    assert 69 < road.nearest_link_distance_m(126.974894754989, 37.5655638710672) < 72
