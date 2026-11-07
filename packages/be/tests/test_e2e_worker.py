"""T4.4 e2e — AI 워커 → 실제 Flask 앱(httpx WSGITransport, 소켓 없는 HTTP 왕복) → MySQL → /closures.

AI 와 BE 가 한 프로세스에 함께 올라오는 유일한 테스트 (패키지끼리는 import 안 한다 — 경계는 HTTP).
입력: 기록된 LLM 응답(recorded/llm 의 sentences 5문장, 재생만) + 카카오 기록 + 코스 GPX·시각표.
기대값은 2026-11-08 notice_v2 기록으로 확인한 값: 공지 후보 7(광화문 r01 1 + r04 3 + 여의도 3),
횡단보도 37(여의도 3건은 데모 범위 종로·중구 밖이라 0), /closures 광화문 12:30 → 13, 15:30 → 37.
"""

from collections.abc import Iterator
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
from naru_contracts import FeatureCollection, Status

BE_DIR = Path(__file__).resolve().parents[1]
TOKEN = "naru-e2e-token"
GWANGHWAMUN = "126.965,37.555,126.990,37.580"


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
