"""march_view — MarchResult → MarchResponse(INTERFACE §3.2) → JSON.

ETag 는 본문 sha1(키프레임은 결정적 — 같은 입력 같은 출력). DB 를 모른다.
"""

from __future__ import annotations

import hashlib

from flask import Response, jsonify

from naru_be.models.domain.march import MarchResult
from naru_contracts import MarchKeyframe, MarchResponse, Window
from naru_contracts.closure import LngLat


def render(result: MarchResult, if_none_match: str | None = None) -> Response:
    body = MarchResponse(
        event_id=result.event_id,
        window=Window(start=result.start, end=result.end),
        step_s=result.step_s,
        crosswalk_points=dict(result.crosswalk_points),
        keyframes=[
            MarchKeyframe(
                t=f.t,
                samples=[[_pt(p) for p in sample] for sample in f.samples],
                center=f.center,
                radius_m=f.radius_m,
                crosswalks=f.crosswalks,
            )
            for f in result.keyframes
        ],
    )
    resp = jsonify(body.model_dump(mode="json"))
    etag = f'"{hashlib.sha1(resp.get_data()).hexdigest()}"'
    seen = {t.strip().removeprefix("W/") for t in (if_none_match or "").split(",")}
    if etag in seen:
        resp = Response(status=304)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def _pt(p: LngLat) -> LngLat:
    return (p[0], p[1])
