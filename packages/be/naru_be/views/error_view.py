"""error_view — 도메인 예외·검증 오류 → ErrorBody(INTERFACE §6) + HTTP 코드.

NaruError(code·http_status·field) 와 pydantic ValidationError(→ invalid_query 400, 첫 오류의 필드)
를 받는다. 404·401·500 은 app factory 가 render_code 로 만든다. DB 를 모른다.
"""

from __future__ import annotations

from flask import Response, jsonify
from pydantic import ValidationError

from naru_be.errors import NaruError
from naru_contracts import ErrorBody
from naru_contracts.errors import ErrorCode, ErrorDetail


def render(exc: NaruError | ValidationError) -> tuple[Response, int]:
    if isinstance(exc, NaruError):
        return render_code(exc.code, exc.message, exc.http_status, exc.field)
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"]) or None
    message = f"{field}: {first['msg']}" if field else first["msg"]
    return render_code("invalid_query", message, 400, field)


def render_code(
    code: str, message: str, http_status: int, field: str | None = None
) -> tuple[Response, int]:
    detail = ErrorDetail(code=_code(code), message=message, field=field)
    return jsonify(ErrorBody(error=detail).model_dump(mode="json")), http_status


def _code(code: str) -> ErrorCode:
    if code == "invalid_query":
        return "invalid_query"
    if code == "unauthorized":
        return "unauthorized"
    if code == "not_found":
        return "not_found"
    if code == "no_route":
        return "no_route"
    if code == "out_of_coverage":
        return "out_of_coverage"
    if code == "geocode_unavailable":
        return "geocode_unavailable"
    return "internal"
