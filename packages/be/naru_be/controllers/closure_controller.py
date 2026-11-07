"""GET /closures — 검증 → Repository.active_at → Engine.restate(시각 재판정) → closure_view (§3)."""

from __future__ import annotations

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.models.domain.parsing import parse_bbox
from naru_be.views import closure_view
from naru_contracts import ClosuresQuery

bp = Blueprint("closures", __name__)


@bp.get("/closures")
def get_closures() -> Response:
    query = ClosuresQuery.model_validate(request.args.to_dict())  # 실패 → error_view 400
    m = naru_models()
    states = m.engine.restate(m.repo.active_at(query.at, parse_bbox(query.bbox)), query.at)
    return closure_view.render(states)
