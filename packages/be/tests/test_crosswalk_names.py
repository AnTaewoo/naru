"""T5.10 — 횡단보도 레그 이름: OA-23081 교차로명, 없으면 가까운 도로의 도로명.

OA-23081 열(2026-11-07 받은 파일을 열어 확인): 연번·자치구·횡단보도관리번호·교차로관리번호·
횡단보도종류·보행등유무·교차로명·X·Y — 위치명 열은 없다. 도로명은 표준노드링크 link.gpkg ROAD_NAME.
기대값은 recorded 경로의 횡단보도 레그가 지나는 간선을 경로 순서대로 찾아 두 파일에서 확인한 값:
교보빌딩→대한문(통제 없음)은 [관리번호 없음(종로) → 세종대로사거리 …] 와 청계광장(06-0000002137),
간선 47131 은 관리번호가 없고 가장 가까운 도로가 소공로(3.4 m).
"""

from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.crosswalk_names import name_crosswalks
from naru_be.models.domain.ped_graph import EdgeKind, PedGraph
from naru_be.models.domain.road_graph import RoadGraph
from naru_be.models.domain.routers import BaselineRouter

KYOBO = (126.9779039768265, 37.5709686446227)  # 카카오 24020019 [lng, lat]
DAEHANMUN = (126.976542945622, 37.5650416322942)  # 카카오 17582477


@pytest.fixture(scope="module")
def ped(seoul_spatial_dir: Path, nodelink_seoul_dir: Path) -> PedGraph:
    settings = Settings()
    road = RoadGraph.from_gpkg(nodelink_seoul_dir / "link.gpkg")
    graph = PedGraph.from_seoul_spatial(seoul_spatial_dir, settings)
    index = CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", settings, road)
    named = name_crosswalks(graph, index, road, settings)
    # 횡단보도 간선 1,346 = 관리번호 있는 819(전부 교차로명) + 없는 527. 527 중 501 은 20 m 안에
    # 이름 있는 도로가 있고 26 은 없어 이름 없이 남는다(FE 는 '횡단보도') — 2026-11-08 실데이터로 잼
    assert named == (819, 501)
    return graph


def test_crosswalk_legs_are_named_intersection_first(ped: PedGraph) -> None:
    path = BaselineRouter(ped, Settings()).route(KYOBO, DAEHANMUN)
    names = [leg.name for leg in path.legs if leg.kind is EdgeKind.crosswalk]
    # 첫 레그는 관리번호 없는 간선(가까운 도로 종로)으로 시작하지만 교차로명이 먼저다
    assert names == ["세종대로사거리", "청계광장"]


def test_edge_without_crosswalk_id_gets_nearest_road(ped: PedGraph) -> None:
    edges = [d["edge"] for _, _, d in ped.graph.edges(data=True) if d["edge"].link_id == "47131"]
    (edge,) = edges
    assert edge.kind is EdgeKind.crosswalk and edge.crosswalk_ids == ()
    assert (edge.name, edge.road_name) == (None, "소공로")
