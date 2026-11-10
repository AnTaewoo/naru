"""report_view — 통제 제보 응답 (INTERFACE §8, T7.15). DB 를 모른다."""

from __future__ import annotations

from flask import Response, jsonify

from naru_be.models.domain.reports import NearestHit
from naru_be.models.repositories.report_repository import ReportRow
from naru_contracts import (
    NearestCrosswalk,
    NearestCrosswalkResponse,
    RecentReportsResponse,
    ReportCounts,
    ReportResponse,
)


def render_nearest(hit: NearestHit | None) -> Response:
    if hit is None:
        return jsonify(NearestCrosswalkResponse(crosswalk=None).model_dump(mode="json"))
    c = hit.crosswalk
    found = NearestCrosswalk(
        id=c.crosswalk_id,
        name=c.intersection_name,
        district=c.district,
        coord=(c.lng, c.lat),
        distance_m=round(hit.distance_m),
    )
    return jsonify(NearestCrosswalkResponse(crosswalk=found).model_dump(mode="json"))


def render_saved(row: ReportRow) -> tuple[Response, int]:
    body = ReportResponse(
        id=row.id, crosswalk_id=row.crosswalk_id, state=row.state, reported_at=row.reported_at
    )
    return jsonify(body.model_dump(mode="json")), 201


def render_recent(counts: dict[str, tuple[int, int]]) -> Response:
    body = RecentReportsResponse(
        counts={cid: ReportCounts(blocked=b, open=o) for cid, (b, o) in counts.items()}
    )
    return jsonify(body.model_dump(mode="json"))
