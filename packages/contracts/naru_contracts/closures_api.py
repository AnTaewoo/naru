"""BE → FE: GET /closures (INTERFACE §3) — GeoJSON FeatureCollection.

GET /closures/events (§3.1, ADR-010·ADR-014) — 통제 사건 목록. v0.14: at 을 주면 지금 지도용
(시간 창·사건 상태·id).
"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

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


class MultiPolygonGeometry(Contract):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[LngLat]]]


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
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    bbox: str | None = None  # "minLng,minLat,maxLng,maxLat", 없으면 전체 (§3.1)
    # v0.14 (ADR-014 A) — at 을 주면 지금 지도: [from, to] 와 겹치는 사건만(from 기본 at, to 기본
    # at 다음 날 24:00 KST), 사건 status 는 at 기준. 셋 다 없으면 전부(하위 호환,
    # status 는 서버 지금)
    at: datetime | None = None
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None

    _tz = field_validator("at", "from_", "to")(_require_offset)

    @model_validator(mode="after")
    def _window(self) -> "ClosureEventsQuery":
        if self.at is None and (self.from_ is not None or self.to is not None):
            raise ValueError("from·to 는 at 과 같이")
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValueError("from 이 to 보다 늦다")
        return self


class ClosureEvent(Contract):
    """같은 (reason, window) 의 횡단보도 상태 묶음 (§3.1). status 는 응답 at 기준 (v0.14)."""

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
    # v0.13 보충(T6.9) — 사건 횡단보도들이 있는 자치구(OA-23081 이름, 가나다순). FE 구 필터 칩
    districts: list[str] = Field(default_factory=list)
    # v0.14 (ADR-014 A) — 지도 단위. id = sha1("reason|시작 UTC|끝 UTC") 앞 12자(재접수에도 같다),
    # status = 응답 at 기준 그 사건 횡단보도 중 가장 심한 상태, confidence = 가장 큰 값.
    # area·centroid = 통제 구역(T7.2) — 아직 없으면 null
    id: str = Field(pattern=r"^[0-9a-f]{12}$")
    status: Status
    confidence: float = Field(ge=0, le=1)
    area: PolygonGeometry | MultiPolygonGeometry | None = None
    centroid: LngLat | None = None

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
    # v0.14 (ADR-014 A) — 사건 status 의 기준 시각(질의 at, 없으면 서버 지금), 상한(300)에 잘렸는지
    at: datetime
    truncated: bool = False

    _tz = field_validator("at")(_require_offset)

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
