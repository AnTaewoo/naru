"""IntersectionMap — 교차로명 → 교차로관리번호 → 횡단보도관리번호 집합 (ROADMAP T1.3).

OA-23081(T0.2)에서 교차로명과 교차로관리번호는 서울 전체에서 1:1 이다
(2026-11-07 확인: 7,592 교차로명, 관리번호 2개 이상인 이름 0). 종로·중구는 409 교차로,
교차로당 횡단보도 1~9개. **정확 일치만** 한다 —
'세종대로'로 '세종대로사거리'를 찾지 않는다. 별칭·부분 일치는 AI 리졸버(T4.2) 몫이고, 리졸버는 같은
xlsx를 읽는다 (데이터 공유, 코드 각자).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import Crosswalk, CrosswalkIndex


@dataclass(frozen=True)
class Intersection:
    intersection_id: str  # 교차로관리번호
    name: str  # 교차로명
    district: str
    crosswalk_ids: tuple[str, ...]  # 횡단보도관리번호, 정렬
    lng: float  # 횡단보도 점들의 평균 (WGS84)
    lat: float


class IntersectionMap:
    def __init__(self, intersections: Iterable[Intersection]) -> None:
        self._by_name: dict[str, Intersection] = {}
        self._by_id: dict[str, Intersection] = {}
        for it in intersections:
            if it.name in self._by_name or it.intersection_id in self._by_id:
                raise ValueError(f"교차로명·관리번호가 겹친다: {it.name} / {it.intersection_id}")
            self._by_name[it.name] = it
            self._by_id[it.intersection_id] = it

    @classmethod
    def from_crosswalks(cls, crosswalks: Iterable[Crosswalk]) -> IntersectionMap:
        groups: dict[str, list[Crosswalk]] = {}
        for c in crosswalks:
            groups.setdefault(c.intersection_id, []).append(c)
        items: list[Intersection] = []
        for intersection_id, group in groups.items():
            names = {c.intersection_name for c in group}
            if len(names) != 1:
                raise ValueError(f"교차로관리번호 {intersection_id}에 교차로명이 여럿: {names}")
            items.append(
                Intersection(
                    intersection_id=intersection_id,
                    name=group[0].intersection_name,
                    district=group[0].district,
                    crosswalk_ids=tuple(sorted(c.crosswalk_id for c in group)),
                    lng=sum(c.lng for c in group) / len(group),
                    lat=sum(c.lat for c in group) / len(group),
                )
            )
        return cls(items)

    @classmethod
    def from_xlsx(cls, xlsx: Path, settings: Settings | None = None) -> IntersectionMap:
        return cls.from_crosswalks(CrosswalkIndex.from_xlsx(xlsx, settings).crosswalks)

    def __len__(self) -> int:
        return len(self._by_id)

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def by_name(self, name: str) -> Intersection | None:
        """정확 일치만. 공백·괄호 변형도 다른 이름이다."""
        return self._by_name.get(name)

    def by_id(self, intersection_id: str) -> Intersection | None:
        return self._by_id.get(intersection_id)

    def crosswalks_of(self, name: str) -> set[str]:
        it = self._by_name.get(name)
        return set(it.crosswalk_ids) if it else set()
