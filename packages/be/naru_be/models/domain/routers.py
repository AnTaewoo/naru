"""TimeDependentRouter · BaselineRouter — PedGraph 위 A* (ARCHITECTURE BE Model, T3.1·T3.2).

BaselineRouter 는 같은 그래프에서 통제를 보지 않는다 (INTERFACE §2 baseline). 둘은 _AStarRouter 를
공유하고 간선 가중(_edge_factor)만 다르다.
비용 = 거리 + 수직 이동 패널티(stairs·elevator 연결 간선) + 통제 가중.
  confirmed(도착 시각 기준) → 간선 제외 · scheduled 이고 confidence >= review_confidence → 거리 x3
  scheduled 인데 confidence < 0.7, zone_scheduled, released → 보통 간선 (INTERFACE §5, 상태기계 표)
간선 도착 시각 = 출발 시각 + 지금까지 거리 / walk_speed. 폐쇄 판정은 ClosureEngine.status_of_state.
avoided = 통제가 없었다면 지났을(기준 경로) 횡단보도 중 도착 시각에 confirmed 이거나 scheduled 라서
피한 것.
"""

from __future__ import annotations

import heapq
import itertools
import math
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta

from naru_be.config import Settings
from naru_be.errors import NoRouteError
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.ped_graph import EdgeKind, PedEdge, PedGraph
from naru_be.models.domain.types import AvoidedCrosswalk, LngLat, Path, RouteLeg
from naru_contracts import ClosureState, Status

ByCrosswalk = dict[str, list[ClosureState]]
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)  # 통제를 안 볼 때의 시각 — 쓰이지 않는다


class _AStarRouter:
    """공통 A*. 서브클래스가 _edge_factor 로 통제 가중을 정한다."""

    def __init__(self, ped: PedGraph, settings: Settings | None = None) -> None:
        self.ped = ped
        self.settings = settings or Settings()

    def _edge_factor(self, edge: PedEdge, at: datetime, by_crosswalk: ByCrosswalk) -> float | None:
        """None = 제외. 1.0 보통."""
        return 1.0

    def _snap(self, src: LngLat, dst: LngLat) -> tuple[str, str, float, float]:
        a, da = self.ped.nearest_node(*src)
        b, db = self.ped.nearest_node(*dst)
        return a, b, da, db

    def _edge_cost(self, edge: PedEdge, factor: float) -> float:
        penalty = {
            EdgeKind.stairs: self.settings.stairs_penalty_m,
            EdgeKind.elevator: self.settings.elevator_penalty_m,
        }.get(edge.kind, 0.0)
        return edge.length_m * factor + penalty

    def _search(self, a: str, b: str, t: datetime, by_crosswalk: ByCrosswalk) -> list[str]:
        g = self.ped.graph
        bx, by = g.nodes[b]["x"], g.nodes[b]["y"]

        def h(n: str) -> float:
            return math.hypot(g.nodes[n]["x"] - bx, g.nodes[n]["y"] - by)

        speed = self.settings.walk_speed_mps
        best: dict[str, float] = {a: 0.0}
        walked: dict[str, float] = {a: 0.0}  # 실제 거리 (도착 시각 계산)
        prev: dict[str, str] = {}
        counter = itertools.count()
        heap: list[tuple[float, int, str]] = [(h(a), next(counter), a)]
        done: set[str] = set()
        while heap:
            _, _, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            if u == b:
                break
            at = t + timedelta(seconds=walked[u] / speed)
            for v, data in g[u].items():
                if v in done:
                    continue
                edge: PedEdge = data["edge"]
                factor = self._edge_factor(edge, at, by_crosswalk)
                if factor is None:
                    continue
                cost = best[u] + self._edge_cost(edge, factor)
                if cost < best.get(v, math.inf):
                    best[v] = cost
                    walked[v] = walked[u] + edge.length_m
                    prev[v] = u
                    heapq.heappush(heap, (cost + h(v), next(counter), v))
        if b not in best:
            raise NoRouteError(f"경로 없음: {a} → {b}")
        path = [b]
        while path[-1] != a:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    def _build(
        self,
        path: list[str],
        src: LngLat,
        dst: LngLat,
        snap_in: float,
        snap_out: float,
        avoided: tuple[AvoidedCrosswalk, ...],
    ) -> Path:
        g = self.ped.graph
        coords: list[LngLat] = [src]
        legs: list[RouteLeg] = []
        distance = snap_in + snap_out

        def add(kind: EdgeKind, name: str | None, length_m: float, pts: list[LngLat]) -> None:
            """선을 이어 붙이고 레그 범위를 늘린다 (ADR-009: 이웃 레그는 경계 점 공유)."""
            for p in pts:
                if coords[-1] != p:
                    coords.append(p)
            end = len(coords) - 1
            if legs and legs[-1].kind is kind:
                last = legs[-1]
                legs[-1] = RouteLeg(
                    kind, last.name or name, last.distance_m + length_m, (last.coord_range[0], end)
                )
            else:
                start = legs[-1].coord_range[1] if legs else 0
                legs.append(RouteLeg(kind, name, length_m, (start, end)))

        def node_xy(n: str) -> LngLat:
            return (g.nodes[n]["lng"], g.nodes[n]["lat"])

        # 접근 구간(출발점 → 첫 노드)은 sidewalk 레그로 — 레그 합 = 총거리 (ADR-009)
        if src != node_xy(path[0]):
            add(EdgeKind.sidewalk, None, snap_in, [node_xy(path[0])])
        for u, v in itertools.pairwise(path):
            edge: PedEdge = g[u][v]["edge"]
            pts = list(edge.coords)
            if pts[0] != node_xy(u) and pts[-1] == node_xy(u):
                pts.reverse()
            distance += edge.length_m
            add(edge.kind, edge.name, edge.length_m, pts)
        if coords[-1] != dst:  # 마지막 노드 → 도착점
            add(EdgeKind.sidewalk, None, snap_out, [dst])
        return Path(
            coords=tuple(coords),
            distance_m=round(distance, 1),
            duration_s=round(distance / self.settings.walk_speed_mps),
            legs=tuple(legs),
            avoided=avoided,
            node_ids=tuple(path),
        )


