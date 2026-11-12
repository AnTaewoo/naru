"""feed_view — FeedResult → GeoJSON FeedCollection(INTERFACE §3.3) → JSON. DB 를 모른다.

ETag(본문 sha1)·If-None-Match → 304, Cache-Control public max-age=feed_cache_s, 누구나 받게 CORS *.
"""

from __future__ import annotations

import hashlib

from flask import Response, jsonify

from naru_be.models.domain.feed import FeedCrosswalk, FeedResult
from naru_contracts import (
    ClosureEvent,
    FeedCollection,
    FeedFeature,
    FeedProperties,
    LineStringGeometry,
)
from naru_contracts.closures_api import PointGeometry


def _props(e: ClosureEvent, kind: str, **extra: object) -> FeedProperties:
    return FeedProperties.model_validate(
        {
            "kind": kind,
            "event_id": e.id,
            "event": e.reason,
            "type": e.type,
            "source": e.source,
            "start": e.window.start,
            "end": e.window.end,
            "status": e.status,
            "confidence": e.confidence,
            "approx": e.approx,
            **extra,
        }
    )


def _crosswalk(c: FeedCrosswalk) -> FeedFeature:
    return FeedFeature(
        geometry=PointGeometry(coordinates=(c.state.lng, c.state.lat)),
        properties=_props(
            c.event,
            "crosswalk",
            status=c.state.status,
            confidence=c.state.confidence,
            approx=c.state.approx,
            crosswalk_id=c.state.crosswalk_id,
            name=c.name,
            p=c.p,
        ),
    )


def to_collection(result: FeedResult, attribution: str, cache_s: int) -> FeedCollection:
    features: list[FeedFeature] = [_crosswalk(c) for c in result.crosswalks]
    for e in result.events:
        if e.area is not None:
            features.append(FeedFeature(geometry=e.area, properties=_props(e, "area")))
        path = result.paths.get(e.id)
        if path:
            geometry = LineStringGeometry(coordinates=list(path))
            features.append(FeedFeature(geometry=geometry, properties=_props(e, "march_path")))
    return FeedCollection(
        at=result.at, generated_at=result.generated_at, attribution=attribution, features=features
    )


def render(
    result: FeedResult, attribution: str, cache_s: int, if_none_match: str | None = None
) -> Response:
    body = to_collection(result, attribution, cache_s)
    resp = jsonify(body.model_dump(mode="json"))
    etag = f'"{hashlib.sha1(resp.get_data()).hexdigest()}"'
    seen = {t.strip().removeprefix("W/") for t in (if_none_match or "").split(",")}
    if etag in seen:
        resp = Response(status=304)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = f"public, max-age={cache_s}"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
