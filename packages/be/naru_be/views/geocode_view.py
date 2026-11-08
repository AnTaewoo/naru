"""지오코딩 응답 (INTERFACE §7). 계약이 개수·label 규칙을 검증한다. DB 를 모른다."""

from __future__ import annotations

from collections.abc import Sequence

from flask import Response, jsonify

from naru_contracts import GeocodeReverseResponse, GeocodeSearchResponse, Place


def render_search(places: Sequence[Place]) -> Response:
    return jsonify(GeocodeSearchResponse(places=list(places)).model_dump(mode="json"))


def render_reverse(address: GeocodeReverseResponse) -> Response:
    return jsonify(address.model_dump(mode="json"))
