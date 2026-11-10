"""알림 구독·관심 지역 — INTERFACE §9 (ADR-014 C, T7.8). 검증 → PushDesk → push_view.

GET /push/vapid-public-key · POST·DELETE /push/subscribe · GET·POST /watch-areas ·
DELETE /watch-areas/<id>. GET·DELETE 의 구독 endpoint 는 헤더 X-Push-Endpoint (주소·접근 로그에
안 남게). POST /internal/push/dispatch (워커, 토큰, T7.9) — 매칭·발송 한 바퀴.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, Request, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.controllers.candidate_controller import require_token
from naru_be.models.domain.types import KST
from naru_be.views import push_view
from naru_contracts import (
    PushDispatchRequest,
    PushSubscription,
    UnsubscribeRequest,
    WatchAreaRequest,
)

bp = Blueprint("push", __name__)
internal = Blueprint("internal_push", __name__, url_prefix="/internal")
internal.before_request(require_token)
ENDPOINT_HEADER = "X-Push-Endpoint"


def endpoint_of(req: Request) -> str:
    """헤더의 구독 endpoint — 모양은 계약(UnsubscribeRequest)이 검사한다 (없으면 400)."""
    return UnsubscribeRequest.model_validate(
        {"endpoint": req.headers.get(ENDPOINT_HEADER, "")}
    ).endpoint


@bp.get("/push/vapid-public-key")
def vapid_public_key() -> Response:
    return push_view.render_key(naru_models().push.public_key())


@bp.post("/push/subscribe")
def subscribe() -> tuple[Response, int]:
    sub = PushSubscription.model_validate(request.get_json(silent=True))  # 실패 → 400
    return push_view.render_subscribed(naru_models().push.subscribe(sub, datetime.now(KST)))


@bp.delete("/push/subscribe")
def unsubscribe() -> Response:
    body = UnsubscribeRequest.model_validate(request.get_json(silent=True))
    naru_models().push.unsubscribe(body.endpoint)
    return push_view.render_gone()


@bp.get("/watch-areas")
def watch_areas() -> Response:
    areas = naru_models().push.areas(endpoint_of(request), datetime.now(KST))
    return push_view.render_areas(areas)


@bp.post("/watch-areas")
def add_watch_area() -> tuple[Response, int]:
    body = WatchAreaRequest.model_validate(request.get_json(silent=True))
    return push_view.render_area(naru_models().push.add_area(body, datetime.now(KST)))


@bp.delete("/watch-areas/<int:area_id>")
def remove_watch_area(area_id: int) -> Response:
    naru_models().push.remove_area(endpoint_of(request), area_id)
    return push_view.render_gone()


@internal.post("/push/dispatch")
def dispatch() -> Response:
    body = PushDispatchRequest.model_validate(request.get_json(silent=True) or {})
    result = naru_models().push.dispatch(body.at or datetime.now(KST))
    return push_view.render_dispatch(result)
