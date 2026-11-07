"""CrosswalkIndex — geometry → 횡단보도 관리번호 집합 (ARCHITECTURE BE Model, INTERFACE §1, T1.2).

관리번호 점은 OA-23081(T0.2, EPSG:5186). 미터 계산은 EPSG:5179 (CONVENTIONS §0).
  from_point(lng, lat, radius_m=30)   점 반경 안의 횡단보도
  from_line(coords, buffer_m=15)      선 버퍼 안의 횡단보도 (코스 폴리라인, 버스 이탈, 돌발 링크)
  from_segment(seg)                   RoadGraph.shortest_path(from→via→to, road) → 선 → 등급별 버퍼
                                      (대로 25 / 로 15 / 길 8 m. road_class 없으면 road 접미사,
                                      그것도 없으면 15 m)
임계값은 naru_be/config.py Settings. 모델이 만든 좌표는 받지 않는다 — PlacePoint는 리졸버 출력이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import shapely
from pyproj import Transformer
from shapely.strtree import STRtree

from naru_be.config import Settings
from naru_be.models.domain.road_graph import RoadGraph
from naru_contracts import RoadClass, SegmentGeom

LngLat = tuple[float, float]
_5186_TO_5179 = Transformer.from_crs("EPSG:5186", "EPSG:5179", always_xy=True)
_5179_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
XLSX_COLUMNS = (
    "연번",
    "자치구",
    "횡단보도관리번호",
    "교차로관리번호",
    "횡단보도종류",
    "보행등유무",
    "교차로명",
    "X좌표",
    "Y좌표",
)


@dataclass(frozen=True)
class Crosswalk:
    crosswalk_id: str  # 횡단보도관리번호 (INTERFACE의 crosswalk_id)
    intersection_id: str  # 교차로관리번호
    intersection_name: str  # 교차로명 (리졸버 지명사전과 공유)
    kind: str  # 횡단보도종류
    has_signal: bool  # 보행등유무 '유'
    district: str
    lng: float
    lat: float
    x: float  # EPSG:5179
    y: float


def _road_class_of(road: str | None) -> RoadClass | None:
    if not road:
        return None
    for cls in (RoadClass.daero, RoadClass.ro, RoadClass.gil):  # 대로를 로보다 먼저
        if road.endswith(cls.value):
            return cls
    return None


class CrosswalkIndex:
    def __init__(
        self,
        crosswalks: Sequence[Crosswalk],
        settings: Settings | None = None,
        road_graph: RoadGraph | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.road_graph = road_graph
        self._items = list(crosswalks)
        self._by_id = {c.crosswalk_id: c for c in self._items}
        self._tree = STRtree([shapely.Point(c.x, c.y) for c in self._items])

    @classmethod
    def from_xlsx(
        cls,
        xlsx: Path,
        settings: Settings | None = None,
        road_graph: RoadGraph | None = None,
    ) -> CrosswalkIndex:
        settings = settings or Settings()
        districts = set(settings.districts)
        wb = openpyxl.load_workbook(xlsx, read_only=True)
        try:
            rows = wb.worksheets[0].iter_rows(values_only=True)
            header = tuple(str(h) for h in next(rows))
            if header != XLSX_COLUMNS:
                raise ValueError(f"OA-23081 컬럼이 다르다: {header}")
            items: list[Crosswalk] = []
            for row in rows:
                if row[1] not in districts or row[7] is None or row[8] is None:
                    continue
                x, y = _5186_TO_5179.transform(float(str(row[7])), float(str(row[8])))
                lng, lat = _5179_TO_4326.transform(x, y)
                items.append(
                    Crosswalk(
                        crosswalk_id=str(row[2]),
                        intersection_id=str(row[3]),
                        intersection_name=str(row[6]),
                        kind=str(row[4]),
                        has_signal=str(row[5]) == "유",
                        district=str(row[1]),
                        lng=lng,
                        lat=lat,
                        x=x,
                        y=y,
                    )
                )
        finally:
            wb.close()
        return cls(items, settings, road_graph)

    def __len__(self) -> int:
        return len(self._items)

    def get(self, crosswalk_id: str) -> Crosswalk:
        return self._by_id[crosswalk_id]

    def _within(self, area: shapely.Geometry) -> set[str]:
        return {
            self._items[int(i)].crosswalk_id for i in self._tree.query(area, predicate="intersects")
        }

    def from_point(self, lng: float, lat: float, radius_m: float | None = None) -> set[str]:
        x, y = _4326_TO_5179.transform(lng, lat)
        return self._within(shapely.Point(x, y).buffer(radius_m or self.settings.point_radius_m))

    def from_line(self, coords: Sequence[LngLat], buffer_m: float | None = None) -> set[str]:
        if len(coords) < 2:
            raise ValueError("선은 점이 둘 이상이어야 한다")
        line = shapely.LineString([_4326_TO_5179.transform(lng, lat) for lng, lat in coords])
        return self._within(line.buffer(buffer_m or self.settings.line_buffer_m))

    def from_segment(self, seg: SegmentGeom) -> set[str]:
        """구간 → 도로 그래프 최단경로 → 등급별 버퍼 → 횡단보도. RoadGraph가 없으면 쓸 수 없다."""
        if self.road_graph is None:
            raise ValueError("from_segment에는 RoadGraph가 필요하다")
        points = [
            (seg.from_.lng, seg.from_.lat),
            *((v.lng, v.lat) for v in seg.via),
            (seg.to.lng, seg.to.lat),
        ]
        path = self.road_graph.shortest_path(points, road=seg.road)
        road_class = seg.road_class or _road_class_of(seg.road)
        buffer_m = (
            self.settings.road_buffer_m[road_class.value]
            if road_class
            else self.settings.line_buffer_m
        )
        return self.from_line(path.coords, buffer_m)
