"""GET /route — 검증 → RoutePlanner → route_view (INTERFACE §2). 3줄."""

from __future__ import annotations

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.views import route_view
from naru_contracts import RouteQuery

bp = Blueprint("route", __name__)


@bp.get("/route")
def get_route() -> Response:
    query = RouteQuery.model_validate(request.args.to_dict())  # 실패 → error_view 400
    result = naru_models().route_planner.plan(query)
    return route_view.render(result)
