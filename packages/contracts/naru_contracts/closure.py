"""AI → BE: ClosureCandidate, CandidateBatch (INTERFACE §1, §1.1). BE 내부·FE 공용: ClosureState."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from naru_contracts._base import Contract
from naru_contracts.enums import ClosureType, EvidenceKind, RoadClass, Source, Status

LngLat = tuple[float, float]  # [lng, lat] 순서 (INTERFACE 표기 규칙)


def _require_offset(v: datetime | None) -> datetime | None:
    if v is not None and v.tzinfo is None:
        raise ValueError("오프셋 없는 시각 — ISO 8601 + 오프셋 필수")
    return v


class Window(Contract):
    start: datetime | None = None
    end: datetime | None = None  # None = 종료 미정 (엔진이 시작+6h 임시 end)

    _tz = field_validator("start", "end")(_require_offset)

    @model_validator(mode="after")
    def _some_bound(self) -> "Window":
        if self.start is None and self.end is None:
            raise ValueError("window는 start·end 중 하나는 있어야 한다")
        return self


class PlacePoint(Contract):
    """리졸버가 정규형을 좌표로 바꾼 결과. 모델(Claude)이 만든 좌표는 여기 들어올 수 없다."""

    canonical: str
    lng: float
    lat: float
    gazetteer_source: str  # kakao | seoul_intersection | seoul_station | road_db
    gazetteer_id: str


class PointGeom(Contract):
    kind: Literal["point"] = "point"
    coordinates: LngLat


class LineGeom(Contract):
    kind: Literal["line"] = "line"
    coordinates: list[LngLat] = Field(min_length=2)


class SegmentGeom(Contract):
    """구간. 선은 BE CrosswalkIndex.from_segment가 도로 그래프 최단경로로 만든다."""

    kind: Literal["segment"] = "segment"
    from_: PlacePoint
    to: PlacePoint
    via: list[PlacePoint] = Field(default_factory=list)
    road: str | None = None  # 도로명 정규형. 있으면 그 도로 링크만 지나도록 제한
    road_class: RoadClass | None = None


class ZoneGeom(Contract):
    kind: Literal["zone"] = "zone"
    zone_name: str
    polygon: list[list[LngLat]]  # GeoJSON Polygon coordinates


Geometry = Annotated[PointGeom | LineGeom | SegmentGeom | ZoneGeom, Field(discriminator="kind")]


class Evidence(Contract):
    kind: EvidenceKind
    ref: str
    at: datetime
    detail: dict[str, float | int | str] | None = None

    _tz = field_validator("at")(_require_offset)


class NoticeRef(Contract):
    notice_id: str
    sentence_id: str
    source_url: str
    published_at: datetime
    excerpt: str

    _tz = field_validator("published_at")(_require_offset)


class ClosureCandidate(Contract):
    candidate_id: str
    source: Source
    type: ClosureType
    status_hint: Status
    geometry: Geometry
    window: Window
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(min_length=1)
    notice_ref: NoticeRef | None = None
    review_required: bool = False

    @model_validator(mode="after")
    def _review_rule(self) -> "ClosureCandidate":
        # INTERFACE §1: confidence < 0.7 → review_required.
        # 임계값은 BE config와 같아야 한다 (T2.1 테스트가 대조)
        if self.confidence < 0.7 and not self.review_required:
            raise ValueError("confidence < 0.7 이면 review_required=True 여야 한다")
        return self


class CandidateBatch(Contract):
    batch_id: str
    produced_at: datetime
    producer: str
    candidates: list[ClosureCandidate]

    _tz = field_validator("produced_at")(_require_offset)


class CandidateBatchResponse(Contract):
    batch_id: str
    accepted: int
    review_required: int
    crosswalks_updated: int


class ClosureState(Contract):
    """횡단보도 하나의 현재 상태. BE Repository 결과이자 /closures Feature properties."""

    crosswalk_id: str
    status: Status
    confidence: float = Field(ge=0.0, le=1.0)
    window: Window
    reason: str
    evidence: list[Evidence]
    lng: float
    lat: float
