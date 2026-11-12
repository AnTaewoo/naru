"""서울 실시간 도시데이터 주요 121장소 영역 (T7.19) — raw/citydata_areas_<날짜>/**/*.shp.

열린데이터광장 OA-21285 첨부 "서울시 주요 121장소 영역.zip"(EPSG:4326, AREA_CD·CATEGORY·AREA_NM,
MANIFEST). 활성 통제 중심에서 가까운 장소를 고르는 데만 쓴다 — citydata 호출의 키는 AREA_NM.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

_TO_M = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


@dataclass(frozen=True)
class Area:
    code: str  # AREA_CD (POI009)
    name: str  # AREA_NM (광화문·덕수궁) — citydata 호출의 키
    category: str
    geom: BaseGeometry  # EPSG:5179


class AreaBook:
    """주요 121장소 영역 — raw/citydata_areas_<날짜>/**/*.shp (EPSG:4326, AREA_CD·AREA_NM)."""

    def __init__(self, areas: Sequence[Area]) -> None:
        self.areas = list(areas)

    @classmethod
    def load(cls, raw_dir: Path) -> AreaBook:
        import geopandas as gpd  # 무거운 import 는 여기서만 (워커 시작 때 한 번)

        dirs = sorted(p for p in raw_dir.glob("citydata_areas_*") if p.is_dir())
        if not dirs:
            raise FileNotFoundError(
                f"실데이터 없음: {raw_dir}/citydata_areas_* — make fetch SRC=citydata_areas"
            )
        shp = next(dirs[-1].rglob("*.shp"), None)
        if shp is None:
            raise FileNotFoundError(f"shp 없음: {dirs[-1]}")
        g = gpd.read_file(shp).to_crs(5179)
        return cls(
            [
                Area(str(r.AREA_CD), str(r.AREA_NM), str(r.CATEGORY), r.geometry)
                for r in g.itertuples()
            ]
        )

    def near(self, point: tuple[float, float], radius_m: float, limit: int) -> list[Area]:
        """[lng, lat] 에서 radius_m 안의 장소 — 가까운 순(영역 안이면 0), 같으면 코드순."""
        p = Point(_TO_M.transform(point[0], point[1]))
        ranked = sorted(
            ((a.geom.distance(p), a.code, a) for a in self.areas), key=lambda t: (t[0], t[1])
        )
        return [a for d, _, a in ranked if d <= radius_m][:limit]
