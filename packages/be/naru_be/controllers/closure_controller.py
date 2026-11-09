"""GET /closures — 검증 → Repository.active_horizon(at~+60분) → Engine.restate(at) → View.

GET /closures/events — 검증 → closure_events.listed(시각·창·상태·상한) → View(ETag)
(INTERFACE §3.1 v0.14, ADR-010·ADR-014 A).
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.models.domain.closure_events import listed
from naru_be.models.domain.parsing import parse_bbox
from naru_be.models.domain.types import KST
from naru_be.views import closure_view
from naru_contracts import ClosureEventsQuery, ClosuresQuery

bp = Blueprint("closures", __name__)


@bp.get("/closures")
def get_closures() -> Response:
    query = ClosuresQuery.model_validate(request.args.to_dict())  # 실패 → error_view 400
    m = naru_models()
    states = m.engine.restate(m.repo.active_horizon(query.at, parse_bbox(query.bbox)), query.at)
    return closure_view.render(states)


@bp.get("/closures/events")
def get_closure_events() -> Response:
    query = ClosureEventsQuery.model_validate(request.args.to_dict())  # 실패 → error_view 400
    bbox = parse_bbox(query.bbox) if query.bbox is not None else None
    m = naru_models()
    result = listed(query, datetime.now(KST), m.repo, m.engine, bbox, m.index.district_of)
    tag = request.headers.get("If-None-Match")
    return closure_view.render_events(result, m.ped.bounds(), m.repo.data_as_of(), tag)
