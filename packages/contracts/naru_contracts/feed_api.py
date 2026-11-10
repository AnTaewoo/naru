"""BE → 누구나: 통제 데이터 GeoJSON 피드 (INTERFACE §3.3, T7.17 — 교수님 멘토링 T-C).

GET /closures/feed?at= — 그 시각 걸린 통제를 GeoJSON FeatureCollection 으로. 횡단보도(Point)·
사건 구역(Polygon·MultiPolygon)·행진 경로(LineString). 여분 멤버 at·generated_at·attribution
(GeoJSON 허용).
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from naru_contracts._base import Contract
from naru_contracts.closure import LngLat, _require_offset
from naru_contracts.closures_api import MultiPolygonGeometry, PointGeometry, PolygonGeometry
from naru_contracts.enums import ClosureType, Source, Status

FeedKind = Literal["crosswalk", "area", "march_path"]


class FeedQuery(Contract):
    at: datetime | None = None  # 없으면 서버 지금

    _tz = field_validator("at")(_require_offset)


class LineStringGeometry(Contract):
    type: Literal["LineString"] = "LineString"
    coordinates: list[LngLat] = Field(min_length=2)


class FeedProperties(Contract):
    kind: FeedKind
    event_id: str = Field(pattern=r"^[0-9a-f]{12}$")  # §3.1 사건 id
    event: str  # 사건 이름 (reason — 공지 문장·코스 구간·돌발 제목)
    type: ClosureType | None
    source: Source | None
    start: datetime | None
    end: datetime | None
    status: Status  # 응답 at 기준
    confidence: float = Field(ge=0, le=1)
    approx: bool = False
    crosswalk_id: str | None = None  # kind crosswalk
    name: str | None = None  # 교차로명 (OA-23081)
    p: float | None = Field(
        default=None, ge=0, le=1
    )  # 행진 확률 모델(§3.2) 경로 위 횡단보도의 그 시각 P

    _tz = field_validator("start", "end")(_require_offset)


class FeedFeature(Contract):
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry | LineStringGeometry | PolygonGeometry | MultiPolygonGeometry
    properties: FeedProperties


class FeedCollection(Contract):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    at: datetime  # 상태·P 의 기준 시각(분 단위로 내림)
    generated_at: datetime
    attribution: str
    features: list[FeedFeature]

    _tz = field_validator("at", "generated_at")(_require_offset)
