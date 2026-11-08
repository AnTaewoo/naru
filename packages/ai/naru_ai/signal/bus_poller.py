"""BusPoller — 통제 창의 버스 위치를 받아 BE 로 (T6.2, ADR-013 D·G). 판단은 하지 않는다.

1순위 공지 통제 (쿼터를 먼저 쓴다)
- BE `/closures/events` 중 공지 출처(smpa·topis·news·seoul_press), 시작 1시간 전 ~ 끝 30분 뒤
  (끝이 없으면 시작+6시간). 그 통제의 횡단보도 점(`/closures` 의 같은 reason)에서 100 m 안
  정류소가 많은 노선 순으로 사건마다 3개, 60초마다(워커 bus 소스 주기).
2순위 TOPIS 집회·행사 돌발 (태우 2026-11-08 — 보정에는 안 쓰고 기준 데이터: 실제로 막힌 구간의
버스 움직임으로 T6.3 이 60 m 이탈·보정값을 맞춘다)
- 지금 걸린(시작 ≤ 지금 ≤ 끝) 집회·행사(A10) 돌발마다 노선 1개 — TOPIS 링크 선에서 100 m 안
  정류소가 많은 순, 공지 노선·다른 돌발 노선과 겹치면 다음. 집회(10B02) 먼저, 최근 시작 먼저.
- 120초 간격, 하루 300회, 전체 900회에서 공지가 쓰고 남은 만큼만. 돌발 하나는 하루 30회까지
  (300회를 몇 건이 다 쓰지 않게 — 약 1시간 분량).
- 노선명이 N(심야)·새벽으로 시작하면 뺀다. 정류소는 OA-1095 (`data/raw/bus_routes_*/OA-1095.xlsx`).
- 부른 노선은 하루 한 번 경로(getRoutePath)도 받는다(bus_feed.RoutePaths). 받기·기록·상한 세기는
  bus_feed, 보내기는 워커가 POST /internal/bus-positions.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

from naru_ai.ingest.topis_api import KST
from naru_ai.signal.bus_feed import BusApi, RoutePathError, RoutePaths, parse_bus_positions
from naru_contracts import (
    BusPositionBatch,
    ClosureEventsResponse,
    FeatureCollection,
    Source,
)

log = logging.getLogger(__name__)

NEAR_M = 100.0  # 통제 횡단보도·돌발 링크에서 이만큼 안의 정류소로 노선을 고른다
SKIP_ROUTES = ("N", "새벽")  # 심야·새벽 노선
LEAD = timedelta(hours=1)  # 통제 시작 1시간 전부터 ("평소" 통과 시간, ADR-013 A)
TAIL = timedelta(minutes=30)
OPEN_END = timedelta(hours=6)  # 끝 없는 통제는 시작+6시간 (INTERFACE §1)
NOTICE_SOURCES = frozenset({Source.smpa, Source.topis, Source.news, Source.seoul_press})

LngLat = tuple[float, float]


@dataclass(frozen=True)
class Stop:
    route_id: str
    route_name: str
    node_id: str
    lng: float
    lat: float


@dataclass(frozen=True)
class IncidentTarget:
    """TOPIS 집회·행사 돌발 하나 (같은 링크·시각 묶음)."""

    key: str  # 가장 작은 acc_id
    rally: bool  # 10B02 집회 — 먼저 본다
    start: datetime
    end: datetime | None
    coords: tuple[LngLat, ...]  # TOPIS 링크 선, 없으면 돌발 점 하나


def _xy(p: LngLat, origin: LngLat) -> tuple[float, float]:
    """origin 기준 평면 m (짧은 거리용, 위도 37.5° 언저리)."""
    return (
        (p[0] - origin[0]) * 111_320.0 * math.cos(math.radians(origin[1])),
        (p[1] - origin[1]) * 110_540.0,
    )


def _meters_to_line(p: LngLat, coords: Sequence[LngLat]) -> float:
    """점에서 선(점 하나면 그 점)까지 거리 m."""
    if len(coords) == 1:
        return math.hypot(*_xy(coords[0], p))
    best = math.inf
    for a, b in itertools.pairwise(coords):
        (ax, ay), (bx, by) = _xy(a, p), _xy(b, p)
        dx, dy = bx - ax, by - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


class RouteStops:
    """OA-1095 노선별 정류소 — 통제 점·돌발 선 근처를 지나는 노선 고르기."""

    def __init__(self, stops: Sequence[Stop]) -> None:
        self.stops = [s for s in stops if not s.route_name.startswith(SKIP_ROUTES)]

    @classmethod
    def load(cls, xlsx: Path) -> RouteStops:
        rows = load_workbook(xlsx, read_only=True).worksheets[0].iter_rows(values_only=True)
        head = [str(c) for c in next(rows)]
        names = ("ROUTE_ID", "노선명", "NODE_ID", "X좌표", "Y좌표")
        rid, name, node, x, y = (head.index(n) for n in names)
        stops = []
        for r in rows:
            try:
                lng, lat = float(str(r[x])), float(str(r[y]))
            except (TypeError, ValueError):
                continue  # 좌표 없는 행
            stops.append(Stop(str(r[rid]), str(r[name]), str(r[node]), lng, lat))
        return cls(stops)

    def _ranked(self, near: Callable[[LngLat], bool], box: tuple[float, ...]) -> list[str]:
        hits: dict[str, set[str]] = defaultdict(set)
        w, s, e, n = box
        for stop in self.stops:
            if w <= stop.lng <= e and s <= stop.lat <= n and near((stop.lng, stop.lat)):
                hits[stop.route_id].add(stop.node_id)
        return [r for r, _ in sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[0]))]

    @staticmethod
    def _box(points: Sequence[LngLat], radius_m: float) -> tuple[float, ...]:
        pad = radius_m / 100_000.0 * 1.5  # 도 단위 여유 (위경도 1e-5° ≈ 1 m)
        lngs, lats = [p[0] for p in points], [p[1] for p in points]
        return (min(lngs) - pad, min(lats) - pad, max(lngs) + pad, max(lats) + pad)

    def near(self, points: Sequence[LngLat], limit: int, radius_m: float = NEAR_M) -> list[str]:
        """그 점들에서 radius 안 정류소(서로 다른 NODE_ID)가 많은 노선 순, 같으면 노선 ID 순."""
        if not points:
            return []

        def close(q: LngLat) -> bool:
            return any(_meters_to_line(q, [p]) <= radius_m for p in points)

        return self._ranked(close, self._box(points, radius_m))[:limit]

    def near_line(self, coords: Sequence[LngLat], radius_m: float = NEAR_M) -> list[str]:
        """선(돌발 링크)에서 radius 안 정류소가 많은 노선 순 — 전부."""
        if not coords:
            return []
        return self._ranked(
            lambda q: _meters_to_line(q, coords) <= radius_m, self._box(coords, radius_m)
        )


class BusPoller:
    def __init__(
        self,
        stops: RouteStops,
        api: BusApi,
        events: Callable[[], ClosureEventsResponse],
        closures: Callable[[str, datetime], FeatureCollection],
        incidents: Callable[[], list[IncidentTarget]] | None = None,
        paths: RoutePaths | None = None,
        *,
        per_event: int = 3,
        daily_cap: int = 900,
        incident_cap: int = 300,
        incident_every_s: int = 120,
        incident_each: int = 30,
    ) -> None:
        self.stops = stops
        self.api = api
        self.events = events
        self.closures = closures
        self.incidents = incidents or (lambda: [])
        self.paths = paths
        self.per_event = per_event
        self.daily_cap = daily_cap
        self.incident_cap = incident_cap
        self.incident_every_s = incident_every_s
        self.incident_each = incident_each
        self._picked: dict[tuple[str, str], list[str]] = {}
        self._incident_pick: dict[str, str | None] = {}
        self._incident_calls: dict[tuple[str, str], int] = defaultdict(int)  # (날짜, 돌발)
        self._last_incident: dict[str, datetime] = {}

    def watched(self, now: datetime) -> list[str]:
        """1순위 — 창 안 공지 통제마다 근처 노선, 겹치면 한 번."""
        routes: list[str] = []
        for ev in self.events().events:
            start = ev.window.start
            if ev.source not in NOTICE_SOURCES or start is None:
                continue
            end = ev.window.end or start + OPEN_END
            if not (start - LEAD <= now <= end + TAIL):
                continue
            key = (ev.reason, start.isoformat())
            if key not in self._picked:
                bbox = ",".join(f"{v:.6f}" for v in ev.bbox)
                fc = self.closures(bbox, start)
                points = [
                    (float(f.geometry.coordinates[0]), float(f.geometry.coordinates[1]))
                    for f in fc.features
                    if f.properties.reason == ev.reason and f.geometry.type == "Point"
                ]
                self._picked[key] = self.stops.near(points, self.per_event)
                log.info("bus routes", extra={"event": ev.reason[:40], "routes": self._picked[key]})
            routes.extend(r for r in self._picked[key] if r not in routes)
        return routes

    def incident_routes(self, now: datetime, taken: Sequence[str]) -> list[tuple[str, str]]:
        """2순위 — 지금 걸린 집회·행사 돌발마다 노선 1개: (노선, 돌발 key)."""
        live = [t for t in self.incidents() if t.start <= now <= (t.end or t.start + OPEN_END)]
        live.sort(key=lambda t: (not t.rally, -t.start.timestamp(), t.key))
        used = set(taken) | {r for r in self._incident_pick.values() if r}
        out: list[tuple[str, str]] = []
        for t in live:
            if t.key not in self._incident_pick:
                route = next((r for r in self.stops.near_line(t.coords) if r not in used), None)
                self._incident_pick[t.key] = route
                log.info("bus incident route", extra={"incident": t.key, "route": route})
                if route:
                    used.add(route)
            route = self._incident_pick[t.key]
            if route and route not in taken:
                out.append((route, t.key))
        return out

    def batches(self, now: datetime) -> list[BusPositionBatch]:
        day = now.astimezone(KST).strftime("%Y%m%d")
        out: list[BusPositionBatch] = []
        notice = self.watched(now)
        for route in notice:
            if self.api.live and self.api.calls_today(now) >= self.daily_cap:
                log.warning("bus daily cap", extra={"cap": self.daily_cap})
                break
            out.extend(self._poll(route, "notice", now))
        for route, key in self.incident_routes(now, notice):
            last = self._last_incident.get(route)
            if last is not None and (now - last).total_seconds() < self.incident_every_s:
                continue
            if self._incident_calls[(day, key)] >= self.incident_each:
                continue
            if self.api.live and (
                self.api.calls_today(now, "incident") >= self.incident_cap
                or self.api.calls_today(now) >= self.daily_cap
            ):
                log.warning("bus incident cap", extra={"cap": self.incident_cap})
                break
            got = self._poll(route, "incident", now)
            self._last_incident[route] = now
            if got:
                self._incident_calls[(day, key)] += 1
                out.extend(got)
        for b in out:
            self._ensure_path(b.route_id, now)
        return out

    def _poll(self, route: str, kind: str, now: datetime) -> list[BusPositionBatch]:
        try:
            rec = self.api.call(route, kind)
        except FileNotFoundError:  # 기록 재생인데 그 노선 기록이 없다 — 지어내지 않고 건너뛴다
            log.info("bus record missing", extra={"route": route, "kind": kind})
            return []
        digest = hashlib.sha1(rec.raw.encode("utf-8")).hexdigest()[:12]
        return [
            BusPositionBatch(
                batch_id=f"bus-{route}-{digest}",
                produced_at=now,
                route_id=route,
                ref=rec.path.as_posix(),
                called_at=rec.received_at,
                positions=parse_bus_positions(rec.raw),
            )
        ]

    def _ensure_path(self, route: str, now: datetime) -> None:
        if self.paths is None:
            return
        try:
            self.paths.ensure(route, now)
        except RoutePathError as exc:  # 경로가 없어도 위치 수집은 계속 (그날 다시 안 부름)
            log.warning("route path", extra={"route": route, "error": str(exc)})
