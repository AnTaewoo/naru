"""통제 제보 — POST /crosswalks/nearest · POST /reports · GET /reports/recent (INTERFACE §8, T7.15).

검증 → ReportDesk → report_view. 좌표는 nearest 본문으로만 받고 저장·로그하지 않는다.
"""

from __future__ import annotations

from flask import Blueprint, Response, request

from naru_be.controllers._deps import naru_models
from naru_be.views import report_view
from naru_contracts import NearestCrosswalkQuery, RecentReportsQuery, ReportRequest

bp = Blueprint("reports", __name__)


@bp.post("/crosswalks/nearest")
def nearest() -> Response:
    query = NearestCrosswalkQuery.model_validate(request.get_json(silent=True))  # 실패 → 400
    return report_view.render_nearest(naru_models().report_desk.nearest(query.lng, query.lat))


@bp.post("/reports")
def post_report() -> tuple[Response, int]:
    report = ReportRequest.model_validate(request.get_json(silent=True))
    return report_view.render_saved(naru_models().report_desk.submit(report))


@bp.get("/reports/recent")
def recent() -> Response:
    query = RecentReportsQuery.model_validate(request.args.to_dict())
    return report_view.render_recent(naru_models().report_desk.recent(query.ids, query.minutes))
