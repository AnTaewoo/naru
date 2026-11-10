"""naru_models() — create_app 이 app.extensions["naru"] 에 둔 Model 싱글턴을 타입 있게 꺼낸다."""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from naru_be.config import Settings
from naru_be.models.domain.bus_intake import BusIntake
from naru_be.models.domain.candidate_intake import CandidateIntake
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.feed import FeedDesk
from naru_be.models.domain.geocoder import Geocoder
from naru_be.models.domain.ped_graph import PedGraph
from naru_be.models.domain.reports import ReportDesk
from naru_be.models.domain.road_graph import RoadGraph
from naru_be.models.domain.route_planner import RoutePlanner
from naru_be.models.repositories.closure_repository import ClosureRepository


@dataclass(frozen=True)
class NaruModels:
    settings: Settings
    ped: PedGraph
    road_graph: RoadGraph
    index: CrosswalkIndex
    engine: ClosureEngine
    repo: ClosureRepository
    route_planner: RoutePlanner
    intake: CandidateIntake
    geocoder: Geocoder
    bus_intake: BusIntake
    report_desk: ReportDesk  # 통제 제보 (T7.15)
    feed: FeedDesk  # 공개 GeoJSON 피드 (T7.17)


def naru_models() -> NaruModels:
    models = current_app.extensions["naru"]
    assert isinstance(models, NaruModels)
    return models
