"""TimeDependentRouter · BaselineRouter — PedGraph 위 A* (ARCHITECTURE BE Model, T3.1·T3.2).

BaselineRouter 는 같은 그래프에서 통제를 보지 않는다 (INTERFACE §2 baseline). 둘은 _AStarRouter 를
공유하고 간선 가중(_edge_factor)만 다르다.
비용(m) = 거리 + 수직 이동 패널티(stairs·elevator 연결 간선) + 통제 비용.
  confirmed(도착 시각 기준) → 간선 제외
  scheduled 이고 confidence >= review_confidence 이고 도착 시각이 공지 창 안 → 횡단보도마다
    scheduled_penalty_s(300초) x walk_speed (ADR-011 A). 창 밖(시작 전·끝난 뒤)은 보통
  scheduled 인데 confidence < 0.7, zone_scheduled, released → 보통 간선 (INTERFACE §5, 상태기계 표)
출발·도착을 붙일 노드가 max_snap_m(150 m) 보다 멀면 OutOfCoverageError (ADR-011 그래프 밖).
간선 도착 시각 = 출발 시각 + 지금까지 거리 / walk_speed. 폐쇄 판정은 ClosureEngine.status_of_state.
avoided = 통제가 없었다면 지났을(기준 경로) 횡단보도 중 도착 시각에 confirmed 이거나 scheduled 라서
피한 것.
avoid(T7.6, INTERFACE §2 v0.14) = 길찾기에서 고른 사건의 상태 — 그 횡단보도는 시각·확신도와 상관없이
간선 제외(§5 규칙보다 앞). 기준 경로가 지나면 avoided 에 그 시각 실제 상태로 넣는다.
"""

from __future__ import annotations

import heapq
import itertools
import math
from collections.abc import Collection, Iterable, Sequence
from datetime import UTC, datetime, timedelta

from naru_be.config import Settings
from naru_be.errors import NoRouteError, OutOfCoverageError
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.ped_graph import EdgeKind, PedEdge, PedGraph
from naru_be.models.domain.types import AvoidedCrosswalk, LngLat, Path, RouteLeg
from naru_contracts import ClosureState, Status

ByCrosswalk = dict[str, list[ClosureState]]
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)  # 통제를 안 볼 때의 시각 — 쓰이지 않는다


