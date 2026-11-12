"""횡단보도 간선 이름 (T5.10) — 경로 상세의 횡단보도 레그 이름. Flask 를 모른다.

OA-23081 에는 교차로명 열이 있고 위치명 열은 없다(2026-11-07 받은 파일). 그래서 간선의
관리번호 → 교차로명, 관리번호가 없는 간선은 가까운 도로의 도로명(표준노드링크 ROAD_NAME,
crosswalk_road_name_m 안)을 road_name 에 둔다. 레그를 합칠 때는 교차로명이 먼저다(routers).
"""

from __future__ import annotations

from dataclasses import replace

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import EdgeKind, PedEdge, PedGraph
from naru_be.models.domain.road_graph import RoadGraph


def name_crosswalks(
    ped: PedGraph, index: CrosswalkIndex, road: RoadGraph, settings: Settings
) -> tuple[int, int]:
    """횡단보도 간선에 이름을 단다. (교차로명으로 단 수, 도로명으로 단 수)."""
    by_intersection = by_road = 0
    for _, _, data in ped.graph.edges(data=True):
        edge: PedEdge = data["edge"]
        if edge.kind is not EdgeKind.crosswalk:
            continue
        names = [index.get(c).intersection_name.strip() for c in edge.crosswalk_ids]
        name = next((n for n in names if n), None)
        if name:
            data["edge"] = replace(edge, name=name)
            by_intersection += 1
            continue
        lng, lat = edge.coords[len(edge.coords) // 2]
        road_name = road.nearest_road_name(lng, lat, settings.crosswalk_road_name_m)
        if road_name:
            data["edge"] = replace(edge, road_name=road_name)
            by_road += 1
    return by_intersection, by_road
