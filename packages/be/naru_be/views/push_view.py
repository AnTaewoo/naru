"""push_view — 구독·관심 지역 응답 (INTERFACE §9, T7.8). DB 를 모른다."""

from __future__ import annotations

from collections.abc import Sequence

from flask import Response, jsonify

from naru_be.models.repositories.push_repository import SubscriptionRow, WatchAreaRow
from naru_contracts import SubscribeResponse, VapidPublicKey, WatchArea, WatchAreasResponse
from naru_contracts.push_api import WatchKind


def render_key(public_key: str) -> Response:
    return jsonify(VapidPublicKey(public_key=public_key).model_dump(mode="json"))


def render_subscribed(row: SubscriptionRow) -> tuple[Response, int]:
    body = SubscribeResponse(id=row.id, active=row.active, created_at=row.created_at)
    return jsonify(body.model_dump(mode="json")), 201


def _area(a: WatchAreaRow) -> WatchArea:
    kind: WatchKind = "last_seen" if a.kind == "last_seen" else "saved"
    return WatchArea(
        id=a.id,
        kind=kind,
        lng=a.lng,
        lat=a.lat,
        radius_m=a.radius_m,
        created_at=a.created_at,
        expires_at=a.expires_at,
    )


def render_area(a: WatchAreaRow) -> tuple[Response, int]:
    return jsonify(_area(a).model_dump(mode="json")), 201


def render_areas(areas: Sequence[WatchAreaRow]) -> Response:
    body = WatchAreasResponse(areas=[_area(a) for a in areas])
    return jsonify(body.model_dump(mode="json"))


def render_gone() -> Response:
    return Response(status=204)
