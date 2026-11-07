"""PedGraph — 서울 도보 네트워크를 NetworkX 그래프로 (ARCHITECTURE §BE Model, ROADMAP T1.1).

입력은 `data/raw/seoul_spatial_<date>/` (T0.2, MANIFEST "seoul_spatial"):
  TbTraficWlkNet_seoul/   도보망 전체. SGG_NM으로 자치구를 고른다
                          (SGG 필터 API는 페이지가 겹쳐 못 쓴다)
  tbTraficCrsng/          대로변 횡단보도 (도보망 링크 ID와 같다)
  tbTraficBrdge/          육교 (노드가 도보망 노드와 같다)
  tbTraficUndpass/        지하철역 연계 지하도 — 별도 망. 출입구(차수 1)를 도보망 노드에 잇는다
  OA-23081.xlsx           횡단보도 관리번호 (EPSG:5186) — 가장 가까운 횡단보도 간선에 붙인다

edge.kind (유형코드표·플래그·오버레이로 정함, 2026-11-07 데이터를 열어 확인):
  crosswalk  양 끝 노드가 CRSWK=1 이거나 대로변 횡단보도 오버레이에 있는 링크
             (종로·중구 1,134개, 중앙값 20 m)
             — 링크 자체의 CRSWK 플래그(565개, 중앙값 40 m)는 횡단보도가 아니라서 쓰지 않는다
  station    SBWY_NTW=1 링크           overpass  육교 오버레이 링크
  underpass  지하도 오버레이 링크
  stairs/elevator  지하도 출입구 ↔ 도보망 노드 연결 (LIFT·ELVT=1이면 elevator)
  sidewalk   나머지
좌표는 WGS84 [lng, lat]로 두고, 거리는 EPSG:5179 미터로 잰다. Flask를 모른다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import networkx as nx
import openpyxl
import shapely
import shapely.wkt
from pyproj import Transformer
from shapely.strtree import STRtree

from naru_be.config import Settings

LngLat = tuple[float, float]
_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
_5186_TO_5179 = Transformer.from_crs("EPSG:5186", "EPSG:5179", always_xy=True)


class EdgeKind(StrEnum):
    sidewalk = "sidewalk"
    crosswalk = "crosswalk"
    underpass = "underpass"
    overpass = "overpass"
    stairs = "stairs"
    elevator = "elevator"
    station = "station"


@dataclass(frozen=True)
class PedEdge:
    link_id: str
    kind: EdgeKind
    length_m: float
    crosswalk_ids: tuple[str, ...]  # 횡단보도 관리번호 (OA-23081). crosswalk 간선에만, 없을 수 있다
    coords: tuple[LngLat, ...]  # WGS84, u → v 순서
    name: str | None = None  # 지하도는 '<역명> 지하보도', 육교는 '육교'. 나머지 None (legs 이름)


@dataclass(frozen=True)
class BuildStats:
    nodes: int
    edges: int
    kinds: dict[str, int]
    largest_component_ratio: float
    crosswalk_ids_attached: int
    crosswalk_points_unmatched: int
    connectors: int
    parallel_dropped: int
    self_loops_dropped: int


def _read_rows(service_dir: Path) -> Iterator[dict[str, Any]]:
    for page in sorted(service_dir.glob("*.json")):
        payload = next(iter(json.loads(page.read_bytes()).values()))
        yield from payload["row"]


def _id(value: object) -> str:
    """API는 ID를 float(149760.0)로 준다 → '149760'."""
    return str(int(float(str(value))))


def _wkt_coords(wkt: str) -> tuple[LngLat, ...]:
    return tuple((float(x), float(y)) for x, y in shapely.wkt.loads(wkt).coords)


def _to_m(coords: Iterable[LngLat]) -> list[tuple[float, float]]:
    return [_TO_5179.transform(x, y) for x, y in coords]


def kind_name(kind: EdgeKind) -> str | None:
    return {EdgeKind.underpass: "지하보도", EdgeKind.overpass: "육교"}.get(kind)


def latest_spatial_dir(data_dir: Path) -> Path:
    dirs = sorted((data_dir / "raw").glob("seoul_spatial_*"))
    if not dirs:
        raise FileNotFoundError(
            "data/raw/seoul_spatial_<date>/ 없음 — make fetch SRC=seoul_spatial"
        )
    return dirs[-1]


class PedGraph:
    """보행 그래프. 노드 속성 lng, lat, x, y(5179 m), node_type, source. 간선 속성 edge, weight."""

    def __init__(self, graph: nx.Graph[str], stats: BuildStats) -> None:
        self.graph = graph
        self.stats = stats
        self._node_ids = list(graph.nodes)
        self._tree = STRtree(
            [shapely.Point(graph.nodes[n]["x"], graph.nodes[n]["y"]) for n in self._node_ids]
        )

    def nearest_node(self, lng: float, lat: float) -> tuple[str, float]:
        """가장 가까운 노드와 거리(m)."""
        x, y = _TO_5179.transform(lng, lat)
        p = shapely.Point(x, y)
        i = int(self._tree.nearest(p))
        n = self._node_ids[i]
        return n, p.distance(shapely.Point(self.graph.nodes[n]["x"], self.graph.nodes[n]["y"]))

    @classmethod
    def from_seoul_spatial(cls, spatial_dir: Path, settings: Settings | None = None) -> PedGraph:
        settings = settings or Settings()
        builder = _Builder(spatial_dir, settings)
        return builder.build()

    def edges(self, kind: EdgeKind | None = None) -> Iterator[tuple[str, str, PedEdge]]:
        for u, v, data in self.graph.edges(data=True):
            edge: PedEdge = data["edge"]
            if kind is None or edge.kind == kind:
                yield u, v, edge

    def edge_by_link(self, link_id: str) -> PedEdge | None:
        for _, _, edge in self.edges():
            if edge.link_id == link_id:
                return edge
        return None


class _Builder:
    def __init__(self, spatial_dir: Path, settings: Settings) -> None:
        self.dir = spatial_dir
        self.settings = settings
        self.g: nx.Graph[str] = nx.Graph()
        self.parallel_dropped = 0
        self.self_loops_dropped = 0
        self.connectors = 0

    # --- 노드·간선 추가 ---------------------------------------------------------------
    def _add_node(self, node_id: str, lng: float, lat: float, node_type: str, source: str) -> None:
        if node_id in self.g:
            return
        x, y = _TO_5179.transform(lng, lat)
        self.g.add_node(node_id, lng=lng, lat=lat, x=x, y=y, node_type=node_type, source=source)

    def _add_edge(self, u: str, v: str, edge: PedEdge) -> bool:
        if u == v:
            self.self_loops_dropped += 1
            return False
        if self.g.has_edge(u, v):
            current: PedEdge = self.g[u][v]["edge"]
            self.parallel_dropped += 1
            if current.length_m <= edge.length_m:
                return False
        self.g.add_edge(u, v, edge=edge, weight=edge.length_m)
        return True

    def _ensure_endpoints(
        self, row: dict[str, Any], coords: tuple[LngLat, ...], prefix: str
    ) -> tuple[str, str]:
        u, v = prefix + _id(row["BGNG_LNKG_ID"]), prefix + _id(row["END_LNKG_ID"])
        self._add_node(u, coords[0][0], coords[0][1], "0", "link-endpoint")
        self._add_node(v, coords[-1][0], coords[-1][1], "0", "link-endpoint")
        return u, v

    # --- 단계 -------------------------------------------------------------------------
    def build(self) -> PedGraph:
        districts = set(self.settings.districts)
        walk = [
            r for r in _read_rows(self.dir / "TbTraficWlkNet_seoul") if r["SGG_NM"] in districts
        ]
        crosswalk_overlay = {
            _id(r["LNKG_ID"])
            for r in _read_rows(self.dir / "tbTraficCrsng")
            if r["NODE_TYPE"] == "LINK" and r["SGG_NM"] in districts
        }
        bridge_rows = [
            r for r in _read_rows(self.dir / "tbTraficBrdge") if r["SGG_NM"] in districts
        ]
        underpass_rows = [
            r for r in _read_rows(self.dir / "tbTraficUndpass") if r["SGG_NM"] in districts
        ]

        crosswalk_nodes: set[str] = set()
        for r in walk:
            if r["NODE_TYPE"] == "NODE":
                nid = _id(r["NODE_ID"])
                lng, lat = _wkt_coords(r["NODE_WKT"])[0]
                self._add_node(nid, lng, lat, r["NODE_TYPE_CD"], "walk")
                if r["CRSWK"] == "1":
                    crosswalk_nodes.add(nid)
        bridge_links = {_id(r["LNKG_ID"]) for r in bridge_rows if r["NODE_TYPE"] == "LINK"}
        for r in walk:
            if r["NODE_TYPE"] != "LINK":
                continue
            coords = _wkt_coords(r["LNKG_WKT"])
            u, v = self._ensure_endpoints(r, coords, "")
            link_id = _id(r["LNKG_ID"])
            if link_id in bridge_links:
                kind = EdgeKind.overpass
            elif r["SBWY_NTW"] == "1":
                kind = EdgeKind.station
            elif link_id in crosswalk_overlay or (u in crosswalk_nodes and v in crosswalk_nodes):
                kind = EdgeKind.crosswalk
            else:
                kind = EdgeKind.sidewalk
            self._add_edge(u, v, PedEdge(link_id, kind, float(r["LNKG_LEN"]), (), coords))

        self._add_overlay_links(bridge_rows, EdgeKind.overpass, prefix="")
        self._add_underpass(underpass_rows)
        attached, unmatched = self._attach_crosswalk_ids()
        return PedGraph(self.g, self._stats(attached, unmatched))

    def _add_overlay_links(self, rows: list[dict[str, Any]], kind: EdgeKind, prefix: str) -> None:
        for r in rows:
            if r["NODE_TYPE"] == "NODE":
                lng, lat = _wkt_coords(r["NODE_WKT"])[0]
                self._add_node(prefix + _id(r["NODE_ID"]), lng, lat, r["NODE_TYPE_CD"], kind.value)
        for r in rows:
            if r["NODE_TYPE"] != "LINK":
                continue
            link_id = _id(r["LNKG_ID"])
            if prefix == "" and self.g.has_edge(*self._endpoint_ids(r, prefix)):
                continue  # 도보망에 이미 같은 간선이 있고 kind도 위에서 정했다
            coords = _wkt_coords(r["LNKG_WKT"])
            u, v = self._ensure_endpoints(r, coords, prefix)
            station = r.get("SBWY_STN_NM") or ""
            name = (
                f"{station} 지하보도" if kind is EdgeKind.underpass and station else kind_name(kind)
            )
            self._add_edge(
                u, v, PedEdge(prefix + link_id, kind, float(r["LNKG_LEN"]), (), coords, name)
            )

    def _endpoint_ids(self, row: dict[str, Any], prefix: str) -> tuple[str, str]:
        return prefix + _id(row["BGNG_LNKG_ID"]), prefix + _id(row["END_LNKG_ID"])

    def _add_underpass(self, rows: list[dict[str, Any]]) -> None:
        """지하도는 별도 망(ID·좌표가 도보망과 안 겹친다). u 접두사, 출입구를 도보망에 잇는다."""
        walk_nodes = [n for n, d in self.g.nodes(data=True) if d["source"] == "walk"]
        tree = STRtree(
            [shapely.Point(self.g.nodes[n]["x"], self.g.nodes[n]["y"]) for n in walk_nodes]
        )
        before = set(self.g.nodes)
        self._add_overlay_links(rows, EdgeKind.underpass, prefix="u")
        lifts = {
            "u" + _id(r["NODE_ID"])
            for r in rows
            if r["NODE_TYPE"] == "NODE" and (r.get("LIFT") == "1" or r.get("ELVT") == "1")
        }
        for n in set(self.g.nodes) - before:
            if self.g.degree(n) != 1:
                continue  # 출입구 = 지하도 망에서 차수 1
            p = shapely.Point(self.g.nodes[n]["x"], self.g.nodes[n]["y"])
            idx = int(tree.nearest(p))
            target = walk_nodes[idx]
            dist = p.distance(shapely.Point(self.g.nodes[target]["x"], self.g.nodes[target]["y"]))
            if dist > self.settings.connector_max_m:
                continue
            kind = EdgeKind.elevator if n in lifts else EdgeKind.stairs
            coords = (
                (self.g.nodes[n]["lng"], self.g.nodes[n]["lat"]),
                (self.g.nodes[target]["lng"], self.g.nodes[target]["lat"]),
            )
            if self._add_edge(n, target, PedEdge(f"c{n}", kind, max(dist, 1.0), (), coords)):
                self.connectors += 1

    def _attach_crosswalk_ids(self) -> tuple[int, int]:
        """OA-23081 관리번호 점을 간선에 붙인다.

        1) crosswalk_match_m 안의 가장 가까운 crosswalk 간선.
        2) 없으면 crosswalk_attach_any_m 안의 아무 간선 (도보망이 횡단보도로 표시하지 않은 작은 길의
           횡단보도 — 점이 간선 위에 얹혀 있다). 그 간선이 crosswalk_promote_max_m보다 짧은
           sidewalk이면 kind를 crosswalk으로 올린다.
        3) 둘 다 없으면 미매칭.
        """
        all_edges = [(u, v, e) for u, v, e in self._edges_of(None)]
        all_lines = [shapely.LineString(_to_m(e.coords)) for _, _, e in all_edges]
        all_tree = STRtree(all_lines)
        cw_pos = [i for i, (_, _, e) in enumerate(all_edges) if e.kind == EdgeKind.crosswalk]
        cw_tree = STRtree([all_lines[i] for i in cw_pos])
        attached: dict[int, list[str]] = {}
        promote: set[int] = set()
        unmatched = 0
        wb = openpyxl.load_workbook(self.dir / "OA-23081.xlsx", read_only=True)
        rows = wb.worksheets[0].iter_rows(values_only=True)
        col = {str(h): i for i, h in enumerate(next(rows))}
        districts = set(self.settings.districts)
        for row in rows:
            if row[col["자치구"]] not in districts or row[col["X좌표"]] is None:
                continue
            x, y = _5186_TO_5179.transform(
                float(str(row[col["X좌표"]])), float(str(row[col["Y좌표"]]))
            )
            p = shapely.Point(x, y)
            crosswalk_id = str(row[col["횡단보도관리번호"]])
            i = cw_pos[int(cw_tree.nearest(p))]
            if p.distance(all_lines[i]) <= self.settings.crosswalk_match_m:
                attached.setdefault(i, []).append(crosswalk_id)
                continue
            i = int(all_tree.nearest(p))
            if p.distance(all_lines[i]) <= self.settings.crosswalk_attach_any_m:
                attached.setdefault(i, []).append(crosswalk_id)
                edge = all_edges[i][2]
                if (
                    edge.kind == EdgeKind.sidewalk
                    and edge.length_m <= self.settings.crosswalk_promote_max_m
                ):
                    promote.add(i)
                continue
            unmatched += 1
        wb.close()
        for i, ids in attached.items():
            u, v, old = all_edges[i]
            kind = EdgeKind.crosswalk if i in promote else old.kind
            self.g[u][v]["edge"] = PedEdge(
                old.link_id, kind, old.length_m, tuple(sorted(ids)), old.coords
            )
        return sum(len(v) for v in attached.values()), unmatched

    def _edges_of(self, kind: EdgeKind | None) -> Iterator[tuple[str, str, PedEdge]]:
        for u, v, data in self.g.edges(data=True):
            edge: PedEdge = data["edge"]
            if kind is None or edge.kind == kind:
                yield u, v, edge

    def _stats(self, attached: int, unmatched: int) -> BuildStats:
        kinds: dict[str, int] = {}
        for _, _, data in self.g.edges(data=True):
            kinds[data["edge"].kind.value] = kinds.get(data["edge"].kind.value, 0) + 1
        largest = max((len(c) for c in nx.connected_components(self.g)), default=0)
        return BuildStats(
            nodes=self.g.number_of_nodes(),
            edges=self.g.number_of_edges(),
            kinds=dict(sorted(kinds.items())),
            largest_component_ratio=largest / max(self.g.number_of_nodes(), 1),
            crosswalk_ids_attached=attached,
            crosswalk_points_unmatched=unmatched,
            connectors=self.connectors,
            parallel_dropped=self.parallel_dropped,
            self_loops_dropped=self.self_loops_dropped,
        )
