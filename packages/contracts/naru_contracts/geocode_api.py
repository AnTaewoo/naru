"""BE → FE: 지오코딩 (INTERFACE §7, ADR-011 B) — 카카오 로컬 API 를 BE 가 대신 부른다.

GET /geocode/search?q=&near=lat,lng (§7.1) · GET /geocode/reverse?lat=&lng= (§7.2).
"""

import math

from pydantic import Field, field_validator, model_validator

from naru_contracts._base import Contract
from naru_contracts.closure import LngLat

SEARCH_LIMIT = 10  # 한 번에 돌려주는 장소 수 (§7.1)


class GeocodeSearchQuery(Contract):
    q: str = Field(min_length=2, max_length=50)  # 앞뒤 공백을 뺀 길이
    near: str | None = None  # "lat,lng" (쿼리 문자열 그대로. 파싱은 BE Model)

    @field_validator("q", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class Place(Contract):
    id: str  # 카카오 장소 id
    name: str
    address: str  # 도로명 주소, 없으면 지번
    coord: LngLat


class GeocodeSearchResponse(Contract):
    places: list[Place] = Field(max_length=SEARCH_LIMIT)


class GeocodeReverseQuery(Contract):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    @field_validator("lat", "lng")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("숫자가 아니다")
        return v


class GeocodeReverseResponse(Contract):
    label: str | None  # 화면용 — 도로명(없으면 지번)에서 시·도를 뺀 것
    road_address: str | None
    address: str | None  # 지번

    @model_validator(mode="after")
    def _label_from_address(self) -> "GeocodeReverseResponse":
        has_address = self.road_address is not None or self.address is not None
        if (self.label is not None) != has_address:
            raise ValueError("label 은 주소가 있을 때만, 주소가 있으면 label 도 있다")
        return self
