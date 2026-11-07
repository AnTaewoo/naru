"""쿼리 문자열 파싱 — INTERFACE §2 `lat,lng`, §3 `bbox=minLng,minLat,maxLng,maxLat` (Model).

contracts 는 문자열 그대로 받고 숫자 해석은 여기서 한다. 잘못되면 InvalidQueryError(field).
"""

from __future__ import annotations

from naru_be.errors import InvalidQueryError
from naru_be.models.domain.types import LngLat

Bbox = tuple[float, float, float, float]  # minLng, minLat, maxLng, maxLat


def _floats(value: str, n: int, field: str, shape: str) -> list[float]:
    parts = value.split(",")
    if len(parts) != n:
        raise InvalidQueryError(f"{field}: '{shape}' 형식이어야 한다", field)
    try:
        return [float(p.strip()) for p in parts]
    except ValueError:
        raise InvalidQueryError(f"{field}: 숫자가 아니다", field) from None


def _check(lng: float, lat: float, field: str) -> None:
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise InvalidQueryError(f"{field}: 위경도 범위 밖 (순서를 확인)", field)


def parse_latlng(value: str, field: str) -> LngLat:
    """`lat,lng` → (lng, lat)."""
    lat, lng = _floats(value, 2, field, "lat,lng")
    _check(lng, lat, field)
    return (lng, lat)


def parse_bbox(value: str, field: str = "bbox") -> Bbox:
    """`minLng,minLat,maxLng,maxLat` → 튜플. min <= max 여야 한다."""
    min_lng, min_lat, max_lng, max_lat = _floats(value, 4, field, "minLng,minLat,maxLng,maxLat")
    _check(min_lng, min_lat, field)
    _check(max_lng, max_lat, field)
    if min_lng > max_lng or min_lat > max_lat:
        raise InvalidQueryError(f"{field}: min 이 max 보다 크다", field)
    return (min_lng, min_lat, max_lng, max_lat)
