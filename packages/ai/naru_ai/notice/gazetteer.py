"""지명사전 — 교차로(서울시 OA-23081 교차로명)·도로명(표준노드링크 ROAD_NAME)·별칭 (규약 §3.4).

교차로 좌표 = 그 교차로관리번호에 속한 횡단보도 관리번호 점들의 평균 (EPSG:5186 → WGS84).
같은 교차로명에 관리번호가 둘 이상이면 고르지 않는다(None) — 추측 좌표 금지.
도로명은 좌표가 없다. 이름이 사전에 있는지와 road_class(대로/로/길)만 준다.
별칭(`data/raw/gazetteer/aliases.csv`: alias,canonical,sentence_id)은 파일이 있을 때만.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from pyproj import Transformer

from naru_contracts import PlacePoint, RoadClass

XLSX_COLUMNS = (
    "연번", "자치구", "횡단보도관리번호", "교차로관리번호", "횡단보도종류",
    "보행등유무", "교차로명", "X좌표", "Y좌표",
)  # fmt: skip
_5186_TO_4326 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
INTERSECTION_SUFFIX = re.compile(r"(사거리|오거리|삼거리|교차로|로터리)$")
VARIANT = re.compile(r"\((연등|경보)\)|\d+$")  # '세종대로사거리(연등)', '을지로입구역2' 같은 변형


@dataclass(frozen=True)
class Intersection:
    intersection_id: str
    name: str
    district: str
    lng: float
    lat: float
    crosswalks: int


class Gazetteer:
    def __init__(
        self,
        intersections: dict[str, list[Intersection]],
        roads: set[str],
        aliases: dict[str, str],
    ) -> None:
        self._intersections = intersections
        self._roads = roads
        self._aliases = aliases

    @classmethod
    def load(
        cls, crosswalk_xlsx: Path, link_gpkg: Path, aliases_csv: Path | None = None
    ) -> Gazetteer:
        return cls(
            cls._load_intersections(crosswalk_xlsx),
            cls._load_roads(link_gpkg),
            cls._load_aliases(aliases_csv),
        )

    # --- 적재 ---------------------------------------------------------------------
    @staticmethod
    def _load_intersections(xlsx: Path) -> dict[str, list[Intersection]]:
        wb = openpyxl.load_workbook(xlsx, read_only=True)
        try:
            rows = wb.worksheets[0].iter_rows(values_only=True)
            header = tuple(str(h) for h in next(rows))
            if header != XLSX_COLUMNS:
                raise ValueError(f"OA-23081 컬럼이 다르다: {header}")
            acc: dict[tuple[str, str, str], list[tuple[float, float]]] = {}
            for row in rows:
                x, y = str(row[7] or "").strip(), str(row[8] or "").strip()
                if not x or not y:
                    continue  # 좌표 없는 행 (실데이터에 있다)
                key = (str(row[6]), str(row[3]), str(row[1]))
                acc.setdefault(key, []).append((float(x), float(y)))
        finally:
            wb.close()
        out: dict[str, list[Intersection]] = {}
        for (name, iid, district), pts in acc.items():
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            lng, lat = _5186_TO_4326.transform(cx, cy)
            out.setdefault(name, []).append(Intersection(iid, name, district, lng, lat, len(pts)))
        return out

    @staticmethod
    def _load_roads(link_gpkg: Path) -> set[str]:
        con = sqlite3.connect(link_gpkg)
        try:
            rows = con.execute(
                "SELECT DISTINCT ROAD_NAME FROM link "
                "WHERE ROAD_NAME IS NOT NULL AND ROAD_NAME != ''"
            )
            return {str(r[0]) for r in rows}
        finally:
            con.close()

    @staticmethod
    def _load_aliases(path: Path | None) -> dict[str, str]:
        if path is None or not path.exists():
            return {}
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if not row.get("sentence_id"):
                raise ValueError(f"aliases.csv: 근거 sentence_id 없음 — {row}")
        return {row["alias"]: row["canonical"] for row in rows}

    # --- 조회 ---------------------------------------------------------------------
    def alias(self, name: str) -> str:
        return self._aliases.get(name, name)

    def intersection(self, canonical: str) -> PlacePoint | None:
        """교차로명 정확 일치 → 접미사(사거리·오거리…) 뗀 이름. 관리번호가 둘 이상이면 None."""
        name = self.alias(canonical)
        for key in (name, INTERSECTION_SUFFIX.sub("", name)):
            hits = self._intersections.get(key)
            if hits is None:
                hits = self._variants(key)
            if not hits:
                continue
            if len({h.intersection_id for h in hits}) != 1:
                return None  # 같은 이름의 교차로가 여럿 — 고르지 않는다
            h = hits[0]
            return PlacePoint(
                canonical=canonical,
                lng=h.lng,
                lat=h.lat,
                gazetteer_source="seoul_intersection",
                gazetteer_id=h.intersection_id,
            )
        return None

    def _variants(self, key: str) -> list[Intersection]:
        """'세종대로사거리(연등)' 같은 변형 이름들. 기본 이름이 없을 때만 본다."""
        out: list[Intersection] = []
        for name, hits in self._intersections.items():
            if name != key and VARIANT.sub("", name) == key:
                out.extend(hits)
        return out

    def road(self, canonical: str) -> tuple[str, RoadClass | None] | None:
        name = self.alias(canonical)
        if name not in self._roads:
            return None
        return name, road_class(name)

    def __len__(self) -> int:
        return len(self._intersections)

    @property
    def road_count(self) -> int:
        return len(self._roads)


def road_class(name: str) -> RoadClass | None:
    for cls in (RoadClass.daero, RoadClass.ro, RoadClass.gil):  # 대로를 로보다 먼저
        if name.endswith(cls.value):
            return cls
    return None
