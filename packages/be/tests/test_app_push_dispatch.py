"""T7.9 — POST /internal/push/dispatch (실제 Flask 앱 + MySQL naru_test + 실제 푸시 서비스).

구독 둘 다 헤드리스 Chrome 이 실제 FCM 에 만든 것(recorded/push): 살아 있는 구독과 브라우저에서
해지한 구독(`*_subscription_gone.json` — 푸시 서비스가 410). 사건은 기록 공지 배치(11/7 r01·r04
구역이 교보빌딩 500 m 와 겹친다 — test_push_dispatcher). 발송은 가짜 없이 pywebpush → FCM
(테스트 VAPID 키 = 구독 때 쓴 키).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from flask.testing import FlaskClient
from pydantic import SecretStr

from naru_ai.publish import CandidatePublisher
from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.controllers._deps import NaruModels
from naru_contracts import CandidateBatch, PushDispatchResponse

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]
TOKEN = "naru-test-token"
HEADERS = {"X-Naru-Internal-Token": TOKEN}
KYOBO = {"lng": 126.9779039768265, "lat": 37.5709686446227, "radius_m": 500, "kind": "saved"}


def latest(recorded_dir: Path, suffix: str) -> dict[str, object]:
    files = sorted((recorded_dir / "push").glob(f"*{suffix}"))
    assert files, f"기록 없음: scripts/record_push_subscription.py ({suffix})"
    doc: dict[str, object] = json.loads(files[-1].read_text("utf-8"))
    return doc


@pytest.fixture(scope="module")
def app(recorded_dir: Path, notice_batch: CandidateBatch) -> Iterator[Flask]:
    base = Settings()
    assert base.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")
    pem = (recorded_dir / "push" / "vapid_test.pem").read_text("utf-8")
    app = create_app(
        Settings(
            DATABASE_URL=base.test_database_url,
            internal_token=TOKEN,
            vapid_private_key=SecretStr(pem),
            vapid_subject="mailto:naru-test@example.invalid",
        )
    )
    models: NaruModels = app.extensions["naru"]
    models.repo.truncate()
    models.push.repo.truncate()
    models.intake.accept(notice_batch)
    yield app
    models.push.repo.truncate()
    models.repo.truncate()


@pytest.fixture(scope="module")
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def dispatch(client: FlaskClient, at: str) -> PushDispatchResponse:
    resp = client.post("/internal/push/dispatch", json={"at": at}, headers=HEADERS)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return PushDispatchResponse.model_validate(resp.get_json())


def test_dispatch_end_to_end(app: Flask, client: FlaskClient, recorded_dir: Path) -> None:
    alive = latest(recorded_dir, "_subscription.json")["subscription"]
    gone = latest(recorded_dir, "_subscription_gone.json")["subscription"]
    assert isinstance(alive, dict) and isinstance(gone, dict)
    assert alive["endpoint"] != gone["endpoint"]
    for sub in (alive, gone):
        assert client.post("/push/subscribe", json=sub).status_code == 201
        area = client.post("/watch-areas", json={**KYOBO, "endpoint": sub["endpoint"]})
        assert area.status_code == 201
    assert client.post("/internal/push/dispatch", json={}).status_code == 401  # 토큰 없음
    # 11/6 23:00 — 11/7 r01·r04 가 창(그 시각 ~ 24시간) 안이고 교보빌딩 500 m 와 겹친다:
    # 구독 둘 x 사건 둘. 밤이라 created 는 07:00 으로 줄만 선다
    night = dispatch(client, "2026-11-06T23:00:00+09:00")
    assert (night.matched, night.sent, night.failed, night.deactivated) == (4, 0, 0, 0)
    models: NaruModels = app.extensions["naru"]
    queued = models.push.repo.sends()
    assert len(queued) == 4 and {s.event_id for s in queued} == {"be5f89a4ebf3", "2e930ec6deeb"}
    assert all(s.kind == "created" and s.sent_at is None for s in queued)
    assert {s.due_at for s in queued} == {datetime(2026, 11, 7, 7, 0, tzinfo=KST)}
    # 07:00 — 실제 발송 넷. 살아 있는 구독 둘은 2xx. 브라우저에서 해지한 구독은 푸시 서비스가
    # 404·410 을 주면 그 구독을 끈다 — 2026-11-11 FCM 은 해지 직후에도 2xx 로 받았다(해지 전파가
    # 늦다). 둘 다 허용
    morning = dispatch(client, "2026-11-07T07:00:00+09:00")
    assert morning.matched == 0 and morning.sent + morning.failed == 4 and morning.sent >= 2
    done = models.push.repo.sends()
    assert all(s.sent_at is not None for s in done)
    statuses = [s.http_status or 0 for s in done]
    assert all(200 <= x < 300 or x in (404, 410) for x in statuses), statuses
    rejected = {s.subscription_id for s in done if s.http_status in (404, 410)}
    assert morning.deactivated == len(rejected)
    assert morning.failed == len([s for s in done if s.http_status in (404, 410)])
    headers = {"X-Push-Endpoint": str(gone["endpoint"])}
    gone_areas = client.get("/watch-areas", headers=headers).status_code
    assert gone_areas == (404 if rejected else 200)
    # 13:00 — 더 줄 설 것 없음(이미 보냄·꺼진 구독)
    later = dispatch(client, "2026-11-07T13:00:00+09:00")
    assert (later.matched, later.sent) == (0, 0)
    # 워커가 부르는 길 — CandidatePublisher.dispatch_push (httpx WSGITransport, 기준 시각은 BE 지금)
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.test")
    pub = CandidatePublisher("http://naru.test", TOKEN, client=http, backoff_s=0.0)
    now_result = pub.dispatch_push()
    assert now_result.at.utcoffset() is not None and now_result.sent == 0
