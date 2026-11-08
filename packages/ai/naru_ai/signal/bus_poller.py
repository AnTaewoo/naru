"""BusPoller — 공지 통제 창의 버스 위치를 받아 BE 로 (T6.2, ADR-013 D·G). 판단은 하지 않는다.

- 어느 통제: BE `/closures/events` 중 공지 출처(smpa·topis·news·seoul_press)만 — 코스·돌발은
  이미 실제 근거(시각표·TOPIS)가 있어 쿼터를 쓰지 않는다. 시작 1시간 전 ~ 끝 30분 뒤
  (끝이 없으면 시작+6시간).
- 어느 노선: 그 통제의 횡단보도 점(`/closures` 의 같은 reason)에서 100 m 안 정류소가 많은 순,
  사건마다 최대 3개. 노선명이 N(심야)·새벽으로 시작하면 뺀다 — 낮 통제엔 차가 없다.
  정류소는 OA-1095 (`data/raw/bus_routes_*/OA-1095.xlsx`, WGS84).
- 받기·파싱·하루 상한은 bus_feed (BusApi). 보내기는 워커가 POST /internal/bus-positions.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

from naru_ai.signal.bus_feed import BusApi, parse_bus_positions
from naru_contracts import (
    BusPositionBatch,
    ClosureEventsResponse,
    FeatureCollection,
    Source,
)

log = logging.getLogger(__name__)

NEAR_M = 100.0  # 통제 횡단보도에서 이만큼 안의 정류소로 노선을 고른다
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


def _meters(a: LngLat, b: LngLat) -> float:
    """짧은 거리(100 m 안팎)용 평면 근사 — 위도 37.5° 기준."""
    dx = (a[0] - b[0]) * 111_320.0 * math.cos(math.radians((a[1] + b[1]) / 2))
    dy = (a[1] - b[1]) * 110_540.0
    return math.hypot(dx, dy)


class RouteStops:
    """OA-1095 노선별 정류소 — 통제 점 근처를 지나는 노선 고르기."""

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

    def near(self, points: Sequence[LngLat], limit: int, radius_m: float = NEAR_M) -> list[str]:
        """그 점들에서 radius 안 정류소(서로 다른 NODE_ID)가 많은 노선 순, 같으면 노선 ID 순."""
        if not points:
            return []
        pad = radius_m / 100_000.0 * 1.5  # 도 단위 여유 (위경도 1e-5° ≈ 1 m)
        w = min(p[0] for p in points) - pad
        e = max(p[0] for p in points) + pad
        s = min(p[1] for p in points) - pad
        n = max(p[1] for p in points) + pad
        hits: dict[str, set[str]] = defaultdict(set)
        for stop in self.stops:
            if not (w <= stop.lng <= e and s <= stop.lat <= n):
                continue
            if any(_meters((stop.lng, stop.lat), p) <= radius_m for p in points):
                hits[stop.route_id].add(stop.node_id)
        ranked = sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        return [route for route, _ in ranked[:limit]]


class BusPoller:
    def __init__(
        self,
        stops: RouteStops,
        api: BusApi,
        events: Callable[[], ClosureEventsResponse],
        closures: Callable[[str, datetime], FeatureCollection],
        per_event: int = 3,
        daily_cap: int = 900,
    ) -> None:
        self.stops = stops
        self.api = api
        self.events = events
        self.closures = closures
        self.per_event = per_event
        self.daily_cap = daily_cap
        self._picked: dict[tuple[str, str], list[str]] = {}

    def watched(self, now: datetime) -> list[str]:
        """지금 볼 노선 — 창 안 공지 통제마다 근처 노선, 겹치면 한 번."""
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

    def batches(self, now: datetime) -> list[BusPositionBatch]:
        out: list[BusPositionBatch] = []
        for route in self.watched(now):
            if self.api.live and self.api.calls_today(now) >= self.daily_cap:
                log.warning("bus daily cap", extra={"cap": self.daily_cap})
                break
            rec = self.api.call(route)
            digest = hashlib.sha1(rec.raw.encode("utf-8")).hexdigest()[:12]
            out.append(
                BusPositionBatch(
                    batch_id=f"bus-{route}-{digest}",
                    produced_at=now,
                    route_id=route,
                    ref=rec.path.as_posix(),
                    called_at=rec.received_at,
                    positions=parse_bus_positions(rec.raw),
                )
            )
        return out