class _AStarRouter:
    """공통 A*. 서브클래스가 _closure_cost 로 통제 비용을 정한다."""

    def __init__(self, ped: PedGraph, settings: Settings | None = None) -> None:
        self.ped = ped
        self.settings = settings or Settings()

    def _closure_cost(self, edge: PedEdge, at: datetime, by_crosswalk: ByCrosswalk) -> float | None:
        """통제 때문에 더하는 비용(m). None = 제외. 0 = 보통."""
        return 0.0

    def _snap(self, src: LngLat, dst: LngLat) -> tuple[str, str, float, float]:
        a, da = self.ped.nearest_node(*src)
        b, db = self.ped.nearest_node(*dst)
        limit = self.settings.max_snap_m
        for dist, field in ((da, "from"), (db, "to")):
            if dist > limit:
                raise OutOfCoverageError(
                    f"{field}: 보행망에서 {dist:.0f} m 떨어져 있다 ({limit:.0f} m 안이어야 한다)",
                    field,
                )
        return a, b, da, db

    def _edge_cost(self, edge: PedEdge) -> float:
        penalty = {
            EdgeKind.stairs: self.settings.stairs_penalty_m,
            EdgeKind.elevator: self.settings.elevator_penalty_m,
        }.get(edge.kind, 0.0)
        return edge.length_m + penalty

    def _search(
        self,
        a: str,
        b: str,
        t: datetime,
        by_crosswalk: ByCrosswalk,
        blocked: Collection[str] = frozenset(),
    ) -> list[str]:
        """blocked = 시각과 상관없이 막는 횡단보도(avoid, T7.6)"""
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
                if blocked and any(cid in blocked for cid in edge.crosswalk_ids):
                    continue
                extra = self._closure_cost(edge, at, by_crosswalk)
                if extra is None:
                    continue
                cost = best[u] + self._edge_cost(edge) + extra
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
        fallbacks: list[str | None] = []  # 레그마다 대안 이름(횡단보도 도로명, T5.10)
        distance = snap_in + snap_out

        def add(
            kind: EdgeKind,
            name: str | None,
            length_m: float,
            pts: list[LngLat],
            fallback: str | None = None,
        ) -> None:
            """선을 이어 붙이고 레그 범위를 늘린다 (ADR-009: 이웃 레그는 경계 점 공유).

            같은 종류가 이어지면 한 레그 — 이름은 처음 나온 것, 대안 이름은 이름이 하나도 없을 때만.
            """
            for p in pts:
                if coords[-1] != p:
                    coords.append(p)
            end = len(coords) - 1
            if legs and legs[-1].kind is kind:
                last = legs[-1]
                legs[-1] = RouteLeg(
                    kind, last.name or name, last.distance_m + length_m, (last.coord_range[0], end)
                )
                fallbacks[-1] = fallbacks[-1] or fallback
            else:
                start = legs[-1].coord_range[1] if legs else 0
                legs.append(RouteLeg(kind, name, length_m, (start, end)))
                fallbacks.append(fallback)

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
            add(edge.kind, edge.name, edge.length_m, pts, edge.road_name)
        if coords[-1] != dst:  # 마지막 노드 → 도착점
            add(EdgeKind.sidewalk, None, snap_out, [dst])
        named = [
            leg if leg.name or not fb else RouteLeg(leg.kind, fb, leg.distance_m, leg.coord_range)
            for leg, fb in zip(legs, fallbacks, strict=True)
        ]
        return Path(
            coords=tuple(coords),
            distance_m=round(distance, 1),
            duration_s=round(distance / self.settings.walk_speed_mps),
            legs=tuple(named),
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
        self,
        src: LngLat,
        dst: LngLat,
        t: datetime,
        closures: Sequence[ClosureState],
        avoid: Sequence[ClosureState] = (),
    ) -> Path:
        """avoid = 길찾기에서 피할 사건의 상태(T7.6) — 시각·확신도와 상관없이 막는다"""
        if t.tzinfo is None:
            raise ValueError("t 는 tz-aware 여야 한다")
        by_crosswalk = self._by_crosswalk(closures)
        forced = self._by_crosswalk(avoid)
        a, b, snap_in, snap_out = self._snap(src, dst)
        baseline = self._search(a, b, t, {})
        path = self._search(a, b, t, by_crosswalk, forced.keys())
        avoided = self._avoided(baseline, path, t, by_crosswalk, forced)
        return self._build(path, src, dst, snap_in, snap_out, avoided)

    @staticmethod
    def _by_crosswalk(closures: Iterable[ClosureState]) -> ByCrosswalk:
        out: ByCrosswalk = {}
        for c in closures:
            out.setdefault(c.crosswalk_id, []).append(c)
        return out

    def _penalized(self, state: ClosureState, status: Status, at: datetime) -> bool:
        """예정이고 확신도 ≥ 0.7 이고 at 이 공지 창 안 (ADR-011 A). 끝이 없으면 시작 뒤 전부."""
        if status is not Status.scheduled or state.confidence < self.settings.review_confidence:
            return False
        start, end = state.window.start, state.window.end
        return (start is None or at >= start) and (end is None or at <= end)

    def _closure_cost(self, edge: PedEdge, at: datetime, by_crosswalk: ByCrosswalk) -> float | None:
        """None = 제외(confirmed). 창 안 예정 횡단보도마다 scheduled_penalty_s x walk_speed (m)."""
        penalty_m = self.settings.scheduled_penalty_s * self.settings.walk_speed_mps
        extra = 0.0
        for cid in edge.crosswalk_ids:
            penalized = False
            for state in by_crosswalk.get(cid, ()):
                status = self.engine.status_of_state(state, at)
                if status is Status.confirmed:
                    return None
                penalized = penalized or self._penalized(state, status, at)
            if penalized:
                extra += penalty_m
        return extra

    def _avoided(
        self,
        baseline: list[str],
        path: list[str],
        t: datetime,
        by_crosswalk: ByCrosswalk,
        forced: ByCrosswalk,
    ) -> tuple[AvoidedCrosswalk, ...]:
        """상태로 피한 것 먼저(confirmed·창 안 예정), 그 밖에 avoid 로 막은 것은 그 시각 상태로"""
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
                    if status is Status.confirmed or self._penalized(state, status, at):
                        seen.add(cid)
                        out.append(self._entry(cid, state, status))
                        break
                if cid not in seen and cid in forced:
                    state = forced[cid][0]
                    seen.add(cid)
                    out.append(self._entry(cid, state, self.engine.status_of_state(state, at)))
        return tuple(out)

    @staticmethod
    def _entry(cid: str, state: ClosureState, status: Status) -> AvoidedCrosswalk:
        return AvoidedCrosswalk(
            cid,
            status,
            state.reason,
            state.window.end,
            tuple(state.evidence),
            state.approx,
        )
