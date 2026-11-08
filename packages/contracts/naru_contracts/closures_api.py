"""BE → FE: GET /closures (INTERFACE §3) — GeoJSON FeatureCollection.

GET /closures/events (§3.1, ADR-010) — 통제 사건 목록.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from naru_contracts._base import Contract
from naru_contracts.closure import CandidateSummary, LngLat, NoticeRef, Window, _require_offset
from naru_contracts.enums import ClosureType, Impact, Source, Status


class ClosuresQuery(Contract):
    bbox: str  # "minLng,minLat,maxLng,maxLat"
    at: datetime

    _tz = field_validator("at")(_require_offset)


class PointGeometry(Contract):
    type: Literal["Point"] = "Point"
    coordinates: LngLat


class PolygonGeometry(Contract):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[LngLat]]


class FeatureProperties(Contract):
    status: Status
    confidence: float
    window: dict[str, datetime | None]
    reason: str
    crosswalk_id: str | None = None
    zone_name: str | None = None
    evidence: list[dict[str, object]] | None = None
    impact: Impact = Impact.blocks  # ADR-008
    approx: bool = False


class Feature(Contract):
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry | PolygonGeometry
    properties: FeatureProperties


class FeatureCollection(Contract):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]


class ClosureEventsQuery(Contract):
    bbox: str | None = None  # "minLng,minLat,maxLng,maxLat", 없으면 전체 (§3.1)


class ClosureEvent(Contract):
    """같은 (reason, window) 의 횡단보도 상태 묶음 (§3.1). 상태는 시각마다 달라서 없다."""

    reason: str
    window: Window
    crosswalks: int = Field(ge=1)  # 서로 다른 횡단보도 수
    bbox: tuple[float, float, float, float]  # minLng, minLat, maxLng, maxLat
    approx: bool = False
    # v0.12 (ADR-012) — 후보의 종류·출처·summary·notice_ref 그대로. v0.12 전 상태는 null
    type: ClosureType | None = None
    source: Source | None = None
    summary: CandidateSummary | None = None
    notice: NoticeRef | None = None

    @model_validator(mode="after")
    def _bbox_min_max(self) -> "ClosureEvent":
        min_lng, min_lat, max_lng, max_lat = self.bbox
        if min_lng > max_lng or min_lat > max_lat:
            raise ValueError(f"bbox 의 min 이 max 보다 크다: {list(self.bbox)}")
        return self


class DataAsOf(Contract):
    """출처별로 저장된 통제의 가장 늦은 근거 시각 (v0.12, ADR-011 C·ADR-012). 없으면 null."""

    topis_incident: datetime | None
    topis_notice: datetime | None
    smpa: datetime | None
    course: datetime | None

    _tz = field_validator("topis_incident", "topis_notice", "smpa", "course")(_require_offset)


class ClosureEventsResponse(Contract):
    events: list[ClosureEvent]
    # v0.10 (ADR-011 C) — 보행망 노드의 minLng, minLat, maxLng, maxLat. 내 위치가 밖이면 FE 가 안내
    coverage: tuple[float, float, float, float]
    data_as_of: DataAsOf  # v0.12

    @model_validator(mode="after")
    def _coverage_min_max(self) -> "ClosureEventsResponse":
        min_lng, min_lat, max_lng, max_lat = self.coverage
        if min_lng > max_lng or min_lat > max_lat:
            raise ValueError(f"coverage 의 min 이 max 보다 크다: {list(self.coverage)}")
        return self

    @model_validator(mode="after")
    def _latest_first(self) -> "ClosureEventsResponse":
        """window.start 가 늦은 것 먼저, start 가 없으면 끝 (§3.1)."""
        seen_none = False
        prev: datetime | None = None
        for k, event in enumerate(self.events):
            start = event.window.start
            if start is None:
                seen_none = True
                continue
            if seen_none or (prev is not None and start > prev):
                raise ValueError(f"events[{k}] — 시작이 늦은 것 먼저, 시작 없는 것은 끝")
            prev = start
        return self
