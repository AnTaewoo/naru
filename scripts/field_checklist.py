"""현장 체크리스트 — 그 날 그 시간대 나루가 막힘으로 보는 (횡단보도, 사건) → CSV + GeoJSON (T7.15).

교수님 멘토링 T-A(11/10): 11/14 현장 검증에 들고 나간다. 막힘 판정은 라우터와 같은 함수
(naru_be.models.domain.prediction — confirmed, 또는 확신도 ≥ 0.7 예정이 공지 창 안; 행진 확률
모델 사건은 P(t, s) ≥ 0.8, ADR-015).
1분 간격으로 보고 처음·마지막으로 막힌 분을 적는다. actual·checked_at·note 는 현장에서 적는
예비 칸(주는 제보 앱).
DB 는 읽기만. 기본 DB 는 Settings.database_url(운영), 검증 DB 면 --database-url.

    uv run python scripts/field_checklist.py --date 2026-11-14 --from 13:00 --to 18:00
        [--database-url URL] [--out docs/eval/field_20261114]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from naru_be.app import latest_dir
from naru_be.config import Settings
from naru_be.db import make_engine, make_sessions
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.prediction import ChecklistRow, checklist
from naru_be.models.repositories.closure_repository import ClosureRepository

KST = timezone(timedelta(hours=9))
WORLD = (-180.0, -90.0, 180.0, 90.0)  # 서울 전체 — bbox 로 거르지 않는다
COLUMNS = (
    *("no", "crosswalk_id", "name", "district", "lng", "lat", "blocked_from", "blocked_to"),
    *("status", "confidence", "event_id", "reason", "window_start", "window_end"),
    *("actual", "checked_at", "note"),
)


def _kst(t: datetime | None, fmt: str = "%m-%d %H:%M") -> str:
    return t.astimezone(KST).strftime(fmt) if t is not None else ""


def record(no: int, r: ChecklistRow) -> dict[str, object]:
    return {
        "no": no,
        "crosswalk_id": r.crosswalk_id,
        "name": r.name or "",
        "district": r.district or "",
        "lng": round(r.lng, 7),
        "lat": round(r.lat, 7),
        "blocked_from": _kst(r.blocked_from, "%H:%M"),
        "blocked_to": _kst(r.blocked_to, "%H:%M"),
        "status": r.status.value,
        "confidence": r.confidence,
        "event_id": r.event_id,
        "reason": r.reason.splitlines()[0],  # 첫 줄 (TOPIS 공지는 본문이 사유 — 전체는 사건 id 로)
        "window_start": _kst(r.window_start),
        "window_end": _kst(r.window_end),
        "actual": "",
        "checked_at": "",
        "note": "",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="현장 체크리스트 (T7.15)")
    ap.add_argument("--date", required=True, type=date.fromisoformat, help="YYYY-MM-DD (KST)")
    ap.add_argument("--from", dest="start", required=True, type=time.fromisoformat, help="HH:MM")
    ap.add_argument("--to", dest="end", required=True, type=time.fromisoformat, help="HH:MM")
    ap.add_argument("--database-url", help="기본: Settings.database_url (운영 DB, 읽기만)")
    ap.add_argument("--out", type=Path, help="기본: docs/eval/field_YYYYMMDD")
    args = ap.parse_args(argv)
    start = datetime.combine(args.date, args.start, KST)
    end = datetime.combine(args.date, args.end, KST)
    if end <= start:
        ap.error("--to 는 --from 보다 뒤")
    settings = Settings()
    spatial = latest_dir(settings.data_dir / "raw", "seoul_spatial_*")
    index = CrosswalkIndex.from_xlsx(spatial / "OA-23081.xlsx", settings)
    url = args.database_url or settings.database_url
    repo = ClosureRepository(make_sessions(make_engine(url)), settings)
    states = repo.active_between(start, end, WORLD)
    engine = ClosureEngine(index, settings)
    rows = checklist(states, index, engine, settings, start, end)  # 행진도 전 구역 (11/12)
    if not rows:
        print(
            f"{start:%Y-%m-%d %H:%M}~{end:%H:%M} 막힘 예측 없음 (상태 {len(states)}건)",
            file=sys.stderr,
        )
        return 1
    out: Path = args.out or Path("docs/eval") / f"field_{args.date:%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f"checklist_{args.date:%Y%m%d}_{args.start:%H%M}-{args.end:%H%M}"
    records = [record(i, r) for i, r in enumerate(rows, start=1)]
    with stem.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as f:  # 엑셀 한글
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [rec["lng"], rec["lat"]]},
            "properties": rec,
        }
        for rec in records
    ]
    geo = {"type": "FeatureCollection", "features": features}
    stem.with_suffix(".geojson").write_text(json.dumps(geo, ensure_ascii=False), "utf-8")
    events = {r.event_id for r in rows}
    crosswalks = {r.crosswalk_id for r in rows}
    print(
        f"{stem}.csv · .geojson — {len(rows)}행, 횡단보도 {len(crosswalks)}곳, 사건 {len(events)}건"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
