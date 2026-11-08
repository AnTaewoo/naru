"""bus_view — BusIntakeResult → BusPositionBatchResponse(INTERFACE §1.2) → 202."""

from __future__ import annotations

from flask import Response, jsonify

from naru_be.models.domain.bus_intake import BusIntakeResult
from naru_contracts import BusPositionBatchResponse


def render(result: BusIntakeResult) -> tuple[Response, int]:
    body = BusPositionBatchResponse(batch_id=result.batch_id, accepted=result.accepted)
    return jsonify(body.model_dump(mode="json")), 202
