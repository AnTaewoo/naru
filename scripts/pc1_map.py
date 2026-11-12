"""PC-1 지도 — PedGraph 간선(kind별 색)과 from_segment 결과를 folium으로 (ROADMAP PC-1).

  uv run python scripts/pc1_map.py            → pc1_map.html (광화문 일대)
  uv run python scripts/pc1_map.py --all      → 종로·중구 전체 (파일이 커진다)

그리는 것: 횡단보도 빨강 · 지하도 파랑 · 육교 초록 · 계단/엘리베이터 보라 · 보도 회색(얇게),
관리번호 점(주황), from_segment(숭례문 → 시청앞교차로, road=세종대로) 경로(검정 굵게)와
25 m 버퍼(검정 반투명), 걸린 횡단보도(노랑 큰 점).
좌표는 전부 데이터에서: 숭례문은 카카오 기록, 시청앞교차로는 노드링크 노드 1010024202.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import folium
import shapely
from pyproj import Transformer

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import PedGraph
from naru_be.models.domain.road_graph import RoadGraph
from naru_contracts import PlacePoint, RoadClass, SegmentGeom

COLORS = {
    "crosswalk": ("#d7263d", 4),
    "underpass": ("#1f6feb", 4),
    "overpass": ("#2a9d8f", 4),
    "stairs": ("#8e44ad", 3),
    "elevator": ("#8e44ad", 3),
    "station": ("#e67e22", 4),
    "sidewalk": ("#9a9a9a", 1),
}
GWANGHWAMUN = (126.965, 37.555, 126.990, 37.580)  # lng/lat bbox (광화문·시청·숭례문)
SUNGNYEMUN = PlacePoint(
    canonical="숭례문",
    lng=126.975313124237,
    lat=37.5600030088843,
    gazetteer_source="kakao",
    gazetteer_id="7813430",
)
CITY_HALL = PlacePoint(
    canonical="시청앞교차로",
    lng=126.97727,
    lat=37.5649,
    gazetteer_source="nodelink",
    gazetteer_id="1010024202",
)
_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
_5179_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def _inside(
    coords: tuple[tuple[float, float], ...], bbox: tuple[float, float, float, float] | None
) -> bool:
    if bbox is None:
        return True
    return any(bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3] for x, y in coords)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PC-1 folium 지도")
    ap.add_argument("--out", type=Path, default=Path("pc1_map.html"))
    ap.add_argument("--all", action="store_true", help="종로·중구 전체")
    args = ap.parse_args(argv)
    settings = Settings()
    raw = settings.data_dir / "raw"
    spatial = sorted(raw.glob("seoul_spatial_*"))[-1]
    nodelink = sorted(raw.glob("nodelink_seoul_*"))[-1]
    bbox = None if args.all else GWANGHWAMUN

    ped = PedGraph.from_seoul_spatial(spatial, settings)
    road_graph = RoadGraph.from_gpkg(nodelink / "link.gpkg")
    index = CrosswalkIndex.from_xlsx(spatial / "OA-23081.xlsx", settings, road_graph)

    m = folium.Map(location=[37.5675, 126.9775], zoom_start=15)  # OSM 타일 (키 불필요)
    layers = {
        kind: folium.FeatureGroup(name=f"{kind} ({n})") for kind, n in ped.stats.kinds.items()
    }
    for _, _, e in ped.edges():
        if not _inside(e.coords, bbox):
            continue
        color, weight = COLORS[e.kind.value]
        tip = f"{e.kind.value} {e.link_id} {e.length_m:.0f} m" + (
            f" 횡단보도 {','.join(e.crosswalk_ids)}" if e.crosswalk_ids else ""
        )
        folium.PolyLine(
            [(lat, lng) for lng, lat in e.coords],
            color=color,
            weight=weight,
            opacity=0.8,
            tooltip=tip,
        ).add_to(layers[e.kind.value])
    for layer in layers.values():
        layer.add_to(m)

    points = folium.FeatureGroup(name=f"횡단보도 관리번호 ({len(index)})")
    for c in index.crosswalks:
        if _inside(((c.lng, c.lat),), bbox):
            folium.CircleMarker(
                (c.lat, c.lng),
                radius=3,
                color="#ff8c00",
                fill=True,
                fill_opacity=0.9,
                tooltip=f"{c.crosswalk_id} {c.intersection_name} {c.kind}",
            ).add_to(points)
    points.add_to(m)

    seg = SegmentGeom(from_=SUNGNYEMUN, to=CITY_HALL, road="세종대로", road_class=RoadClass.daero)
    path = road_graph.shortest_path(
        [(SUNGNYEMUN.lng, SUNGNYEMUN.lat), (CITY_HALL.lng, CITY_HALL.lat)], road="세종대로"
    )
    hits = index.from_segment(seg)
    buffer_m = settings.road_buffer_m[RoadClass.daero.value]
    line = shapely.LineString(
        [_4326_TO_5179.transform(lng, lat) for lng, lat in path.coords]
    ).buffer(buffer_m)
    seg_layer = folium.FeatureGroup(
        name=f"from_segment 숭례문→시청 세종대로 ({len(hits)}개, {path.length_m:.0f} m)"
    )
    folium.Polygon(
        [
            (lat, lng)
            for lng, lat in (_5179_TO_4326.transform(x, y) for x, y in line.exterior.coords)
        ],
        color="#000",
        weight=1,
        fill=True,
        fill_opacity=0.12,
    ).add_to(seg_layer)
    folium.PolyLine(
        [(lat, lng) for lng, lat in path.coords],
        color="#000",
        weight=5,
        tooltip=f"{' > '.join(path.roads)} {path.length_m:.0f} m",
    ).add_to(seg_layer)
    for cid in sorted(hits):
        c = index.get(cid)
        folium.CircleMarker(
            (c.lat, c.lng),
            radius=7,
            color="#ffd400",
            fill=True,
            fill_opacity=1.0,
            tooltip=f"걸림 {cid} {c.intersection_name}",
        ).add_to(seg_layer)
    seg_layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(args.out))
    print(
        f"{args.out} — 간선 {ped.stats.edges}, 관리번호 {len(index)}, "
        f"from_segment {len(hits)}개 {sorted(hits)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
