"""오류 응답 (INTERFACE §6). Flask error_view가 만든다."""

from typing import Literal

from naru_contracts._base import Contract

ErrorCode = Literal[
    "invalid_query",
    "unauthorized",
    "not_found",
    "no_route",
    "out_of_coverage",
    "geocode_unavailable",  # v0.11 (ADR-011 B) — 카카오 로컬을 못 불렀다, 503
    "too_many_reports",  # v0.14 보충 (T7.15) — 같은 기기·횡단보도 600초 안 다시 제보, 429
    "not_modeled",  # v0.15 (ADR-015 F) — 행진 확률 모델 대상이 아닌 사건, 404
    "rate_limited",  # v0.15 보충 (T7.17) — 공개 피드 IP 당 분당 요청 상한, 429
    "push_unavailable",  # v0.15 보충 (T7.8, ADR-014 C) — 서버에 VAPID 키가 없다, 503
    "internal",
]


class ErrorDetail(Contract):
    code: ErrorCode
    message: str
    field: str | None = None


class ErrorBody(Contract):
    error: ErrorDetail
