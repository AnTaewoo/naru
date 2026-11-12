"""GET /closures/feed — 공개 GeoJSON 피드 (INTERFACE §3.3, T7.17).

검증 → 요청 제한 → FeedDesk → View.

IP 는 nginx 뒤라 X-Forwarded-For 첫 값, 없으면 remote_addr.
"""

from __future__ import annotations

import time
from datetime import datetime

from flask import Blueprint, Request, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.errors import RateLimitedError
from naru_be.models.domain.feed import ATTRIBUTION
from naru_be.models.domain.types import KST
from naru_be.views import feed_view
from naru_contracts import FeedQuery

bp = Blueprint("feed", __name__)


def client_ip(req: Request) -> str:
    forwarded = req.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or (req.remote_addr or "?")


@bp.get("/closures/feed")
def get_feed() -> Response:
    query = FeedQuery.model_validate(request.args.to_dict())  # 실패 → error_view 400
    m = naru_models()
    if not m.feed.limiter.allow(client_ip(request), time.monotonic()):
        raise RateLimitedError(f"분당 {m.settings.feed_rate_per_min}회까지")
    result = m.feed.collection_at(query.at or datetime.now(KST))
    return feed_view.render(
        result, ATTRIBUTION, m.settings.feed_cache_s, request.headers.get("If-None-Match")
    )
