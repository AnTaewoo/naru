"""route_view — RouteResult → RouteResponse(INTERFACE §2) → JSON. DB 를 모른다."""

from __future__ import annotations

from flask import Response, jsonify

from naru_be.models.domain.types import KST, Path, RouteResult
from naru_be.views._time import evidence_kst, kst
from naru_contracts import LegKind, RouteResponse
from naru_contracts.route import Avoided, Baseline, Leg, LineString


def render(result: RouteResult) -> Response:
    return jsonify(to_response(result).model_dump(mode="json"))


def to_response(result: RouteResult) -> RouteResponse:
    path = result.path
    return RouteResponse(
        route=_line(path),
        duration_s=path.duration_s,
        distance_m=path.distance_m,
        legs=[
            Leg(
                kind=LegKind(leg.kind.value),
                name=leg.name,
                distance_m=round(leg.distance_m, 1),
                coord_range=leg.coord_range,
            )
            for leg in path.legs
        ],
        avoided=[
            Avoided(
                crosswalk_id=a.crosswalk_id,
                status=a.status,
                reason=a.reason,
                until=kst(a.until),
                evidence=evidence_kst(a.evidence),
                approx=a.approx,
            )
            for a in path.avoided
        ],
        baseline=Baseline(
            route=_line(result.baseline),
            duration_s=result.baseline.duration_s,
            distance_m=result.baseline.distance_m,
        ),
        computed_at=result.computed_at.astimezone(KST),
    )


def _line(path: Path) -> LineString:
    return LineString(coordinates=list(path.coords))
