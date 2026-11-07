"""T1.2 — CrosswalkIndex.from_point / from_line / from_segment + RoadGraph (실데이터).

좌표는 전부 데이터에서 뽑았다 (2026-11-07 확인, 옆 주석). 기대값도 데이터를 열어 확인한 값.
"""

import itertools
from pathlib import Path

import gpxpy
import networkx as nx
import pytest
from pyproj import Transformer

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.road_graph import RoadGraph
from naru_contracts import PlacePoint, RoadClass, SegmentGeom

# 세종대로사거리 — nodelink_seoul 노드 1000009004 'NODE_NAME 세종대로사거리' (광화문광장 남단)
SEJONGDAERO_SAGEORI = (126.97698, 37.57023)
# 숭례문 — data/recorded/kakao/keyword 765cd74f….json documents[0] (id 7813430)
SUNGNYEMUN = PlacePoint(
    canonical="숭례문",
    lng=126.975313124237,
    lat=37.5600030088843,
    gazetteer_source="kakao",
    gazetteer_id="7813430",
)
# 시청앞교차로 — nodelink_seoul 노드 1010024202 (세종대로 위, 덕수궁 대한문 앞)
CITY_HALL = PlacePoint(
    canonical="시청앞교차로",
    lng=126.97727,
    lat=37.5649,
    gazetteer_source="nodelink",
    gazetteer_id="1010024202",
)


@pytest.fixture(scope="module")
def road_graph(nodelink_seoul_dir: Path) -> RoadGraph:
    return RoadGraph.from_gpkg(nodelink_seoul_dir / "link.gpkg")


@pytest.fixture(scope="module")
def index(seoul_spatial_dir: Path, road_graph: RoadGraph) -> CrosswalkIndex:
    return CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", Settings(), road_graph)


def test_index_loads_jongno_junggu(index: CrosswalkIndex) -> None:
    assert len(index) == 1211  # OA-23081 종로구 590 + 중구 621
    c = index.get("06-0000029520")  # 세종대로사거리 이단(화살표있음), 교차로관리번호 535
    assert c.intersection_name == "세종대로사거리" and c.intersection_id == "535"
    assert 126.975 < c.lng < 126.978 and 37.569 < c.lat < 37.571


def test_from_point_gwanghwamun(index: CrosswalkIndex) -> None:
    ids = index.from_point(*SEJONGDAERO_SAGEORI, 30)  # ROADMAP (b)
    assert ids  # 세종대로사거리 8점 중 중심에서 9·13·24·27 m 인 4점
    assert all(index.get(i).intersection_name == "세종대로사거리" for i in ids)
    assert len(index.from_point(*SEJONGDAERO_SAGEORI, 60)) >= len(ids)
    assert index.from_point(*SEJONGDAERO_SAGEORI, 1) == set()


def test_from_line_course_sejongdaero(index: CrosswalkIndex, course_dir: Path) -> None:
    # ROADMAP (a): 코스 GPX 첫 1.4 km (출발 → 세종대로사거리 → 숭례문, course_meta 0.30 + 1.10 km)
    gpx = gpxpy.parse((course_dir / "seoul_marathon_2026.gpx").read_text("utf-8"))
    pts = [(p.longitude, p.latitude) for t in gpx.tracks for s in t.segments for p in s.points]
    coords = []
    total = 0.0
    for prev, cur in itertools.pairwise(pts):
        coords.append(prev)
        total += ((cur[0] - prev[0]) * 88_400) ** 2 + ((cur[1] - prev[1]) * 110_574) ** 2
        if total**0.5 > 1_400**2:
            break
    ids = index.from_line(coords[: max(2, len(coords))], 15)
    names = {index.get(i).intersection_name for i in ids}
    assert any("세종대로" in n for n in names)
    assert "숭례문" in names or "세종대로사거리" in names


def test_from_segment_sungnyemun_to_cityhall_on_sejongdaero(
    index: CrosswalkIndex, road_graph: RoadGraph
) -> None:
    # ROADMAP (c): 숭례문 → 시청, road=세종대로 → 세종대로 횡단보도만, 종로 횡단보도 없음
    seg = SegmentGeom(from_=SUNGNYEMUN, to=CITY_HALL, road="세종대로", road_class=RoadClass.daero)
    path = road_graph.shortest_path(
        [(SUNGNYEMUN.lng, SUNGNYEMUN.lat), (CITY_HALL.lng, CITY_HALL.lat)], road="세종대로"
    )
    assert 400 < path.length_m < 900  # 숭례문 ~ 시청앞교차로 세종대로 약 550 m
    assert "세종대로" in path.roads
    ids = index.from_segment(seg)
    names = {index.get(i).intersection_name for i in ids}
    assert names and not any("종로" in n for n in names)
    assert "숭례문" in names or "시청" in names
    # 25 m 버퍼(대로)는 15 m 버퍼보다 넓다
    assert ids >= index.from_line(path.coords, 15)


def test_road_graph_strict_on_sejongdaero(road_graph: RoadGraph) -> None:
    # 숭례문앞교차로(노드 1010013802) → 세종대로사거리. road=세종대로면 그 도로 노드·링크만 지난다
    sungnyemun = (126.97576, 37.56051)
    path = road_graph.shortest_path([sungnyemun, SEJONGDAERO_SAGEORI], road="세종대로")
    assert path.strict and path.roads == ("세종대로",)
    assert 1000 < path.length_m < 1300  # 1,102 m (2026-11-07). 전체 그래프 최단은 1,100 m
    free = road_graph.shortest_path(
        [sungnyemun, SEJONGDAERO_SAGEORI]
    )  # 가장 가까운 노드로 붙어 1,106 m
    assert free.strict and 1000 < free.length_m < 1300 and "세종대로" in free.roads


def test_road_graph_falls_back_when_road_is_broken(road_graph: RoadGraph) -> None:
    # 세종대로 링크(59개)는 nodelink에서 5조각 — 다른 조각의 노드끼리는 strict 로 못 잇고 폴백한다
    g = road_graph.graph
    sub = g.edge_subgraph([(u, v) for u, v, d in g.edges(data=True) if d["road"] == "세종대로"])
    comps = sorted((sorted(c) for c in nx.connected_components(sub)), key=len, reverse=True)
    assert len(comps) == 5
    a, b = comps[0][0], comps[1][0]
    to_wgs = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    pts = [to_wgs.transform(*road_graph.node_xy[n]) for n in (a, b)]
    path = road_graph.shortest_path(pts, road="세종대로")
    assert not path.strict and "세종대로" in path.roads and len(path.roads) >= 2
    assert path.length_m > 0 and len(path.coords) >= 2
