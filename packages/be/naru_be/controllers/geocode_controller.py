"""GET /geocode/search · /geocode/reverse — 검증 → Geocoder(카카오 로컬) → View.

INTERFACE §7, ADR-011 B.
"""

from __future__ import annotations

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.models.domain.parsing import parse_latlng
from naru_be.views import geocode_view
from naru_contracts import GeocodeReverseQuery, GeocodeSearchQuery

bp = Blueprint("geocode", __name__)


@bp.get("/geocode/search")
def search() -> Response:
    query = GeocodeSearchQuery.model_validate(request.args.to_dict())  # 실패 → error_view 400
    near = parse_latlng(query.near, "near") if query.near is not None else None
    return geocode_view.render_search(naru_models().geocoder.search(query.q, near))


@bp.get("/geocode/reverse")
def reverse() -> Response:
    query = GeocodeReverseQuery.model_validate(request.args.to_dict())
    return geocode_view.render_reverse(naru_models().geocoder.reverse(query.lng, query.lat))
