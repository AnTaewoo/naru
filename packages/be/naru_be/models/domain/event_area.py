"""사건 통제 구역 (T7.2, ADR-014 A) — 후보 모양(EPSG:5179) union → 단순화 → EPSG:4326.

후보 모양은 CrosswalkIndex 가 횡단보도를 고를 때 쓰는 것 그대로(점 30 m·선 15 m·구간 도로 경로 +
등급 버퍼) — 구역 안 횡단보도 = 그 사건이 막는 횡단보도. 중심은 무게중심, 휜 선이라 밖으로 나가면
구역 안 대표점. 단순화는 2 m 로 줄인 뒤 바깥으로 2 m(mitre)를 다시 붙인다 — Douglas-Peucker 는
경계를 허용치 안에서만 옮기니 붙인 여유가 원래 모양을 다 덮어, 고른 횡단보도는 늘 구역 안이다(5 m 로
깎기만 하면 11/9 국회대로 횡단보도 둘이 0.6·1.1 m 밖). 좌표는 소수 6자리(약 0.1 m). Flask·DB 모른다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import shapely
from numpy.typing import NDArray
from pyproj import Transformer

from naru_contracts.closure import LngLat
from naru_contracts.closures_api import MultiPolygonGeometry, PolygonGeometry

SIMPLIFY_M = 2.0  # 단순화 허용치 = 다시 붙이는 바깥 여유
_5179_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class EventArea:
    area: PolygonGeometry | MultiPolygonGeometry
    centroid: LngLat


def _to_4326(xy: NDArray[np.float64]) -> NDArray[np.float64]:
    lng, lat = _5179_TO_4326.transform(xy[:, 0], xy[:, 1])
    return np.round(np.column_stack([lng, lat]), 6)


def _rings(poly: shapely.Polygon) -> list[list[LngLat]]:
    rings = [poly.exterior, *poly.interiors]
    return [[(float(x), float(y)) for x, y in ring.coords] for ring in rings]


def event_area(shapes: Sequence[shapely.Geometry]) -> EventArea:
    """한 사건 후보들의 모양 → 구역·중심. shapes 는 EPSG:5179, 하나 이상."""
    if not shapes:
        raise ValueError("모양이 없다")
    whole = shapely.unary_union(list(shapes))
    merged = whole.simplify(SIMPLIFY_M, preserve_topology=True).buffer(
        SIMPLIFY_M, join_style="mitre", mitre_limit=2.0
    )
    center = merged.centroid
    if not merged.contains(center):
        center = merged.representative_point()
    geo = shapely.transform(merged, _to_4326)
    (lng, lat), *_ = shapely.transform(center, _to_4326).coords
    if isinstance(geo, shapely.Polygon):
        area: PolygonGeometry | MultiPolygonGeometry = PolygonGeometry(coordinates=_rings(geo))
    elif isinstance(geo, shapely.MultiPolygon):
        area = MultiPolygonGeometry(coordinates=[_rings(p) for p in geo.geoms])
    else:
        raise ValueError(f"구역이 면이 아니다: {geo.geom_type}")
    return EventArea(area, (float(lng), float(lat)))
