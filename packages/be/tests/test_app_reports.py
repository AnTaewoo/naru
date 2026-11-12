"""T7.15 — 통제 제보 HTTP (INTERFACE §8): nearest 200·null, POST /reports 201·429·400, recent.

create_app(naru_test) — 실제 색인·실제 MySQL. 기대값은 test_reports 와 같은 확인값(2026-11-10 xlsx):
광화문교보빌딩 → 06-0000051345 '교보생명' 종로구 71 m, 성남(서울 밖) → null.
"""

import uuid
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.models.repositories.report_repository import ReportRepository
from naru_contracts import (
    ErrorBody,
    NearestCrosswalkResponse,
    RecentReportsResponse,
    ReportResponse,
)

KYOBO = {"lat": 37.5709686446227, "lng": 126.9779039768265}  # 카카오 '광화문교보빌딩'
SEONGNAM = {"lat": 37.3947, "lng": 127.1112}  # 서울 밖 (test_routers 와 같은 점)
KYOBO_CW = "06-0000051345"


@pytest.fixture(scope="module")
def app(report_repo: ReportRepository) -> Iterator[Flask]:
    base = Settings()
    yield create_app(Settings(DATABASE_URL=base.test_database_url))
    report_repo.truncate()


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_nearest_crosswalk(client: FlaskClient) -> None:
    resp = client.post("/crosswalks/nearest", json=KYOBO)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    cw = NearestCrosswalkResponse.model_validate(resp.get_json()).crosswalk
    assert cw is not None
    assert (cw.id, cw.name, cw.district, cw.distance_m) == (KYOBO_CW, "교보생명", "종로구", 71)
    assert cw.coord == (126.97768829792257, 37.571585764131775)  # INTERFACE §8.1 예시와 같다
    far = client.post("/crosswalks/nearest", json=SEONGNAM)
    assert far.status_code == 200 and far.get_json() == {"crosswalk": None}
    # 좌표는 본문으로만 — 쿼리 문자열은 받지 않는다
    bad = client.post("/crosswalks/nearest", query_string=KYOBO)
    assert bad.status_code == 400
    assert ErrorBody.model_validate(bad.get_json()).error.code == "invalid_query"


def test_report_then_too_many_then_recent(client: FlaskClient) -> None:
    device = str(uuid.uuid4())  # FE 와 같은 방식의 기기 토큰
    body = {
        "crosswalk_id": KYOBO_CW,
        "state": "blocked",
        "accuracy_m": 14,
        "source": "user",
        "device": device,
    }
    first = client.post("/reports", json=body)
    assert first.status_code == 201, first.get_data(as_text=True)
    saved = ReportResponse.model_validate(first.get_json())
    assert (saved.crosswalk_id, saved.state) == (KYOBO_CW, "blocked")
    assert (
        saved.reported_at.utcoffset() is not None and saved.reported_at.utcoffset().seconds == 32400
    )
    again = client.post("/reports", json={**body, "state": "open"})
    assert again.status_code == 429
    err = ErrorBody.model_validate(again.get_json()).error
    assert (err.code, err.field) == ("too_many_reports", "crosswalk_id")
    unknown = client.post("/reports", json={**body, "crosswalk_id": "06-0000000000"})
    assert unknown.status_code == 400
    assert ErrorBody.model_validate(unknown.get_json()).error.field == "crosswalk_id"
    shape = client.post("/reports", json={**body, "accuracy_m": 1500})
    assert shape.status_code == 400
    assert ErrorBody.model_validate(shape.get_json()).error.field == "accuracy_m"
    recent = client.get("/reports/recent", query_string={"ids": f"{KYOBO_CW},06-0000030621"})
    assert recent.status_code == 200
    counts = RecentReportsResponse.model_validate(recent.get_json()).counts
    assert set(counts) == {KYOBO_CW}
    assert (counts[KYOBO_CW].blocked, counts[KYOBO_CW].open) == (1, 0)
    no_ids = client.get("/reports/recent")
    assert no_ids.status_code == 400
    assert ErrorBody.model_validate(no_ids.get_json()).error.field == "ids"
