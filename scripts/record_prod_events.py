"""운영 사건 v2 응답 기록 (T7.4) — FE 지금 지도의 '구역 없는 사건' 테스트 입력.

    uv run python scripts/record_prod_events.py

운영(https://naru.antaewoo.com)은 T7.2(0005 closure_events) 전에 받은 배치의
사건에 구역(area)이 없다 — 워커가 더 보내지 않는 11/7 돌발들. 그 실제 응답을 GET
한 번으로 받아 record_naru_api 형식(+ etag·origin·fetched_at)으로 남긴다.
운영 DB 는 읽기만 한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "recorded" / "naru_api"
ORIGIN = "https://naru.antaewoo.com/api"
AT = {"closure_events_prod_1107_1530": "2026-11-07T15:30:00+09:00"}


def main() -> None:
    with httpx.Client(timeout=20, headers={"user-agent": "NaruBot/0.1 (record_prod_events)"}) as c:
        for name, at in AT.items():
            resp = c.get(f"{ORIGIN}/closures/events", params={"at": at})
            resp.raise_for_status()
            doc = {
                "method": "GET",
                "path": "/closures/events",
                "query": {"at": at},
                "status": resp.status_code,
                "etag": resp.headers.get("etag"),
                "origin": ORIGIN,
                "fetched_at": datetime.now(KST).isoformat(timespec="seconds"),
                "body": resp.json(),
            }
            path = OUT / f"{name}.json"
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            events = doc["body"]["events"]
            no_area = sum(1 for e in events if not e.get("area"))
            print(
                path.relative_to(ROOT),
                resp.status_code,
                f"{len(resp.content):,}B",
                "events",
                len(events),
                "no area",
                no_area,
            )


if __name__ == "__main__":
    main()
