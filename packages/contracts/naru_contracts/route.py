"""BE → FE: GET /route (INTERFACE §2)."""

import re
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from naru_contracts._base import Contract
from naru_contracts.closure import Evidence, LngLat, _require_offset
from naru_contracts.enums import LegKind, Status

AVOID_MAX = 10  # 한 번에 피할 사건 수 (v0.14)
EVENT_ID = re.compile(r"[0-9a-f]{12}")  # §3.1 사건 id


class RouteQuery(Contract):
    from_: str = Field(alias="from")  # "lat,lng" (쿼리 문자열 그대로. 파싱은 BE Model)
    to: str
    depart_at: datetime
    mode: str = "walk"
    # v0.14 (ADR-014 A, T7.6) — 사건 id(§3.1) 쉼표로 여럿.
    # 그 사건 횡단보도를 시각·확신도와 상관없이 막는다
    avoid: tuple[str, ...] = ()

    _tz = field_validator("depart_at")(_require_offset)

    @field_validator("avoid", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        """쿼리 문자열 "id,id" → 튜플 (빈 칸은 뺀다)"""
        if isinstance(v, str):
            return tuple(p for p in (x.strip() for x in v.split(",")) if p)
        return v

    @field_validator("avoid")
    @classmethod
    def _ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        bad = next((x for x in v if not EVENT_ID.fullmatch(x)), None)
        if bad is not None:
            raise ValueError(f"avoid: 사건 id 는 12자리 소문자 16진수 ({bad})")
        ids = tuple(dict.fromkeys(v))  # 겹치면 하나, 순서 그대로
        if len(ids) > AVOID_MAX:
            raise ValueError(f"avoid: 사건 {AVOID_MAX}개까지 ({len(ids)}개)")
        return ids


class LineString(Contract):
    type: str = "LineString"
    coordinates: list[LngLat]


LEG_DISTANCE_TOLERANCE_M = 1.0  # Σ legs.distance_m 와 distance_m 의 반올림 차 허용 (ADR-009)


class Leg(Contract):
    kind: LegKind
    name: str | None = None
    distance_m: float
    # ADR-009: route.coordinates 인덱스 [i, j], 양끝 포함. 이웃 레그는 경계 점을 공유한다
    coord_range: tuple[int, int]


class Avoided(Contract):
    crosswalk_id: str
    status: Status
    reason: str
    until: datetime | None = None
    evidence: list[Evidence]
    approx: bool = False  # ADR-008: 후보의 approx 그대로

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

    @model_validator(mode="after")
    def _legs_partition_route(self) -> "RouteResponse":
        """ADR-009: 레그가 route.coordinates 를 빈틈없이 나누고, 거리 합이 총거리와 같다."""
        if not self.legs:
            return self
        n = len(self.route.coordinates)
        prev_end = 0
        for k, leg in enumerate(self.legs):
            i, j = leg.coord_range
            if not 0 <= i <= j < n:
                raise ValueError(f"legs[{k}].coord_range {[i, j]} 가 route 좌표 0..{n - 1} 밖")
            if i != prev_end:
                raise ValueError(f"legs[{k}].coord_range 는 {prev_end} 에서 시작해야 (받은 {i})")
            prev_end = j
        if prev_end != n - 1:
            raise ValueError(f"마지막 레그는 route 끝 {n - 1} 까지 (받은 {prev_end})")
        total = sum(leg.distance_m for leg in self.legs)
        if abs(total - self.distance_m) > LEG_DISTANCE_TOLERANCE_M:
            raise ValueError(f"Σ legs.distance_m {total:.1f} ≠ distance_m {self.distance_m}")
        return self
