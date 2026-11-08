"""오류 응답 (INTERFACE §6). Flask error_view가 만든다."""

from typing import Literal

from naru_contracts._base import Contract

ErrorCode = Literal[
    "invalid_query", "unauthorized", "not_found", "no_route", "out_of_coverage", "internal"
]


class ErrorDetail(Contract):
    code: ErrorCode
    message: str
    field: str | None = None


class ErrorBody(Contract):
    error: ErrorDetail
