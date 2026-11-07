"""BE 도메인 예외 — INTERFACE §6 오류 코드와 1:1. Model 이 던지고 error_view 가 응답으로 만든다.

code ∈ {invalid_query, unauthorized, not_found, no_route, internal}. Flask 를 모른다.
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
