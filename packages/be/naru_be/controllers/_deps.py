"""naru_models() — create_app 이 app.extensions["naru"] 에 둔 Model 싱글턴을 타입 있게 꺼낸다."""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from naru_be.config import Settings
from naru_be.models.domain.candidate_intake import CandidateIntake
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.geocoder import Geocoder
from naru_be.models.domain.ped_graph import PedGraph
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


def naru_models() -> NaruModels:
    models = current_app.extensions["naru"]
    assert isinstance(models, NaruModels)
    return models
