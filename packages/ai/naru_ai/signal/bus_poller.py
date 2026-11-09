"""BusPoller — 전면 통제·마라톤 창의 버스 위치를 기록만 한다 (T6.2, ADR-013 보류 — 태우 2026-11-09).

확신도 보정은 뺐다: 11/9 1개 차로 행진(국회대로·강남대로·하나증권)에서 버스가 152회 정상 통과,
무정차 0 — 버스는 차로 상태를 보는 신호라 부분 차로 행진의 횡단보도 막힘을 모른다
(docs/eval/bus_20261109.md). 남긴 것은 기록 — 2027 서울마라톤에서 정류소 건너뜀으로 구간별 실제
통제·해제 시각을 보려고.
- 대상: BE `/closures/events` 중 시작 1시간 전 ~ 끝 30분 뒤(끝이 없으면 시작+6시간)인 마라톤
  (type marathon)과 전면 통제(공지 파싱 lanes.scope full·one_side_full — 워커가 넘기는
  (공지 발췌, 시작) 묶음). 시작 가까운 순. 그 통제의 횡단보도 점(`/closures` 의 같은 reason)에서
  100 m 안 정류소가 많은 노선 순으로 사건마다 3개, 60초마다(워커 bus 소스 주기), 하루 900회.
- 원문은 bus_feed 가 data/recorded/bus/<notice|marathon>/ 에 남긴다. NARU_BUS_RECORD_ONLY=1(기본)
  이면 워커가 BE 로 아무것도 안 보낸다 — 후보·상태 어디에도 안 들어간다.
- 노선명이 N(심야)·새벽으로 시작하면 뺀다. 정류소는 OA-1095 (`data/raw/bus_routes_*/OA-1095.xlsx`).
  부른 노선은 하루 한 번 경로(getRoutePath)도 받는다(bus_feed.RoutePaths).
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import math
from collections import defaultdict
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

from naru_ai.signal.bus_feed import BusApi, RoutePathError, RoutePaths, parse_bus_positions
from naru_contracts import (
    BusPositionBatch,
    ClosureEventsResponse,
    ClosureType,
    FeatureCollection,
)

log = logging.getLogger(__name__)

NEAR_M = 100.0  # 통제 횡단보도에서 이만큼 안의 정류소로 노선을 고른다
SKIP_ROUTES = ("N", "새벽")  # 심야·새벽 노선
LEAD = timedelta(hours=1)  # 통제 시작 1시간 전부터 (평소 움직임과 견줄 수 있게)
TAIL = timedelta(minutes=30)
OPEN_END = timedelta(hours=6)  # 끝 없는 통제는 시작+6시간 (INTERFACE §1)
# 사건 bbox 로 /closures 를 물을 때 둘레 — 횡단보도 하나뿐인 사건은 bbox 가 점이라 소수 6자리로
# 자르면 그 점이 빠졌다(11/7 r06, T6.9). 약 20 m
BBOX_PAD_DEG = 0.0002
TARGETS_LOG_EVERY = timedelta(minutes=10)  # 대상 수가 그대로여도 이만큼마다 한 줄 (태우 11/9)
LngLat = tuple[float, float]


@dataclass(frozen=True)
class Stop:
    route_id: str
    route_name: str
    node_id: str
    lng: float
    lat: float


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


@dataclass(frozen=True)
class Target:
    """창 안 기록 대상 하나 — 마라톤 또는 전면 통제."""

    key: tuple[str, str]  # (reason, 시작 ISO)
    routes: tuple[str, ...]
    marathon: bool
    start: datetime
    end: datetime


class BusPoller:
    def __init__(
        self,
        stops: RouteStops,
        api: BusApi,
        events: Callable[[], ClosureEventsResponse],
        closures: Callable[[str, datetime], FeatureCollection],
        full: Callable[[], Collection[tuple[str, datetime]]] | None = None,
        paths: RoutePaths | None = None,
        *,
        per_event: int = 3,
        daily_cap: int = 900,
    ) -> None:
        self.stops = stops
        self.api = api
        self.events = events
        self.closures = closures
        self.full = full or (lambda: ())
        self.paths = paths
        self.per_event = per_event
        self.daily_cap = daily_cap
        self._picked: dict[tuple[str, str], list[str]] = {}
        self._counts: dict[str, int] = {}  # 대상 수 로그 (바뀔 때 + 10분에 한 번)
        self._logged: dict[str, int] | None = None
        self._counts_at: datetime | None = None

    def targets(self, now: datetime) -> list[Target]:
        """창 안 마라톤·전면 통제 — 시작 가까운 순. 부분 차로 공지·돌발은 대상이 아니다."""
        full = set(self.full())
        out: list[Target] = []
        self._counts = {"marathon_events": 0, "full_events": 0}
        for ev in self.events().events:
            start = ev.window.start
            if start is None:
                continue
            end = ev.window.end or start + OPEN_END
            if not (start - LEAD <= now <= end + TAIL):
                continue
            marathon = ev.type is ClosureType.marathon
            if not marathon and (ev.reason, start) not in full:
                continue
            self._counts["marathon_events" if marathon else "full_events"] += 1
            key = (ev.reason, start.isoformat())
            if key not in self._picked:
                w, s, e, n = ev.bbox
                pad = BBOX_PAD_DEG
                bbox = f"{w - pad:.6f},{s - pad:.6f},{e + pad:.6f},{n + pad:.6f}"
                fc = self.closures(bbox, start)
                points = [
                    (float(f.geometry.coordinates[0]), float(f.geometry.coordinates[1]))
                    for f in fc.features
                    if f.properties.reason == ev.reason and f.geometry.type == "Point"
                ]
                self._picked[key] = self.stops.near(points, self.per_event)
                log.info("bus routes", extra={"event": ev.reason[:40], "routes": self._picked[key]})
            out.append(Target(key, tuple(self._picked[key]), marathon, start, end))
        return sorted(out, key=lambda t: (abs((t.start - now).total_seconds()), t.key))

    def watched(self, now: datetime) -> list[tuple[str, str]]:
        """(노선, 기록 폴더) — 겹치면 한 번. 마라톤은 bus/marathon, 전면 통제는 bus/notice."""
        out: list[tuple[str, str]] = []
        for t in self.targets(now):
            kind = "marathon" if t.marathon else "notice"
            out.extend((r, kind) for r in t.routes if r not in {x for x, _ in out})
        return out

    def batches(self, now: datetime) -> list[BusPositionBatch]:
        """대상 노선을 한 번씩 부른다(기록). 하루 상한을 넘으면 멈춘다."""
        watched = self.watched(now)
        self._log_targets(now, len(watched))
        out: list[BusPositionBatch] = []
        for route, kind in watched:
            if self.api.live and self.api.calls_today(now) >= self.daily_cap:
                log.warning("bus daily cap", extra={"cap": self.daily_cap})
                break
            out.extend(self._poll(route, kind, now))
        for b in out:
            self._ensure_path(b.route_id, now)
        return out

    def _log_targets(self, now: datetime, routes: int) -> None:
        """대상 수 한 줄 — 바뀔 때와 10분에 한 번. 쉬는 것과 고장을 로그로 가린다."""
        counts = {**self._counts, "routes": routes}
        due = self._counts_at is None or now - self._counts_at >= TARGETS_LOG_EVERY
        if counts == self._logged and not due:
            return
        calls = self.api.calls_today(now) if self.api.live else None
        log.info("bus targets", extra={**counts, "calls_today": calls})
        self._logged, self._counts_at = counts, now

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
