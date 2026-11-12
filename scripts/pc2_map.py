"""PC-2 지도 — 시각표의 통제 전·중·후 3시각에 폐쇄 횡단보도를 folium 으로 (ROADMAP PC-2).

  uv run python scripts/pc2_map.py            → pc2_map.html
기록된 코스 후보(T2.2) 16개를 CrosswalkIndex(15 m 버퍼)로 횡단보도에 붙이고 ClosureEngine(T2.3)으로
3시각(출발 전 06:30 · 통제 중 07:45 · 통제 후 13:00, 2026-03-15 KST)의 상태를 계산해 레이어 셋으로
그린다. scheduled 노랑 · confirmed 빨강 · released 회색 (ARCHITECTURE FE 색). DB 는 안 거친다.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import folium

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_contracts import CandidateBatch, LineGeom

KST = timezone(timedelta(hours=9))
TIMES = (
    ("출발 전 06:30", datetime(2026, 3, 15, 6, 30, tzinfo=KST)),
    ("통제 중 07:45", datetime(2026, 3, 15, 7, 45, tzinfo=KST)),
    ("통제 후 13:00", datetime(2026, 3, 15, 13, 0, tzinfo=KST)),
)
COLOR = {
    "scheduled": "#f2c200",
    "confirmed": "#d7263d",
    "released": "#8a8a8a",
    "zone_scheduled": "#9b59b6",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PC-2 folium 지도")
    ap.add_argument("--out", type=Path, default=Path("pc2_map.html"))
    args = ap.parse_args(argv)
    settings = Settings()
    raw = settings.data_dir / "raw"
    spatial = sorted(raw.glob("seoul_spatial_*"))[-1]
    batch_file = sorted((settings.data_dir / "recorded" / "candidates" / "course").glob("*.json"))[
        -1
    ]
    batch = CandidateBatch.model_validate(json.loads(batch_file.read_text("utf-8")))
    index = CrosswalkIndex.from_xlsx(spatial / "OA-23081.xlsx", settings)
    engine = ClosureEngine(index, settings)

    m = folium.Map(location=[37.5675, 126.9775], zoom_start=14)
    course = folium.FeatureGroup(name="코스 (기록된 후보 16구간)")
    for c in batch.candidates:
        if isinstance(c.geometry, LineGeom):
            folium.PolyLine(
                [(lat, lng) for lng, lat in c.geometry.coordinates],
                color="#1f6feb",
                weight=3,
                opacity=0.6,
                tooltip=c.candidate_id,
            ).add_to(course)
    course.add_to(m)
    for label, at in TIMES:
        counts: dict[str, int] = {}
        layer = folium.FeatureGroup(name=label, show=label.startswith("통제 중"))
        for c in batch.candidates:
            if not isinstance(c.geometry, LineGeom):
                continue
            for s in engine.apply(c, index.from_line(c.geometry.coordinates), at=at):
                counts[s.status.value] = counts.get(s.status.value, 0) + 1
                folium.CircleMarker(
                    (s.lat, s.lng),
                    radius=5,
                    color=COLOR[s.status.value],
                    fill=True,
                    fill_opacity=0.9,
                    tooltip=f"{s.crosswalk_id} {s.status.value} {s.reason}",
                ).add_to(layer)
        layer.layer_name = f"{label} — " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(args.out))
    print(f"{args.out} — 후보 {len(batch.candidates)}개, 시각 {len(TIMES)}개 ({batch_file.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
