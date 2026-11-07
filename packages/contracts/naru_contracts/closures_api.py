"""BE → FE: GET /closures (INTERFACE §3) — GeoJSON FeatureCollection."""

from datetime import datetime
from typing import Literal

from pydantic import field_validator

from naru_contracts._base import Contract
from naru_contracts.closure import LngLat, _require_offset
from naru_contracts.enums import Impact, Status


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
