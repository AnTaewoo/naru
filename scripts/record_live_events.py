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
3/15 04:30·13:30 에 마라톤 1구간을 피해서(GET /route?avoid=). 통제 제보(T7.15, INTERFACE §8) —
교보빌딩 점 최근접·서울 밖 없음·제보 201·같은 기기 429·최근 집계(기기 토큰은 파일에 안 남긴다).
행진 키프레임(T7.16, INTERFACE §3.2) — 11/7 r01 동화면세점 고리(be5f89a4ebf3)·TOPIS 통제지도
국회대로 행진(ccaa9980c6ac) 통제 시간 전체, r04 갈라진 행진(2e930ec6deeb)은 404 not_modeled.
T7.4 에서 PDF·통제지도를 더해 다시 기록 — FE 지금 지도에 확신도 0.7 미만 사건이 있어야 한다.
"""

from __future__ import annotations

import gzip
import json
import shutil
import tempfile
import uuid
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
# 태우 11/10 — 공지 해제 시각 뒤 30분(released_grace, 아직 막힘) 문구 "정리 중":
# 3/15 08:35 는 1구간(08:08)·출발지 구간(08:30) 둘 다 해제 시각이 지났지만 +30분 안이라 통제 중
ROUTES["route_0835"] = {"from": KYOBO, "to": DAEHANMUN, "depart_at": "2026-03-15T08:35:00+09:00"}
# T7.15 통제 제보 — 교보빌딩 카카오 점 → 06-0000051345 '교보생명' 71 m,
# 성남(서울 밖, test_routers 와 같은 점) → 없음.
# 제보는 교보생명 막힘, 같은 기기가 바로 다시 열림 → 429,
# 세종대로사거리(06-0000023206 — route_0745 가 피하는 1구간 횡단보도) 막힘
# → 최근 집계는 교보생명·세종대로사거리 각 1
KYOBO_CW, SEJONG_CW = "06-0000051345", "06-0000023206"
# T7.16 행진 키프레임 — 사건 id 는 closure_events_catalog_1107_1530 의 값
MARCHES = {
    "march_be5f89a4ebf3": "be5f89a4ebf3",  # 11/7 r01 동화면세점 앞 → 종로1R → 동화면세점, 50,000명
    "march_ccaa9980c6ac": "ccaa9980c6ac",  # 11/9 TOPIS 통제지도 국회대로 행진 1109233 (75곳)
    "error_not_modeled": "2e930ec6deeb",  # 11/7 r04 — 숭례문오거리에서 갈라져 대상 아님
}
NEAREST: dict[str, dict[str, object]] = {
    "report_nearest_kyobo": {"lat": 37.5709686446227, "lng": 126.9779039768265},
    "report_nearest_none": {"lat": 37.3947, "lng": 127.1112},
}
REPORT: dict[str, object] = {
    "crosswalk_id": KYOBO_CW,
    "state": "blocked",
    "accuracy_m": 14,
    "source": "user",
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
    models.report_desk.repo.truncate()
    device = str(uuid.uuid4())  # FE 와 같은 방식의 기기 토큰 — 기록 파일에는 안 남긴다
    posts: list[tuple[str, str, dict[str, object]]] = [
        *(("/crosswalks/nearest", name, body) for name, body in NEAREST.items()),
        ("/reports", "report_sent", REPORT),
        ("/reports", "report_too_many", {**REPORT, "state": "open"}),
        ("/reports", "report_sent_sejong", {**REPORT, "crosswalk_id": SEJONG_CW}),
    ]
    for url, name, body in posts:
        payload = {**body, "device": device} if url == "/reports" else body
        resp = client.post(url, json=payload)
        doc = {"method": "POST", "path": url, "json": body, "status": resp.status_code}
        doc["body"] = resp.get_json()
        path = out / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(path.relative_to(ROOT), resp.status_code, doc["body"])
    query = {"ids": f"{KYOBO_CW},{SEJONG_CW},06-0000036391", "minutes": "60"}
    resp = client.get("/reports/recent", query_string=query)
    doc = {"method": "GET", "path": "/reports/recent", "query": query, "status": resp.status_code}
    doc["body"] = resp.get_json()
    path = out / "reports_recent.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(path.relative_to(ROOT), resp.status_code, doc["body"])
    models.report_desk.repo.truncate()
    for name, event_id in MARCHES.items():
        resp = client.get(f"/closures/events/{event_id}/march")
        doc = {"method": "GET", "path": f"/closures/events/{event_id}/march"}
        doc |= {"status": resp.status_code, "etag": resp.headers.get("ETag")}
        doc["body"] = resp.get_json()
        path = out / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raw = resp.get_data()
        frames = doc["body"].get("keyframes", []) if resp.status_code == 200 else []
        print(
            path.relative_to(ROOT),
            resp.status_code,
            f"{len(raw):,}B gzip {len(gzip.compress(raw)):,}B",
            "keyframes",
            len(frames),
            "points/frame max",
            max((sum(len(s) for s in f["samples"]) for f in frames), default=0),
        )
    models.repo.truncate()


if __name__ == "__main__":
    main()
