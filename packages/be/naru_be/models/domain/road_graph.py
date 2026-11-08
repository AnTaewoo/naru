"""RoadGraph — 표준노드링크 서울 추출본(link.gpkg)을 NetworkX로. 구간(from→via→to)을 선으로 (T1.2).

입력은 `data/raw/nodelink_seoul_<date>/link.gpkg` (T0.3, MANIFEST "nodelink_seoul").
GeoPackage는 sqlite3로 직접 읽는다 (geom 컬럼 = GP 헤더 + WKB).
좌표계는 ITRF2000 중부원점(=EPSG:5186) → 미터 계산은 EPSG:5179, 결과 선은 WGS84 [lng, lat].

`shortest_path(points, road)`: 점마다 가장 가까운 노드(road가 있으면 그 도로명 링크의 노드)로 붙이고
이웃한 점끼리 최단경로를 잇는다. road가 있으면 먼저 그 도로명 링크만으로 찾고(ARCHITECTURE),
끊겨 있으면 다른 도로 링크에 길이 x ROAD_DETOUR_PENALTY 를 매겨 전체 그래프에서 찾는다
(세종대로는 nodelink에서 5조각).
"""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import shapely
from pyproj import Transformer
from shapely.strtree import STRtree

LngLat = tuple[float, float]
XY = tuple[float, float]
_5186_TO_5179 = Transformer.from_crs("EPSG:5186", "EPSG:5179", always_xy=True)
_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
_5179_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
ROAD_DETOUR_PENALTY = 4.0  # road 지정 시 다른 도로 링크의 길이 배수 (끊긴 구간을 잇는 용도)


@dataclass(frozen=True)
class RoadPath:
    coords: tuple[LngLat, ...]  # WGS84
    length_m: float
    roads: tuple[str, ...]  # 지난 도로명, 연속 중복 제거
    strict: bool  # road 지정 링크만으로 이어졌으면 True


def gpkg_geometry(blob: bytes) -> shapely.Geometry:
    """GeoPackage 바이너리 → shapely (헤더 GP·버전·플래그·srs_id·envelope 뒤에 WKB)."""
    if blob[:2] != b"GP":
        raise ValueError("GeoPackage 지오메트리 헤더가 아니다")
    envelope = (blob[3] >> 1) & 0b111
    envelope_len = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[envelope]
    return shapely.from_wkb(bytes(blob[8 + envelope_len :]))


class RoadGraph:
    def __init__(self, graph: nx.Graph[str], node_xy: dict[str, XY]) -> None:
        self.graph = graph
        self.node_xy = node_xy
        self._node_ids = list(node_xy)
        self._tree = STRtree([shapely.Point(xy) for xy in node_xy.values()])
        self._links = [shapely.LineString(d["coords"]) for _, _, d in graph.edges(data=True)]
        self._link_roads = [str(d["road"]) for _, _, d in graph.edges(data=True)]
        self._link_tree = STRtree(self._links)

    @classmethod
    def from_gpkg(cls, link_gpkg: Path) -> RoadGraph:
        graph: nx.Graph[str] = nx.Graph()
        node_xy: dict[str, XY] = {}
        con = sqlite3.connect(link_gpkg)
        try:
            rows = con.execute("SELECT LINK_ID, F_NODE, T_NODE, ROAD_NAME, LENGTH, geom FROM link")
            for link_id, f_node, t_node, road_name, length, blob in rows:
                line = gpkg_geometry(blob)
                if not isinstance(line, shapely.LineString):
                    raise ValueError(f"link {link_id}: LineString이 아니다 ({type(line).__name__})")
                coords = tuple(_5186_TO_5179.transform(x, y) for x, y in line.coords)
                node_xy.setdefault(f_node, coords[0])
                node_xy.setdefault(t_node, coords[-1])
                if f_node == t_node:
                    continue
                length_m = float(length)
                if graph.has_edge(f_node, t_node) and graph[f_node][t_node]["length"] <= length_m:
                    continue
                graph.add_edge(
                    f_node,
                    t_node,
                    link_id=link_id,
                    road=road_name or "",
                    length=length_m,
                    coords=coords,
                )
        finally:
            con.close()
        return cls(graph, node_xy)

    def nearest_node(self, lng: float, lat: float, road: str | None = None) -> str:
        x, y = _4326_TO_5179.transform(lng, lat)
        if road:
            candidates = {
                n for u, v, d in self.graph.edges(data=True) if d["road"] == road for n in (u, v)
            }
            if candidates:
                return min(
                    candidates,
                    key=lambda n: (self.node_xy[n][0] - x) ** 2 + (self.node_xy[n][1] - y) ** 2,
                )
        return self._node_ids[int(self._tree.nearest(shapely.Point(x, y)))]

    def nearest_road_name(self, lng: float, lat: float, max_m: float) -> str | None:
        """max_m 안에서 가장 가까운, 이름 있는 도로 링크의 도로명 (T5.10 레그 이름 대안)."""
        pt = shapely.Point(_4326_TO_5179.transform(lng, lat))
        best: tuple[float, str] | None = None
        for k in self._link_tree.query(pt.buffer(max_m)):
            name = self._link_roads[int(k)]
            dist = float(self._links[int(k)].distance(pt))
            if name and dist <= max_m and (best is None or dist < best[0]):
                best = (dist, name)
        return best[1] if best else None

    def nearest_link_distance_m(self, lng: float, lat: float) -> float:
        """가장 가까운 도로 링크까지 거리 (ADR-008: impact unknown 지점의 30 m 승격 규칙)."""
        pt = shapely.Point(_4326_TO_5179.transform(lng, lat))
        return float(self._links[int(self._link_tree.nearest(pt))].distance(pt))

    def shortest_path(self, points: Sequence[LngLat], road: str | None = None) -> RoadPath:
        if len(points) < 2:
            raise ValueError("점이 둘 이상이어야 한다")
        nodes = [self.nearest_node(lng, lat, road) for lng, lat in points]
        strict = True
        coords: list[XY] = []
        roads: list[str] = []
        total = 0.0
        for a, b in itertools.pairwise(nodes):
            path, used_strict = self._path(a, b, road)
            strict = strict and used_strict
            for u, v in itertools.pairwise(path):
                data = self.graph[u][v]
                seg = list(data["coords"])
                if seg[0] != self.node_xy[u] and seg[-1] == self.node_xy[u]:
                    seg.reverse()
                for xy in seg:
                    if not coords or coords[-1] != xy:
                        coords.append(xy)
                total += float(data["length"])
                if not roads or roads[-1] != data["road"]:
                    roads.append(data["road"])
        wgs = tuple(_5179_TO_4326.transform(x, y) for x, y in coords)
        return RoadPath(wgs, round(total, 1), tuple(roads), strict)

    def _path(self, a: str, b: str, road: str | None) -> tuple[list[str], bool]:
        if a == b:
            return [a], True
        if road:
            sub = self.graph.edge_subgraph(
                [(u, v) for u, v, d in self.graph.edges(data=True) if d["road"] == road]
            )
            if a in sub and b in sub and nx.has_path(sub, a, b):
                return list(nx.shortest_path(sub, a, b, weight="length")), True

            def penalized(u: str, v: str, d: dict[str, object]) -> float:
                return float(str(d["length"])) * (1.0 if d["road"] == road else ROAD_DETOUR_PENALTY)

            return list(nx.shortest_path(self.graph, a, b, weight=penalized)), False
        return list(nx.shortest_path(self.graph, a, b, weight="length")), True
