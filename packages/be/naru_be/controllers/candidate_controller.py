"""POST /internal/candidates — AI 워커 전용. 토큰은 before_request 한 곳 (CONVENTIONS §4.3)."""

from __future__ import annotations

import hmac

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.views import candidate_view, error_view
from naru_contracts import CandidateBatch

bp = Blueprint("internal", __name__, url_prefix="/internal")


@bp.before_request
def require_token() -> tuple[Response, int] | None:
    expected = naru_models().settings.internal_token
    given = request.headers.get("X-Naru-Internal-Token", "")
    if not expected or not hmac.compare_digest(given, expected):
        return error_view.render_code("unauthorized", "X-Naru-Internal-Token 불일치", 401)
    return None


@bp.post("/candidates")
def post_candidates() -> tuple[Response, int]:
    batch = CandidateBatch.model_validate(request.get_json())  # 실패 → error_view 400
    result = naru_models().intake.accept(batch)
    return candidate_view.render(result)
