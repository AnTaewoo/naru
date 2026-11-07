"""로컬 Flask 응답을 FE 테스트 입력으로 기록 — `make record-naru-api` (T3.4).

실제 앱(create_app, 개발 DB naru)에 기록된 코스 배치를 POST 하고 /route·/closures·오류 응답을
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
    settings = Settings()
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

    for key, hhmm in TIMES.items():
        at = f"2026-03-15T{hhmm}:00+09:00"
        q = {"from": KYOBO, "to": DAEHANMUN, "depart_at": at}
        record(out, f"route_{key}", "GET", "/route", client.get("/route", query_string=q), query=q)
        q2 = {"bbox": GWANGHWAMUN, "at": at}
        resp = client.get("/closures", query_string=q2)
        record(out, f"closures_{key}", "GET", "/closures", resp, query=q2)

    q = {"from": KYOBO, "to": DAEHANMUN, "depart_at": "2026-03-15T07:45:00"}
    resp = client.get("/route", query_string=q)
    record(out, "error_invalid_query", "GET", "/route", resp, query=q)
    record(out, "error_not_found", "GET", "/nope", client.get("/nope"))

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    meta = {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "batch_file": str(batches[-1]),
        "database": settings.database_url.rsplit("@", 1)[-1],  # 호스트/DB 만
        "files": sorted(p.name for p in out.glob("*.json") if p.name != "_meta.json"),
    }
    (out / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
