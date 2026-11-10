"""T7.8 — 알림 구독·관심 지역 API (INTERFACE §9, ADR-014 C). 실제 Flask 앱 + MySQL naru_test.

구독 입력은 실제 브라우저가 실제 푸시 서비스(FCM)에 만든 구독 기록 —
scripts/record_push_subscription.py(헤드리스 Chrome 영속 프로필, VAPID 테스트 키
{D}/recorded/push/vapid_test.pem). 공개키는 그 PEM 에서 서버가 다시 뽑은 값이 기록의
vapid_public_key 와 같아야 한다. 관심 지역 점은 카카오 기록(광화문교보빌딩·덕수궁 대한문).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from flask.testing import FlaskClient
from pydantic import SecretStr
from pyproj import Transformer

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_be.errors import PushUnavailableError
from naru_be.models.domain.push_desk import PushDesk, snap_to_grid
from naru_contracts import (
    ErrorBody,
    SubscribeResponse,
    VapidPublicKey,
    WatchArea,
    WatchAreasResponse,
)

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]
KYOBO = (126.9779039768265, 37.5709686446227)  # 카카오 '광화문교보빌딩'
DAEHANMUN = (126.976542945622, 37.5650416322942)  # 카카오 '덕수궁 대한문'
HEADER = "X-Push-Endpoint"


@pytest.fixture(scope="module")
def recorded_push(recorded_dir: Path) -> dict[str, object]:
    files = sorted((recorded_dir / "push").glob("*_subscription.json"))
    assert files, (
        "기록 없음: NARU_FE_ORIGIN=… uv run python scripts/record_push_subscription.py 먼저"
    )
    doc: dict[str, object] = json.loads(files[-1].read_text("utf-8"))
    return doc


@pytest.fixture(scope="module")
def app(recorded_dir: Path) -> Iterator[Flask]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")  # 0008
    pem = (recorded_dir / "push" / "vapid_test.pem").read_text("utf-8")
    app = create_app(
        Settings(DATABASE_URL=base.test_database_url, vapid_private_key=SecretStr(pem))
    )
    models: NaruModels = app.extensions["naru"]
    models.push.repo.truncate()
    yield app
    models.push.repo.truncate()


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_vapid_public_key_matches_recording(
    client: FlaskClient, recorded_push: dict[str, object]
) -> None:
    resp = client.get("/push/vapid-public-key")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    key = VapidPublicKey.model_validate(resp.get_json()).public_key
    assert key == recorded_push["vapid_public_key"]  # 브라우저가 구독할 때 쓴 바로 그 키
    # 키가 없는 서버는 503 push_unavailable (Model 만 — .env 의 운영 키를 읽지 않게 빈 키를 준다)
    desk = PushDesk(
        client.application.extensions["naru"].push.repo, Settings(vapid_private_key=SecretStr(""))
    )
    with pytest.raises(PushUnavailableError) as e:
        desk.public_key()
    assert e.value.http_status == 503


def test_subscribe_and_watch_areas(client: FlaskClient, recorded_push: dict[str, object]) -> None:
    sub = recorded_push["subscription"]
    assert isinstance(sub, dict)
    endpoint = str(sub["endpoint"])
    first = client.post("/push/subscribe", json=sub)
    assert first.status_code == 201, first.get_data(as_text=True)
    saved = SubscribeResponse.model_validate(first.get_json())
    assert saved.active and saved.created_at.utcoffset() == timedelta(hours=9)
    again = client.post("/push/subscribe", json=sub)  # 같은 endpoint — 같은 id
    assert SubscribeResponse.model_validate(again.get_json()).id == saved.id
    for bad in ({**sub, "endpoint": "http://example.invalid/x"}, {"endpoint": endpoint}):
        assert client.post("/push/subscribe", json=bad).status_code == 400
    headers = {HEADER: endpoint}
    empty = client.get("/watch-areas", headers=headers)
    assert empty.status_code == 200
    assert WatchAreasResponse.model_validate(empty.get_json()).areas == []
    # 저장 관심 지역 — 교보빌딩 500 m, 점 그대로
    area = client.post(
        "/watch-areas",
        json={
            "endpoint": endpoint,
            "kind": "saved",
            "lng": KYOBO[0],
            "lat": KYOBO[1],
            "radius_m": 500,
        },
    )
    assert area.status_code == 201, area.get_data(as_text=True)
    kyobo = WatchArea.model_validate(area.get_json())
    assert (kyobo.kind, kyobo.lng, kyobo.lat, kyobo.radius_m, kyobo.expires_at) == (
        "saved",
        round(KYOBO[0], 7),
        round(KYOBO[1], 7),
        500,
        None,
    )
    # 마지막 위치 — 대한문: 150 m 격자 가운데로 반올림, 3시간 뒤 만료
    seen = client.post(
        "/watch-areas",
        json={"endpoint": endpoint, "kind": "last_seen", "lng": DAEHANMUN[0], "lat": DAEHANMUN[1]},
    )
    assert seen.status_code == 201
    last = WatchArea.model_validate(seen.get_json())
    glng, glat = snap_to_grid(DAEHANMUN[0], DAEHANMUN[1], 150.0)
    assert (last.lng, last.lat, last.radius_m) == (glng, glat, 500)
    assert (last.lng, last.lat) != (round(DAEHANMUN[0], 7), round(DAEHANMUN[1], 7))
    assert last.expires_at is not None
    assert last.expires_at - last.created_at == timedelta(hours=3)
    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    x, y = tf.transform(glng, glat)
    x0, y0 = tf.transform(*DAEHANMUN)
    assert abs(x - x0) <= 75.5 and abs(y - y0) <= 75.5 and (x % 150) - 75 < 0.01
    # 마지막 위치를 다시 보내면 바꿔 끼운다 — 저장 1 + 마지막 1
    seen2 = client.post(
        "/watch-areas",
        json={"endpoint": endpoint, "kind": "last_seen", "lng": KYOBO[0], "lat": KYOBO[1]},
    )
    assert seen2.status_code == 201
    areas = WatchAreasResponse.model_validate(
        client.get("/watch-areas", headers=headers).get_json()
    )
    assert sorted(a.kind for a in areas.areas) == ["last_seen", "saved"]
    assert next(a for a in areas.areas if a.kind == "last_seen").id == seen2.get_json()["id"]
    # 반경은 300·500·1000 만, 저장은 10개까지
    bad_r = client.post(
        "/watch-areas",
        json={
            "endpoint": endpoint,
            "kind": "saved",
            "lng": KYOBO[0],
            "lat": KYOBO[1],
            "radius_m": 400,
        },
    )
    assert bad_r.status_code == 400
    assert ErrorBody.model_validate(bad_r.get_json()).error.field == "radius_m"
    for _ in range(9):
        more = client.post(
            "/watch-areas",
            json={
                "endpoint": endpoint,
                "kind": "saved",
                "lng": KYOBO[0],
                "lat": KYOBO[1],
                "radius_m": 300,
            },
        )
        assert more.status_code == 201
    full = client.post(
        "/watch-areas",
        json={
            "endpoint": endpoint,
            "kind": "saved",
            "lng": KYOBO[0],
            "lat": KYOBO[1],
            "radius_m": 300,
        },
    )
    assert (
        full.status_code == 400
        and "10개" in ErrorBody.model_validate(full.get_json()).error.message
    )
    # 지우기 — 내 것만, 없는 id 는 404, 헤더 없으면 400, 모르는 endpoint 는 404
    assert client.delete(f"/watch-areas/{kyobo.id}", headers=headers).status_code == 204
    assert client.delete(f"/watch-areas/{kyobo.id}", headers=headers).status_code == 404
    assert client.get("/watch-areas").status_code == 400
    other = client.get("/watch-areas", headers={HEADER: endpoint + "x"})
    assert other.status_code == 404
    assert ErrorBody.model_validate(other.get_json()).error.code == "not_found"
    # 구독 해지 → 관심 지역은 더 못 본다, 다시 구독하면 같은 id 로 켜진다
    assert client.delete("/push/subscribe", json={"endpoint": endpoint}).status_code == 204
    assert client.get("/watch-areas", headers=headers).status_code == 404
    back = SubscribeResponse.model_validate(client.post("/push/subscribe", json=sub).get_json())
    assert back.id == saved.id and back.active
