"""사건 v2(INTERFACE §3.1 v0.14 — id·상태·통제 구역) 응답 기록 — FE 지금 지도 테스트 입력
(T7.2, ADR-014).

    uv run python scripts/record_live_events.py

테스트 DB(naru_test)에 실제 앱을 띄우고 워커 발행 경로로 기록만 싣는다(운영 DB 는 안 건드린다):
경찰청 '오늘의 주요집회' PDF 3개(11/7·11/8·11/9, T6.6 inbox 경로 — LLM 기록 재생, 0.7 미만 둘)·
코스(3/15)·공지(sentences.jsonl — PDF 로 읽은 날짜의 경찰청 행은 건너뜀, T6.9)·돌발 11/7 15:40·
TOPIS 공지 6300(11/7 09:00 에 볼 글)·TOPIS 통제지도 11/9 08:37 목록(T7.3 예정 집회)·돌발 11/9 14:55.
그 뒤 GET /closures/events?at=… 를 시각마다 그대로 남긴다(record_naru_api 형식, ETag 도).
11/7 15:30 = 집회 날, 11/9 13:30 = 국회대로 행진 통제 중·강남대로 30분 뒤, 3/15 07:45 = 마라톤,
11/8 20:00 = 다음 날(11/9) 통제가 '내일'(T7.5). 시트 목록(T7.12)은 at 앞뒤 365일
넓은 창 — 11/7 15:30, 11/8 12:00(이 시각 걸린 통제 없음). 길찾기 avoid(T7.6) — 교보빌딩 → 대한문을
3/15 04:30·13:30 에 마라톤 1구간을 피해서(GET /route?avoid=).
T7.4 에서 PDF·통제지도를 더해 다시 기록 — FE 지금 지도에 확신도 0.7 미만 사건이 있어야 한다.
"""

from __future__ import annotations

import json
import shutil
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
TOPIS_MAP = "20261109T083719_selectAccAllListASC.json"  # T6.5 통제지도 목록 6행 (T7.3)
SMPA_RAW = ROOT / "data" / "raw" / "notices" / "smpa"  # 태우가 받은 PDF (MANIFEST notices/smpa)
SMPA_PDFS = [f"2611{d}) 오늘의 주요집회.pdf" for d in ("07(토", "08(일", "09(월")]
AT = {
    "closure_events_live_1107_1530": "2026-11-07T15:30:00+09:00",
    "closure_events_live_1109_1330": "2026-11-09T13:30:00+09:00",
    "closure_events_live_0315_0745": "2026-03-15T07:45:00+09:00",
    # T7.5 '내일' 묶음 — 11/8 저녁에 본 11/9 통제(경찰청 PDF·TOPIS 통제지도·돌발 예정)
    "closure_events_live_1108_2000": "2026-11-08T20:00:00+09:00",
}
# T7.12 시트 목록 — t 앞뒤 365일 넓은 창(FE 와 같은 from·to).
# 11/8 12:00 = 이 시각 걸린 통제가 없는 날
CATALOG = {
    "closure_events_catalog_1107_1530": "2026-11-07T15:30:00+09:00",
    "closure_events_catalog_1108_1200": "2026-11-08T12:00:00+09:00",
}


# T7.6 이 구역 피해서 길찾기 — /route?avoid= (교보빌딩 → 대한문, record_naru_api 와 같은 카카오 점).
# 마라톤 1구간(adaea2f4cc02, 07:20~08:08)을 04:30(시작 전 — 예정)·13:30(끝난 뒤 — 해제)에 피한다
KYOBO = "37.5709686446227,126.9779039768265"
DAEHANMUN = "37.5650416322942,126.976542945622"
SEG1 = "adaea2f4cc02"
ROUTES = {
    f"route_avoid_{hhmm}": {
        "from": KYOBO,
        "to": DAEHANMUN,
        "depart_at": f"2026-03-15T{hhmm[:2]}:{hhmm[2:]}:00+09:00",
        "avoid": SEG1,
    }
    for hhmm in ("0430", "1330")
}


def wide(at: str) -> dict[str, str]:
    """시트 목록 질의 — at 과 앞뒤 365일 (FE naruApiClient catalogParams 와 같다)"""
    t = datetime.fromisoformat(at)
    day = timedelta(days=365)
    return {"at": at, "from": (t - day).isoformat(), "to": (t + day).isoformat()}


def main() -> None:
    base = Settings()
    if not base.test_database_url.endswith("/naru_test"):
        raise SystemExit("naru_test 가 아니다 — 운영 DB 를 쓰지 않는다")
    app = create_app(Settings(DATABASE_URL=base.test_database_url, internal_token="naru-record"))
    models = app.extensions["naru"]
    models.repo.truncate()
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.record")
    pub = CandidatePublisher("http://naru.record", "naru-record", client=http, backoff_s=0.0)
    smpa = Path(tempfile.mkdtemp())  # 운영 inbox 와 떨어진 임시 폴더 — PDF 사본만
    (smpa / "inbox").mkdir()
    for name in SMPA_PDFS:
        shutil.copy2(SMPA_RAW / name, smpa / "inbox" / name)
    for i, record in enumerate(INCIDENTS):
        ai = AISettings(
            NARU_INCIDENT_RECORD=str(RECORDED / "incident" / record),
            NARU_TOPIS_RECORD=str(RECORDED / "topis_notice" / TOPIS),
            NARU_TOPIS_MAP_RECORD=str(RECORDED / "topis_web" / TOPIS_MAP),
            NARU_SMPA_DIR=str(smpa),
        )
        worker = IngestWorker(ai, pub)  # client 없음 → 공지는 LLM 기록 재생만
        if i == 0:
            # PDF 먼저 — 읽은 날짜의 sentences.jsonl 경찰청 행은 run_once 가 건너뛴다(중복 없음)
            worker.smpa_round(datetime(2026, 11, 6, 20, 0, tzinfo=KST))
            worker.run_once()
            topis = worker.topis_batch(datetime(2026, 11, 7, 9, 0, tzinfo=KST))
            if topis is not None:
                pub.publish(topis)
            mapped = worker.topis_map_batch()  # 돌발 11/9 보다 먼저 — T6.1 연결로 통제 중
            if mapped is not None:
                pub.publish(mapped)
        pub.publish(worker.incident_batch())
    client = app.test_client()
    out = RECORDED / "naru_api"
    queries = {name: {"at": at} for name, at in AT.items()}
    queries |= {name: wide(at) for name, at in CATALOG.items()}
    for name, query in queries.items():
        resp = client.get("/closures/events", query_string=query)
        doc = {
            "method": "GET",
            "path": "/closures/events",
            "query": query,
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
    for name, query in ROUTES.items():
        resp = client.get("/route", query_string=query)
        doc = {
            "method": "GET",
            "path": "/route",
            "query": query,
            "status": resp.status_code,
            "body": resp.get_json(),
        }
        path = out / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        avoided = [(a["crosswalk_id"], a["status"]) for a in doc["body"].get("avoided", [])]
        print(path.relative_to(ROOT), resp.status_code, "avoided", avoided)
    models.repo.truncate()


if __name__ == "__main__":
    main()
