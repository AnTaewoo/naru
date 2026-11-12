"""candidate_view — IntakeResult → CandidateBatchResponse(INTERFACE §1.1) → 202."""

from __future__ import annotations

from flask import Response, jsonify

from naru_be.models.domain.types import IntakeResult
from naru_contracts import CandidateBatchResponse


def render(result: IntakeResult) -> tuple[Response, int]:
    body = CandidateBatchResponse(
        batch_id=result.batch_id,
        accepted=result.accepted,
        review_required=result.review_required,
        crosswalks_updated=result.crosswalks_updated,
    )
    return jsonify(body.model_dump(mode="json")), 202
