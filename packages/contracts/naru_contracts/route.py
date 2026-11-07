"""BE → FE: GET /route (INTERFACE §2)."""

from datetime import datetime

from pydantic import Field, field_validator

from naru_contracts._base import Contract
from naru_contracts.closure import Evidence, LngLat, _require_offset
from naru_contracts.enums import LegKind, Status


class RouteQuery(Contract):
    from_: str = Field(alias="from")  # "lat,lng" (쿼리 문자열 그대로. 파싱은 BE Model)
    to: str
    depart_at: datetime
    mode: str = "walk"

    _tz = field_validator("depart_at")(_require_offset)


class LineString(Contract):
    type: str = "LineString"
    coordinates: list[LngLat]


class Leg(Contract):
    kind: LegKind
    name: str | None = None
    distance_m: float


class Avoided(Contract):
    crosswalk_id: str
    status: Status
    reason: str
    until: datetime | None = None
    evidence: list[Evidence]

    _tz = field_validator("until")(_require_offset)


class Baseline(Contract):
    route: LineString
    duration_s: float
    distance_m: float


class RouteResponse(Contract):
    route: LineString
    duration_s: float
    distance_m: float
    legs: list[Leg]
    avoided: list[Avoided]
    baseline: Baseline
    computed_at: datetime

    _tz = field_validator("computed_at")(_require_offset)
