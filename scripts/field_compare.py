"""현장 검증 비교 — 그 날 field 제보마다 그 시각 나루 예측과 맞춰 본다 (T7.15) → docs/eval/.

양성 = 막힘. 맞음 · 덜 막음(나루 열림, 실제 막힘) · 더 막음(나루 막힘, 실제 열림).
recall = 맞힌 막힘 / 실제 막힘, precision = 맞힌 막힘 / 나루 막힘. 예측은 라우터와 같은 함수
(naru_be.models.domain.prediction.blocked_at). 제보는 source=field 만(FE ?mode=field). DB 는 읽기만.

    uv run python scripts/field_compare.py --date 2026-11-14 [--database-url URL] [--out FILE]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from naru_be.app import latest_dir
from naru_be.config import Settings
from naru_be.db import make_engine, make_sessions
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.prediction import CompareResult, Verdict, compare
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_be.models.repositories.report_repository import ReportRepository
from naru_contracts import Status

KST = timezone(timedelta(hours=9))
WORLD = (-180.0, -90.0, 180.0, 90.0)
VERDICT_KO: dict[Verdict, str] = {"match": "맞음", "over": "더 막음", "under": "덜 막음"}
PREDICTED_KO = {Status.confirmed: "통제 중", Status.scheduled: "예정(창 안)", None: "열림"}


def _ratio(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def render(result: CompareResult, index: CrosswalkIndex, day: date, db: str) -> str:
    devices = {r.report.device_hash for r in result.rows}
    crosswalks = {r.report.crosswalk_id for r in result.rows}
    now = datetime.now(KST)
    lines = [
        f"# 현장 검증 {day:%Y-%m-%d} — field 제보 vs 나루 예측",
        "",
        f"- 만든 때 {now:%Y-%m-%d %H:%M} KST · `scripts/field_compare.py --date {day}` · DB `{db}`",
        f"- 제보 {len(result.rows)}건 · 기기 {len(devices)}대 · 횡단보도 {len(crosswalks)}곳",
        "- 예측 = 라우터와 같은 막힘 판정(`prediction.blocked_at`): confirmed, 또는 확신도 ≥ 0.7"
        " 예정이 공지 창 안. 양성 = 막힘",
        "",
        "| | 실제 막힘 | 실제 열림 |",
        "|---|---|---|",
        f"| 나루 막힘 | {result.tp} | {result.fp} (더 막음) |",
        f"| 나루 열림 | {result.fn} (덜 막음) | {result.tn} |",
        "",
        f"- recall {_ratio(result.recall)} · precision {_ratio(result.precision)} (분모 0 이면 —)",
        "",
        "## 제보별",
        "| 시각 | 횡단보도 | 교차로명 | 실제 | 나루 | 판정 | 사유 | 정확도 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in result.rows:
        r = row.report
        cw = index.find(r.crosswalk_id)
        actual = "막힘" if r.state == "blocked" else "열림"
        why = row.reason.splitlines()[0] if row.reason else ""  # 첫 줄 (TOPIS 공지는 본문이 사유)
        lines.append(
            f"| {r.reported_at.astimezone(KST):%H:%M} | {r.crosswalk_id} | "
            f"{cw.intersection_name if cw else ''} | {actual} | {PREDICTED_KO[row.predicted]} | "
            f"{VERDICT_KO[row.verdict]} | {why} | {r.accuracy_m} m |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="현장 검증 비교 (T7.15)")
    ap.add_argument("--date", required=True, type=date.fromisoformat, help="YYYY-MM-DD (KST)")
    ap.add_argument("--database-url", help="기본: Settings.database_url (운영 DB, 읽기만)")
    ap.add_argument("--out", type=Path, help="기본: docs/eval/field_YYYYMMDD.md")
    args = ap.parse_args(argv)
    settings = Settings()
    url = args.database_url or settings.database_url
    sessions = make_sessions(make_engine(url))
    day0 = datetime.combine(args.date, time(0), KST)
    day1 = day0 + timedelta(days=1) - timedelta(seconds=1)
    reports = ReportRepository(sessions).between(day0, day1, source="field")
    if not reports:
        print(f"{args.date} field 제보 없음 — 비교할 것이 없다", file=sys.stderr)
        return 1
    spatial = latest_dir(settings.data_dir / "raw", "seoul_spatial_*")
    index = CrosswalkIndex.from_xlsx(spatial / "OA-23081.xlsx", settings)
    states = ClosureRepository(sessions, settings).active_between(day0, day1, WORLD)
    result = compare(reports, states, ClosureEngine(index, settings), settings)
    out: Path = args.out or Path("docs/eval") / f"field_{args.date:%Y%m%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(result, index, args.date, url.rsplit("/", 1)[-1]), "utf-8")
    print(
        f"{out} — 제보 {len(reports)}건, 맞음 {result.tp + result.tn}·덜 막음 {result.fn}·"
        f"더 막음 {result.fp}, recall {_ratio(result.recall)} precision {_ratio(result.precision)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
