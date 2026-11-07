"""T0.3 — 표준노드링크 서울 추출본(node.gpkg·link.gpkg)이 RoadGraph 입력으로 쓸 만한지 (실데이터).

기대값은 2026-11-07에 원본 shp(nodelink_20261014)와 추출본을 열어 확인한 값. 옆 주석이 확인 방법.
"""

from pathlib import Path

import geopandas as gpd


def _read(d: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    return gpd.read_file(d / "node.gpkg"), gpd.read_file(d / "link.gpkg")


def test_nodes_and_links_open(nodelink_seoul_dir: Path) -> None:
    nodes, links = _read(nodelink_seoul_dir)
    assert len(nodes) > 1000  # ROADMAP T0.3 기준
    # 서울 = ID 앞 2자리 10·11·12. prefix별 건수 합 (2026-11-07): 노드 46,085 / 링크 63,383
    assert len(nodes) == 46085 and len(links) == 63383
    assert {"NODE_ID", "NODE_TYPE", "NODE_NAME"} <= set(nodes.columns)
    assert {"LINK_ID", "F_NODE", "T_NODE", "ROAD_RANK", "ROAD_NAME", "LANES", "LENGTH"} <= set(
        links.columns
    )
    assert nodes.crs is not None and nodes.crs.is_projected and links.crs == nodes.crs
    assert nodes["NODE_ID"].str.len().eq(10).all() and nodes["NODE_ID"].is_unique
    assert links["LINK_ID"].is_unique
    assert nodes.geom_type.eq("Point").all() and links.geom_type.eq("LineString").all()


def test_demo_districts_present(nodelink_seoul_dir: Path) -> None:
    nodes, _ = _read(nodelink_seoul_dir)
    # ID 앞 4자리 = 자치구. 1000 종로구 1,348 / 1010 중구 1,212 / 1180 영등포구 2,640 노드
    prefix = nodes["NODE_ID"].str[:4]
    assert (prefix == "1000").sum() == 1348
    assert (prefix == "1010").sum() == 1212
    assert (prefix == "1180").sum() == 2640
    # 광화문 근처(126.974~126.980, 37.568~37.578)에서 찾은 노드: NODE_ID 1000018200 '경복궁'
    gyeongbok = nodes[nodes["NODE_ID"] == "1000018200"]
    assert gyeongbok["NODE_NAME"].item() == "경복궁"
    pt = gyeongbok.to_crs(4326).geometry.item()
    assert pt.x > 126.974 and pt.x < 126.980
    assert pt.y > 37.568 and pt.y < 37.578


def test_sejongdaero_links(nodelink_seoul_dir: Path) -> None:
    nodes, links = _read(nodelink_seoul_dir)
    sj = links[links["ROAD_NAME"] == "세종대로"]
    assert len(sj) == 59  # 전국 원본에서도 59 (앞 4자리 1010 36개 + 1000 23개)
    assert set(sj["LINK_ID"].str[:4]) == {"1000", "1010"}
    b = sj.to_crs(4326).total_bounds  # 광화문~서울역: 126.9726~126.9773, 37.5566~37.5753
    assert b[0] > 126.972 and b[2] < 126.978
    assert b[1] > 37.556 and b[3] < 37.576
    node_ids = set(nodes["NODE_ID"])
    assert sj["F_NODE"].isin(node_ids).all() and sj["T_NODE"].isin(node_ids).all()
    # T1.2 road_class: 도로명 접미사 대로/로/길. 앞 2자리 11만 세도 대로 1,168 · 길 11,820
    name = links["ROAD_NAME"].fillna("")
    assert name.str.endswith("대로").sum() > 1000
    assert name.str.endswith("길").sum() > 1000
