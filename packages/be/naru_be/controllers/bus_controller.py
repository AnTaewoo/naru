"""POST /internal/bus-positions — AI 워커 전용 (INTERFACE §1.2, T6.2).

토큰 검사는 /internal/candidates 와 같은 함수.
"""

from __future__ import annotations

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.controllers.candidate_controller import require_token
from naru_be.views import bus_view
from naru_contracts import BusPositionBatch

bp = Blueprint("internal_bus", __name__, url_prefix="/internal")
bp.before_request(require_token)


@bp.post("/bus-positions")
def post_bus_positions() -> tuple[Response, int]:
    batch = BusPositionBatch.model_validate(request.get_json())  # 실패 → error_view 400
    return bus_view.render(naru_models().bus_intake.accept(batch))
