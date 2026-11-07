"""RoutePlanner — 활성 폐쇄 조회 → 두 라우터 → RouteResult (ARCHITECTURE BE Model, T3.2).

입력은 contracts RouteQuery(from/to 는 "lat,lng", 파싱은 parsing.parse_latlng). 폐쇄는 출발~도착
bbox 에 여유(route_bbox_pad_m)를 두고, 출발 시각부터 route_horizon_min 안에 시작하는 것까지
(Repository.active_between) — 걷는 동안 시작하는 통제도 라우터가 도착 시각으로 판정해야 하므로.
Flask 를 모른다. 잘못된 좌표는 InvalidQueryError(INTERFACE §6 invalid_query).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from naru_be.config import Settings
from naru_be.errors import InvalidQueryError
from naru_be.models.domain.parsing import parse_latlng
from naru_be.models.domain.routers import BaselineRouter, TimeDependentRouter
from naru_be.models.domain.types import LngLat, RouteResult
from naru_be.models.repositories.closure_repository import Bbox, ClosureRepository
from naru_contracts import RouteQuery

M_PER_DEG_LAT = 111_320.0  # WGS84 위도 1도 (근사). 경도는 cos(lat) 배


class RoutePlanner:
    def __init__(
        self,
        repo: ClosureRepository,
        router: TimeDependentRouter,
        baseline_router: BaselineRouter,
        settings: Settings | None = None,
    ) -> None:
        self.repo = repo
        self.router = router
        self.baseline_router = baseline_router
        self.settings = settings or Settings()

    def plan(self, query: RouteQuery) -> RouteResult:
        if query.mode != "walk":
            raise InvalidQueryError(f"mode: walk 만 지원한다 ({query.mode})", "mode")
        src, dst = parse_latlng(query.from_, "from"), parse_latlng(query.to, "to")
        horizon = query.depart_at + timedelta(minutes=self.settings.route_horizon_min)
        closures = self.repo.active_between(query.depart_at, horizon, self._bbox(src, dst))
        return RouteResult(
            path=self.router.route(src, dst, query.depart_at, closures),
            baseline=self.baseline_router.route(src, dst),
            depart_at=query.depart_at,
            computed_at=datetime.now(UTC),
        )

    def bbox_of(self, query: RouteQuery) -> Bbox:
        return self._bbox(parse_latlng(query.from_, "from"), parse_latlng(query.to, "to"))

    def _bbox(self, src: LngLat, dst: LngLat) -> Bbox:
        pad = self.settings.route_bbox_pad_m
        mid_lat = (src[1] + dst[1]) / 2
        dlat = pad / M_PER_DEG_LAT
        dlng = pad / (M_PER_DEG_LAT * math.cos(math.radians(mid_lat)))
        return (
            min(src[0], dst[0]) - dlng,
            min(src[1], dst[1]) - dlat,
            max(src[0], dst[0]) + dlng,
            max(src[1], dst[1]) + dlat,
        )
