"""TimeDependentRouter — 폐쇄 상태를 도착 시각으로 판정하는 A* (ARCHITECTURE BE Model, T3.1).

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
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.ped_graph import EdgeKind, PedEdge, PedGraph
from naru_be.models.domain.types import AvoidedCrosswalk, LngLat, Path, RouteLeg
from naru_contracts import ClosureState, Status


class NoRouteError(Exception):
    pass


class TimeDependentRouter:
    def __init__(
        self, ped: PedGraph, engine: ClosureEngine, settings: Settings | None = None
    ) -> None:
        self.ped = ped
        self.engine = engine
        self.settings = settings or Settings()

    # --- 공개 -----------------------------------------------------------------------
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

    def route_free(self, src: LngLat, dst: LngLat) -> Path:
        """통제를 전혀 안 본 경로 (BaselineRouter 가 쓴다)."""
        a, b, snap_in, snap_out = self._snap(src, dst)
        epoch = datetime(2000, 1, 1, tzinfo=UTC)  # 통제 없음 — 시각은 쓰이지 않는다
        return self._build(self._search(a, b, epoch, {}), src, dst, snap_in, snap_out, ())

    # --- 내부 -----------------------------------------------------------------------
    def _snap(self, src: LngLat, dst: LngLat) -> tuple[str, str, float, float]:
        a, da = self.ped.nearest_node(*src)
        b, db = self.ped.nearest_node(*dst)
        return a, b, da, db

    @staticmethod
    def _by_crosswalk(closures: Iterable[ClosureState]) -> dict[str, list[ClosureState]]:
        out: dict[str, list[ClosureState]] = {}
        for c in closures:
            out.setdefault(c.crosswalk_id, []).append(c)
        return out

    def _edge_factor(
        self, edge: PedEdge, at: datetime, by_crosswalk: dict[str, list[ClosureState]]
    ) -> float | None:
        """None = 제외. 1.0 보통, scheduled_cost_factor 예정."""
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

    def _edge_cost(self, edge: PedEdge, factor: float) -> float:
        penalty = {
            EdgeKind.stairs: self.settings.stairs_penalty_m,
            EdgeKind.elevator: self.settings.elevator_penalty_m,
        }.get(edge.kind, 0.0)
        return edge.length_m * factor + penalty

    def _search(
        self, a: str, b: str, t: datetime, by_crosswalk: dict[str, list[ClosureState]]
    ) -> list[str]:
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

    def _avoided(
        self,
        baseline: list[str],
        path: list[str],
        t: datetime,
        by_crosswalk: dict[str, list[ClosureState]],
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
        for u, v in itertools.pairwise(path):
            edge: PedEdge = g[u][v]["edge"]
            pts = list(edge.coords)
            if pts[0] != (g.nodes[u]["lng"], g.nodes[u]["lat"]) and pts[-1] == (
                g.nodes[u]["lng"],
                g.nodes[u]["lat"],
            ):
                pts.reverse()
            for p in pts:
                if coords[-1] != p:
                    coords.append(p)
            distance += edge.length_m
            if legs and legs[-1].kind is edge.kind:
                last = legs[-1]
                legs[-1] = RouteLeg(
                    last.kind, last.name or edge.name, last.distance_m + edge.length_m
                )
            else:
                legs.append(RouteLeg(edge.kind, edge.name, edge.length_m))
        if coords[-1] != dst:
            coords.append(dst)
        return Path(
            coords=tuple(coords),
            distance_m=round(distance, 1),
            duration_s=round(distance / self.settings.walk_speed_mps),
            legs=tuple(legs),
            avoided=avoided,
            node_ids=tuple(path),
        )
