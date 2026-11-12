"""로컬 Flask 응답을 FE 테스트 입력으로 기록 — `make record-naru-api` (T3.4).

실제 앱(create_app, 개발 DB naru)에 기록된 코스 배치를 POST 하고 /route·/closures·
/closures/events(T5.4, 개발 DB 에 있는 통제 전부)·/geocode/*(T5.8, 카카오 기록 재생)·오류 응답을
`data/recorded/naru_api/<name>.json` 에 그대로 둔다 (real-data-testing §4.2). 토큰은 .env
NARU_INTERNAL_TOKEN (파일에 남기지 않는다). 좌표는 카카오 기록(광화문교보빌딩·덕수궁 대한문).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from naru_be.app import create_app
from naru_be.config import Settings

BE_DIR = Path(__file__).resolve().parents[1] / "packages" / "be"
KYOBO = "37.5709686446227,126.9779039768265"  # 카카오 24020019 (lat,lng)
DAEHANMUN = "37.5650416322942,126.976542945622"  # 카카오 17582477
GWANGHWAMUN = "126.965,37.555,126.990,37.580"
TIMES = {"0430": "04:30", "0745": "07:45", "1330": "13:30"}  # 통제 전 / 중 / 후 (2026-03-15 KST)
# T5.5 회귀 — 태우가 2026-11-08 실서버에 보낸 요청 그대로 (lat,lng)
SEJONG = ("37.56368,126.97230", "37.56368,126.98193")  # 11/7 15:00 세종대로 건너기 (예정 집회 안)
JAMSIL = ("37.5133,127.0980", "37.5145,127.1035")  # 그래프 밖 → out_of_coverage
# T5.8 지오코딩 — 앱은 카카오 기록 재생(geocode_source=recorded, live 없음).
# near = FE 지도 기본 중심
NEAR = "37.5675,126.9775"
SEARCHES = {"kyobo": "교보빌딩", "deoksugung": "덕수궁", "cityhall": "시청"}
REVERSES = {
    "kyobo": KYOBO,
    "daehanmun": DAEHANMUN,
    "sejong_from": SEJONG[0],
    "sejong_to": SEJONG[1],
}


def record(out: Path, name: str, method: str, path: str, resp: TestResponse, **req: object) -> None:
    doc = {"method": method, "path": path, **req, "status": resp.status_code}
    doc["body"] = resp.get_json()
    (out / f"{name}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{name}.json  {method} {path} → {doc['status']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="로컬 Flask 응답 기록 (FE 테스트 입력)")
    ap.add_argument("--recorded", type=Path, default=Path("data/recorded"))
    args = ap.parse_args(argv)
    settings = Settings(geocode_source="recorded")
    if not settings.internal_token:
        raise SystemExit("NARU_INTERNAL_TOKEN 없음 — .env 에 채운다")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={settings.database_url}"]})()
    command.upgrade(cfg, "head")
    app = create_app(settings)
    client: FlaskClient = app.test_client()
    out = args.recorded / "naru_api"
    out.mkdir(parents=True, exist_ok=True)

    batches = sorted((args.recorded / "candidates" / "course").glob("*.json"))
    if not batches:
        raise SystemExit("기록 없음: make record-candidates SOURCE=course 먼저")
    batch = json.loads(batches[-1].read_text("utf-8"))
    headers = {"X-Naru-Internal-Token": settings.internal_token}
    resp = client.post("/internal/candidates", json=batch, headers=headers)
    record(out, "candidates_course", "POST", "/internal/candidates", resp, json=str(batches[-1]))
    resp = client.post("/internal/candidates", json=batch)
    record(out, "error_unauthorized", "POST", "/internal/candidates", resp)
    # 공지 후보(T5.5) — 11/7 서울경찰청 집회. 예정 통제 우회 기록용
    notices = sorted((args.recorded / "candidates" / "notice").glob("*.json"))
    if not notices:
        raise SystemExit("기록 없음: make record-candidates SOURCE=notice 먼저")
    notice = json.loads(notices[-1].read_text("utf-8"))
    resp = client.post("/internal/candidates", json=notice, headers=headers)
    record(out, "candidates_notice", "POST", "/internal/candidates", resp, json=str(notices[-1]))

    for key, hhmm in TIMES.items():
        at = f"2026-03-15T{hhmm}:00+09:00"
        q = {"from": KYOBO, "to": DAEHANMUN, "depart_at": at}
        record(out, f"route_{key}", "GET", "/route", client.get("/route", query_string=q), query=q)
        q2 = {"bbox": GWANGHWAMUN, "at": at}
        resp = client.get("/closures", query_string=q2)
        record(out, f"closures_{key}", "GET", "/closures", resp, query=q2)

    # 예정 집회 창 안 우회 (ADR-011 A) · 그래프 밖 (ADR-011, INTERFACE §6)
    q = {"from": SEJONG[0], "to": SEJONG[1], "depart_at": "2026-11-07T15:00:00+09:00"}
    record(out, "route_1107_1500", "GET", "/route", client.get("/route", query_string=q), query=q)
    # 같은 시각 광화문 통제(T5.9) — 홈 목록의 공지 행(파서 제목·공지 원문 보기) 입력
    q2 = {"bbox": GWANGHWAMUN, "at": "2026-11-07T15:00:00+09:00"}
    resp = client.get("/closures", query_string=q2)
    record(out, "closures_1107_1500", "GET", "/closures", resp, query=q2)
    q = {"from": JAMSIL[0], "to": JAMSIL[1], "depart_at": "2026-03-15T10:00:00+09:00"}
    resp = client.get("/route", query_string=q)
    record(out, "error_out_of_coverage", "GET", "/route", resp, query=q)

    # 통제 사건 목록 (INTERFACE §3.1) — 개발 DB 에 들어 있는 배치(코스·공지) 전부가 실린다
    record(out, "closure_events", "GET", "/closures/events", client.get("/closures/events"))

    q = {"from": KYOBO, "to": DAEHANMUN, "depart_at": "2026-03-15T07:45:00"}
    resp = client.get("/route", query_string=q)
    record(out, "error_invalid_query", "GET", "/route", resp, query=q)
    record(out, "error_not_found", "GET", "/nope", client.get("/nope"))

    # 지오코딩 (INTERFACE §7) — 카카오 기록에 있는 요청만. 잠실은 기록이 없어 503 그대로
    for key, word in SEARCHES.items():
        q = {"q": word, "near": NEAR}
        resp = client.get("/geocode/search", query_string=q)
        record(out, f"geocode_search_{key}", "GET", "/geocode/search", resp, query=q)
    for key, latlng in REVERSES.items():
        lat, lng = latlng.split(",")
        q = {"lat": lat, "lng": lng}
        resp = client.get("/geocode/reverse", query_string=q)
        record(out, f"geocode_reverse_{key}", "GET", "/geocode/reverse", resp, query=q)
    lat, lng = JAMSIL[0].split(",")
    q = {"lat": lat, "lng": lng}
    resp = client.get("/geocode/reverse", query_string=q)
    record(out, "error_geocode_unavailable", "GET", "/geocode/reverse", resp, query=q)
    q = {"q": "시"}
    resp = client.get("/geocode/search", query_string=q)
    record(out, "error_geocode_query", "GET", "/geocode/search", resp, query=q)

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    meta = {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "batch_file": str(batches[-1]),
        "notice_batch_file": str(notices[-1]),
        "database": settings.database_url.rsplit("@", 1)[-1],  # 호스트/DB 만
        "files": sorted(p.name for p in out.glob("*.json") if p.name != "_meta.json"),
    }
    (out / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
