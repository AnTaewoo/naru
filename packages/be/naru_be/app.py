"""create_app(settings) — 설정·로그·DB·Model 싱글턴·Blueprint·에러 핸들러 (CONVENTIONS §4.3, T3.4).

무거운 Model(PedGraph·CrosswalkIndex·RoadGraph)은 한 번 만들어 app.extensions["naru"] 에 둔다.
실데이터 위치: data/raw/seoul_spatial_<date>/ (가장 최근), data/raw/nodelink_seoul_<date>/link.gpkg.
`uv run flask --app naru_be.app run --port 5000` (make dev).
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, Response
from flask.json.provider import DefaultJSONProvider
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from naru_be.config import Settings
from naru_be.controllers import closure_controller, route_controller
from naru_be.controllers._deps import NaruModels
from naru_be.db import make_engine, make_sessions
from naru_be.errors import NaruError
from naru_be.log import configure_logging
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import PedGraph
from naru_be.models.domain.road_graph import RoadGraph
from naru_be.models.domain.route_planner import RoutePlanner
from naru_be.models.domain.routers import BaselineRouter, TimeDependentRouter
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_be.views import error_view

log = logging.getLogger(__name__)


def latest_dir(parent: Path, pattern: str) -> Path:
    dirs = sorted(p for p in parent.glob(pattern) if p.is_dir())
    if not dirs:
        raise FileNotFoundError(f"실데이터 없음: {parent}/{pattern} — make fetch 먼저")
    return dirs[-1]


def build_models(settings: Settings) -> NaruModels:
    raw = settings.data_dir / "raw"
    spatial = latest_dir(raw, "seoul_spatial_*")
    road_graph = RoadGraph.from_gpkg(latest_dir(raw, "nodelink_seoul_*") / "link.gpkg")
    ped = PedGraph.from_seoul_spatial(spatial, settings)
    index = CrosswalkIndex.from_xlsx(spatial / "OA-23081.xlsx", settings, road_graph)
    engine = ClosureEngine(index, settings)
    repo = ClosureRepository(make_sessions(make_engine(settings.database_url)), settings)
    planner = RoutePlanner(
        repo, TimeDependentRouter(ped, engine, settings), BaselineRouter(ped, settings), settings
    )
    log.info(
        "models loaded",
        extra={
            "spatial": str(spatial),
            "ped_nodes": ped.graph.number_of_nodes(),
            "crosswalks": len(index),
        },
    )
    return NaruModels(settings, ped, index, engine, repo, planner)


def create_app(settings: Settings | None = None, models: NaruModels | None = None) -> Flask:
    settings = settings or Settings()
    configure_logging()
    app = Flask("naru_be")
    assert isinstance(app.json, DefaultJSONProvider)
    app.json.ensure_ascii = False  # 한글 그대로 (INTERFACE 예시처럼)
    app.extensions["naru"] = models or build_models(settings)
    app.register_blueprint(route_controller.bp)
    app.register_blueprint(closure_controller.bp)
    _register_errors(app)
    return app


def _register_errors(app: Flask) -> None:
    @app.errorhandler(NaruError)
    def on_domain(exc: NaruError) -> tuple[Response, int]:
        return error_view.render(exc)

    @app.errorhandler(ValidationError)
    def on_validation(exc: ValidationError) -> tuple[Response, int]:
        return error_view.render(exc)

    @app.errorhandler(HTTPException)
    def on_http(exc: HTTPException) -> tuple[Response, int]:
        status = exc.code or 500
        code = {401: "unauthorized", 404: "not_found", 405: "not_found"}.get(status, "internal")
        return error_view.render_code(code, exc.description or exc.name, status)

    @app.errorhandler(Exception)
    def on_unexpected(exc: Exception) -> tuple[Response, int]:
        log.exception("unhandled request error")
        return error_view.render_code("internal", "내부 오류", 500)
