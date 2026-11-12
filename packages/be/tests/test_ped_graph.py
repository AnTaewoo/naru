"""T1.1 — PedGraph: 종로구·중구 도보망 + 오버레이 → NetworkX (실데이터).

서비스 범위는 T6.9 부터 서울 전체지만, 이 파일은 종로·중구로 고정해 T1.1 에서 손으로 확인한 값을
그대로 지킨다. 서울 전체 크기는 test_seoul_coverage.

기대값은 2026-11-07 seoul_spatial_20261107 을 열어 확인한 값. 옆 주석이 확인 방법.
"""

from pathlib import Path

import networkx as nx
import pytest

from naru_be.config import Settings
from naru_be.models.domain.ped_graph import EdgeKind, PedGraph

CENTRAL = (126.90, 37.45, 127.10, 37.70)  # 종로·중구 WGS84 범위


@pytest.fixture(scope="module")
def ped(seoul_spatial_dir: Path) -> PedGraph:
    return PedGraph.from_seoul_spatial(seoul_spatial_dir, Settings(districts=("종로구", "중구")))


def test_graph_size_and_connectivity(ped: PedGraph) -> None:
    s = ped.stats
    assert s.nodes > 0 and s.edges > 0  # ROADMAP T1.1
    assert s.largest_component_ratio >= 0.8  # ROADMAP T1.1. 실제 98.0%
    # 도보망 노드 14,377(+끝점 보강)·링크 18,511(중복쌍 66, self-loop 19 제외) + 지하도·육교
    assert s.nodes == 15183 and s.edges == 19067
    assert s.self_loops_dropped == 19 and s.parallel_dropped == 66
    assert all(
        CENTRAL[0] < d["lng"] < CENTRAL[2] and CENTRAL[1] < d["lat"] < CENTRAL[3]
        for _, d in ped.graph.nodes(data=True)
    )
    assert nx.is_connected(ped.graph.subgraph(max(nx.connected_components(ped.graph), key=len)))


def test_edge_kinds(ped: PedGraph) -> None:
    k = ped.stats.kinds
    assert k["crosswalk"] > 100  # ROADMAP T1.1
    # 양 끝 CRSWK 노드 링크 1,084 과 대로변 횡단보도 오버레이 843 의 합집합 1,134 → 중복 제거 1,125
    # + 관리번호 점이 얹힌 60 m 이하 sidewalk 221개 승격 = 1,346
    assert k["crosswalk"] == 1346
    assert k["station"] == 2  # SBWY_NTW=1 링크
    assert k["underpass"] == 397  # 지하도 오버레이 링크 (종로·중구)
    assert k["overpass"] == 89  # 육교 오버레이 링크
    assert k["stairs"] + k["elevator"] == ped.stats.connectors == 244  # 출입구 266개 중 30 m 안
    assert k["elevator"] == 55  # LIFT 또는 ELVT=1 출입구
    for _, _, e in ped.edges():
        assert e.length_m > 0 and len(e.coords) >= 2
        assert e.kind != EdgeKind.crosswalk or e.length_m < 1000


def test_crosswalk_ids_attached(ped: PedGraph) -> None:
    s = ped.stats
    # OA-23081 종로·중구 1,211점: 횡단보도 간선 15 m 안 767 + 아무 간선 8 m 안 371, 미매칭 73
    assert s.crosswalk_ids_attached == 1138 and s.crosswalk_points_unmatched == 73
    with_ids = [e for _, _, e in ped.edges() if e.crosswalk_ids]
    assert len(with_ids) == 953
    assert sum(1 for e in with_ids if e.kind == EdgeKind.crosswalk) == 819
    assert {e.kind for e in with_ids} <= {
        EdgeKind.crosswalk,
        EdgeKind.sidewalk,
        EdgeKind.underpass,
        EdgeKind.overpass,
        EdgeKind.stairs,
    }
    # 세종대로사거리 관리번호 06-0000029520 → 링크 25607 (점이 간선에서 0.8 m, 2026-11-07 확인)
    e = ped.edge_by_link("25607")
    assert e is not None and e.kind == EdgeKind.crosswalk and e.crosswalk_ids == ("06-0000029520",)
    # 세종대로사거리 8개 관리번호(교차로관리번호 535)는 모두 crosswalk 간선 6개에 붙어 있다
    sejong = {
        "06-0000046713",
        "06-0000036391",
        "06-0000029520",
        "06-0000046716",
        "06-0000023206",
        "06-0000023205",
        "06-0000035426",
        "06-0000023200",
    }
    hits = {
        (ee.link_id, ee.kind)
        for _, _, ee in ped.edges()
        for cid in ee.crosswalk_ids
        if cid in sejong
    }
    assert len(hits) == 6 and all(kind == EdgeKind.crosswalk for _, kind in hits)
