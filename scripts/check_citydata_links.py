"""citydata 도로 링크 ID ↔ 표준노드링크 1회 대조 (T7.19, 멘토링 T-E) — 요청 없음.

  uv run python scripts/check_citydata_links.py            # recorded/rtd 의 citydata 기록 전부

기록된 ROAD_TRAFFIC_STTS 링크마다: 같은 LINK_ID 가 raw/nodelink_seoul_*/link.gpkg 에 있나, 있으면
양 끝 좌표(START_ND_XY·END_ND_XY)가 그 링크 선의 양 끝과 10 m 안에서 맞나(같은 방향 / 반대 방향).
결과는 docs/data/indirect_signals.md 에 적는다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point

DATA = Path("data")
TO_M = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
NEAR_M = 10.0


def _latest(root: Path, pattern: str) -> Path:
    found = sorted(root.glob(pattern))
    if not found:
        raise SystemExit(f"없음: {root / pattern}")
    return found[-1]


def _xy(s: str) -> tuple[float, float]:
    lng, lat = s.split("_")
    return TO_M.transform(float(lng), float(lat))


def main() -> int:
    recorded = DATA / "recorded" / "rtd"
    files = sorted(recorded.glob("*_citydata*.json")) + sorted(
        (recorded / "signals").glob("*_citydata_*.json")
    )
    links: dict[str, dict[str, str]] = {}
    areas: set[str] = set()
    for f in files:
        rec = json.loads(f.read_text("utf-8"))
        raw = rec["raw"]
        body = json.loads(raw) if isinstance(raw, str) else raw
        city = body.get("CITYDATA") or {}
        areas.add(str(city.get("AREA_NM")))
        for it in (city.get("ROAD_TRAFFIC_STTS") or {}).get("ROAD_TRAFFIC_STTS") or []:
            links[str(it["LINK_ID"])] = it
    print(f"기록 {len(files)}개, 장소 {sorted(areas)}, 링크(LINK_ID 기준) {len(links)}개")
    gpkg = _latest(DATA / "raw", "nodelink_seoul_*") / "link.gpkg"
    g = gpd.read_file(gpkg, columns=["LINK_ID", "F_NODE", "T_NODE", "ROAD_NAME"]).to_crs(5179)
    by_id = g.set_index(g["LINK_ID"].astype(str))
    have = same = reverse = far = 0
    far_examples: list[tuple[str, str, int]] = []
    for lid, it in links.items():
        if lid not in by_id.index:
            continue
        have += 1
        geom = by_id.loc[lid, "geometry"]
        line = geom.geoms[0] if geom.geom_type == "MultiLineString" else geom
        head, tail = Point(line.coords[0]), Point(line.coords[-1])
        s, e = Point(_xy(it["START_ND_XY"])), Point(_xy(it["END_ND_XY"]))
        d_same = max(head.distance(s), tail.distance(e))
        d_rev = max(head.distance(e), tail.distance(s))
        if d_same <= NEAR_M:
            same += 1
        elif d_rev <= NEAR_M:
            reverse += 1
        else:
            far += 1
            far_examples.append((lid, it["ROAD_NM"], round(min(d_same, d_rev))))
    n = len(links)
    print(f"표준노드링크에 같은 LINK_ID: {have}/{n} ({have / n:.0%})")
    print(f"  양 끝 10 m 안 — 같은 방향 {same} · 반대 방향 {reverse} · 10 m 밖 {far}")
    if far_examples:
        print("  10 m 밖 예:", far_examples[:8])
    print(f"gpkg: {gpkg.name}, 링크 {len(g)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