class BaselineRouter(_AStarRouter):
    """같은 PedGraph, 통제 미적용 (INTERFACE §2 baseline)."""

    def route(self, src: LngLat, dst: LngLat) -> Path:
        a, b, snap_in, snap_out = self._snap(src, dst)
        return self._build(self._search(a, b, EPOCH, {}), src, dst, snap_in, snap_out, ())


class TimeDependentRouter(_AStarRouter):
    def __init__(
        self, ped: PedGraph, engine: ClosureEngine, settings: Settings | None = None
    ) -> None:
        super().__init__(ped, settings)
        self.engine = engine

    def route(
        self, src: LngLat, dst: LngLat, t: datetime, closures: Sequence[ClosureState]
    ) -> Path:
        if t.tzinfo is None:
            raise ValueError("t 는 tz-aware 여야 한다")
        by_crosswalk = self._by_crosswalk(closures)
        a, b, snap_in, snap_out = self._snap(src, dst)
        baseline = self._search(a, b, t, {})
        path = self._search(a, b, t, by_crosswalk)
        avoided = self._avoided(baseline, path, t, by_crosswalk)
        return self._build(path, src, dst, snap_in, snap_out, avoided)

    @staticmethod
    def _by_crosswalk(closures: Iterable[ClosureState]) -> ByCrosswalk:
        out: ByCrosswalk = {}
        for c in closures:
            out.setdefault(c.crosswalk_id, []).append(c)
        return out

    def _edge_factor(self, edge: PedEdge, at: datetime, by_crosswalk: ByCrosswalk) -> float | None:
        """None = 제외(confirmed). scheduled_cost_factor = 예정(confidence >= 0.7)."""
        factor = 1.0
        for cid in edge.crosswalk_ids:
            for state in by_crosswalk.get(cid, ()):
                status = self.engine.status_of_state(state, at)
                if status is Status.confirmed:
                    return None
                if (
                    status is Status.scheduled
                    and state.confidence >= self.settings.review_confidence
                ):
                    factor = self.settings.scheduled_cost_factor
        return factor

    def _avoided(
        self,
        baseline: list[str],
        path: list[str],
        t: datetime,
        by_crosswalk: ByCrosswalk,
    ) -> tuple[AvoidedCrosswalk, ...]:
        g = self.ped.graph
        used = {cid for u, v in itertools.pairwise(path) for cid in g[u][v]["edge"].crosswalk_ids}
        out: list[AvoidedCrosswalk] = []
        seen: set[str] = set()
        walked = 0.0
        for u, v in itertools.pairwise(baseline):
            edge: PedEdge = g[u][v]["edge"]
            at = t + timedelta(seconds=walked / self.settings.walk_speed_mps)
            walked += edge.length_m
            for cid in edge.crosswalk_ids:
                if cid in seen or cid in used:
                    continue
                for state in by_crosswalk.get(cid, ()):
                    status = self.engine.status_of_state(state, at)
                    penalized = (
                        status is Status.scheduled
                        and state.confidence >= self.settings.review_confidence
                    )
                    if status is Status.confirmed or penalized:
                        seen.add(cid)
                        out.append(
                            AvoidedCrosswalk(
                                cid,
                                status,
                                state.reason,
                                state.window.end,
                                tuple(state.evidence),
                                state.approx,
                            )
                        )
                        break
        return tuple(out)
