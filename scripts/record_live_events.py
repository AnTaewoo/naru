"""사건 v2(INTERFACE §3.1 v0.14 — id·상태·통제 구역) 응답 기록 — FE 지금 지도 테스트 입력
(T7.2, ADR-014).

    uv run python scripts/record_live_events.py

테스트 DB(naru_test)에 실제 앱을 띄우고 워커 발행 경로로 기록만 싣는다(운영 DB 는 안 건드린다):
코스(3/15)·공지(sentences.jsonl, LLM 기록 재생)·돌발 11/7 15:40·TOPIS 공지 6300(11/7 09:00 에
볼 글)·돌발 11/9 14:55. 그 뒤 GET /closures/events?at=… 를 시각마다 그대로 남긴다(record_naru_api
형식, ETag 도). 11/7 15:30 = 집회 날(사건 11), 11/9 13:30 = 국회대로 통제 중·강남대로 30분 뒤,
3/15 07:45 = 마라톤.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from naru_ai.config import Settings as AISettings
from naru_ai.publish import CandidatePublisher
from naru_ai.worker import IngestWorker
from naru_be.app import create_app
from naru_be.config import Settings

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
RECORDED = ROOT / "data" / "recorded"
INCIDENTS = ["20261107T154053_AccInfo.json", "20261109T145523_AccInfo.json"]
TOPIS = "20261108T192013.json"  # 11/7 09:00 에 볼 글 중 6300
AT = {
    "closure_events_live_1107_1530": "2026-11-07T15:30:00+09:00",
    "closure_events_live_1109_1330": "2026-11-09T13:30:00+09:00",
    "closure_events_live_0315_0745": "2026-03-15T07:45:00+09:00",
}


def main() -> None:
    base = Settings()
    if not base.test_database_url.endswith("/naru_test"):
        raise SystemExit("naru_test 가 아니다 — 운영 DB 를 쓰지 않는다")
    app = create_app(Settings(DATABASE_URL=base.test_database_url, internal_token="naru-record"))
    models = app.extensions["naru"]
    models.repo.truncate()
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.record")
    pub = CandidatePublisher("http://naru.record", "naru-record", client=http, backoff_s=0.0)
    smpa = tempfile.mkdtemp()  # 운영 inbox 와 떨어진 빈 폴더
    for i, record in enumerate(INCIDENTS):
        ai = AISettings(
            NARU_INCIDENT_RECORD=str(RECORDED / "incident" / record),
            NARU_TOPIS_RECORD=str(RECORDED / "topis_notice" / TOPIS),
            NARU_SMPA_DIR=smpa,
        )
        worker = IngestWorker(ai, pub)
        if i == 0:
            worker.run_once()
            topis = worker.topis_batch(datetime(2026, 11, 7, 9, 0, tzinfo=KST))
            if topis is not None:
                pub.publish(topis)
        pub.publish(worker.incident_batch())
    client = app.test_client()
    out = RECORDED / "naru_api"
    for name, at in AT.items():
        resp = client.get("/closures/events", query_string={"at": at})
        doc = {
            "method": "GET",
            "path": "/closures/events",
            "query": {"at": at},
            "status": resp.status_code,
            "etag": resp.headers.get("ETag"),
            "body": resp.get_json(),
        }
        path = out / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        events = doc["body"]["events"]
        verts = sum(
            sum(len(ring) for ring in poly)
            for e in events
            if e["area"]
            for poly in (
                [e["area"]["coordinates"]]
                if e["area"]["type"] == "Polygon"
                else e["area"]["coordinates"]
            )
        )
        size = len(resp.get_data())
        print(
            path.relative_to(ROOT),
            resp.status_code,
            f"{size:,}B",
            "events",
            len(events),
            "vertices",
            verts,
        )
    models.repo.truncate()


if __name__ == "__main__":
    main()
