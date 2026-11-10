"""행진 확률 모델 (ADR-015, T7.16) — 시간에 따라 움직이는 막힘 확률 P(t, s) 와 예상 위치 키프레임.

대상(A): type march, 창 시작·끝, 순서 있는 경로 하나 — 공지 구간 seg1..N(후보 id 끝 숫자 순)이
이어지거나(앞 끝·다음 시작 사이 march_join_m) TOPIS 통제지도 사슬 하나. 구간이 지점으로만
풀렸거나(…-segK-from|to) 갈라지면 대상이 아니다(None) — 옛 방식(창 안 고정 비용) 그대로.
프로필(B·D): 접수 때 도로 최단경로 선을 버리지 않고 길이 L, 행렬 길이 L_q(인원/(폭x밀도),
하한·L 로 자름), 횡단보도별 s(점을 선에 사영) 를 남긴다. 폭 = 지난 도로명 접미사 등급(가장
많은 것, 같으면 넓은 쪽).
모델(C): v = L/(끝-시작), 표본 v_i = v(1 + w·u_i)(u 등간격, 난수 없음), 머리 x_i(t) =
v_i(t-시작), s - 선행 ≤ x_i < s + L_q 면 그 표본에서 막힘. P = 막힌 표본/K, 창 안 하한, 창 밖 0.
라우터·키프레임 API·현장 도구가 전부 p_at 하나를 쓴다. Flask·DB 를 모른다.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property

import shapely
from pyproj import Transformer

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex, road_class_of
from naru_contracts import ClosureCandidate, ClosureType, LineGeom, SegmentGeom

LngLat = tuple[float, float]
_5179_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
BROKEN_SEGMENT = re.compile(r"-seg\d+-(from|to)$")  # 구간이 지점으로만 풀린 후보 (CandidateBuilder)
ORDER = re.compile(r"(\d+)$")  # …-seg{k} · topismap-{acc}-{k}
WIDTH_ORDER = ("대로", "로", "길")  # 같은 수면 넓은 쪽


@dataclass(frozen=True)
class MarchPart:
    """후보 하나의 경로 선 (접수 때, EPSG:5179) — 구간·선 후보만."""

    candidate_id: str
    line: shapely.LineString
    crosswalk_ids: frozenset[str]
    roads: tuple[str, ...]  # 지난 도로명 (구간은 도로 그래프, 선은 후보 summary.roads)
    road_class: str | None  # 구간 후보의 road_class


@dataclass(frozen=True)
class MarchProfile:
    """사건 행 JSON `march` (B) — 경로(EPSG:4326)·길이·행렬 길이·폭·횡단보도별 s."""

    path: tuple[LngLat, ...]
    length_m: float
    queue_m: float
    width_m: float
    s: dict[str, float]

    @cached_property
    def line(self) -> shapely.LineString:
        return shapely.LineString([_4326_TO_5179.transform(lng, lat) for lng, lat in self.path])

    def to_json(self) -> dict[str, object]:
        return {
            "path": [list(p) for p in self.path],
            "length_m": self.length_m,
            "queue_m": self.queue_m,
            "width_m": self.width_m,
            "s": self.s,
        }

    @classmethod
    def from_json(cls, raw: Mapping[str, object]) -> MarchProfile:
        path = raw["path"]
        s = raw["s"]
        assert isinstance(path, list) and isinstance(s, dict)
        return cls(
            path=tuple((float(p[0]), float(p[1])) for p in path),
            length_m=float(str(raw["length_m"])),
            queue_m=float(str(raw["queue_m"])),
            width_m=float(str(raw["width_m"])),
            s={str(k): float(str(v)) for k, v in s.items()},
        )


@dataclass(frozen=True)
class Keyframe:
    t: datetime
    samples: tuple[tuple[LngLat, ...], ...]  # 표본별 머리~꼬리 점
    center: LngLat
    radius_m: float
    crosswalks: dict[str, float]  # 횡단보도 id → P


def march_part(index: CrosswalkIndex, c: ClosureCandidate) -> MarchPart | None:
    """구간·선 후보 → 경로 선. 지점·구역 후보는 None (CandidateIntake 는 같은 계산을 한 번만)."""
    g = c.geometry
    if isinstance(g, SegmentGeom):
        line, path = index.line_of_segment(g)
        ids = index.within(line.buffer(index.buffer_of_segment(g)))
        cls = g.road_class or road_class_of(g.road)
        road_class = cls.value if cls else None
        return MarchPart(c.candidate_id, line, frozenset(ids), path.roads, road_class)
    if isinstance(g, LineGeom):
        line = index.line_of(g.coordinates)
        ids = index.within(line.buffer(index.settings.line_buffer_m))
        roads = tuple(c.summary.roads) if c.summary else ()
        return MarchPart(c.candidate_id, line, frozenset(ids), roads, None)
    return None


def _order(part: MarchPart) -> tuple[int, str]:
    found = ORDER.search(part.candidate_id)
    return (int(found.group(1)) if found else 0, part.candidate_id)


def _width_m(parts: Sequence[MarchPart], settings: Settings) -> float:
    """폭 — 구간 road_class 가 있으면 그것, 없으면 지난 도로명 등급 중 가장 많은 것(같으면
    넓은 쪽), 없으면 '로'."""
    classes = [p.road_class for p in parts if p.road_class]
    if not classes:
        for p in parts:
            classes.extend(cls.value for road in p.roads if (cls := road_class_of(road)))
    counts = Counter(classes)
    best = "로"
    if counts:
        best = max(WIDTH_ORDER, key=lambda k: (counts.get(k, 0), -WIDTH_ORDER.index(k)))
    return settings.march_width_m[best]


def march_profile(
    candidates: Sequence[ClosureCandidate],
    parts: Mapping[str, MarchPart],
    index: CrosswalkIndex,
    settings: Settings,
) -> MarchProfile | None:
    """한 사건의 후보들 → 프로필. 대상(A)이 아니면 None."""
    if not candidates or not parts:
        return None
    for c in candidates:
        if c.type is not ClosureType.march or c.window.start is None or c.window.end is None:
            return None
        if BROKEN_SEGMENT.search(c.candidate_id):
            return None
    ordered = sorted(parts.values(), key=_order)
    coords: list[tuple[float, float]] = [(x, y) for x, y in ordered[0].line.coords]
    for nxt in ordered[1:]:
        pts = [(x, y) for x, y in nxt.line.coords]
        if shapely.Point(coords[-1]).distance(shapely.Point(pts[0])) > settings.march_join_m:
            return None  # 갈라지거나 끊긴 경로
        coords.extend(pts[1:] if pts[0] == coords[-1] else pts)
    line = shapely.LineString(coords)
    length = float(line.length)
    width = _width_m(ordered, settings)
    people = next(
        (c.summary.reported_people for c in candidates if c.summary and c.summary.reported_people),
        None,
    )
    queue = settings.march_queue_m if people is None else people / (width * settings.march_density)
    queue = min(max(queue, settings.march_queue_min_m), length)
    s: dict[str, float] = {}
    for part in ordered:
        for cid in sorted(part.crosswalk_ids):
            cw = index.find(cid)
            if cw is not None and cid not in s:
                s[cid] = round(float(line.project(shapely.Point(cw.x, cw.y))), 1)
    path = tuple(
        (round(lng, 6), round(lat, 6))
        for lng, lat in (_5179_TO_4326.transform(x, y) for x, y in coords)
    )
    return MarchProfile(path, round(length, 1), round(queue, 1), width, s)
