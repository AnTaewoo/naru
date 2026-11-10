"""BE 도메인 예외 — INTERFACE §6 오류 코드와 1:1. Model 이 던지고 error_view 가 응답으로 만든다.

code ∈ {invalid_query, unauthorized, not_found, no_route, out_of_coverage, geocode_unavailable,
too_many_reports, internal}.
Flask 를 모른다.
"""

from __future__ import annotations


class NaruError(Exception):
    code = "internal"
    http_status = 500

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class InvalidQueryError(NaruError):
    code = "invalid_query"
    http_status = 400


class NoRouteError(NaruError):
    code = "no_route"
    http_status = 422


class GeocodeUnavailableError(NaruError):
    """카카오 로컬을 못 불렀다 — 키 없음·오류·시간 초과·기록 없음 (INTERFACE §6·§7, ADR-011 B)."""

    code = "geocode_unavailable"
    http_status = 503


class OutOfCoverageError(NaruError):
    """출발·도착이 보행망에서 max_snap_m 보다 멀다 (ADR-011 그래프 밖). field = from | to."""

    code = "out_of_coverage"
    http_status = 422


class TooManyReportsError(NaruError):
    """같은 기기·같은 횡단보도를 report_min_interval_s 안에 다시 제보 (INTERFACE §8.2, T7.15)."""

    code = "too_many_reports"
    http_status = 429
