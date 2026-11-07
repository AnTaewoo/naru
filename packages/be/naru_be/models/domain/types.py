"""도메인 결과 타입 — frozen dataclass. Model 은 contracts 응답 타입을 만들지 않는다 (View 몫)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from naru_be.models.domain.ped_graph import EdgeKind
from naru_contracts import Evidence, Status

LngLat = tuple[float, float]


@dataclass(frozen=True)
class RouteLeg:
    kind: EdgeKind
    name: str | None
    distance_m: float


@dataclass(frozen=True)
class AvoidedCrosswalk:
    crosswalk_id: str
    status: Status  # 도착 예정 시각 기준
    reason: str
    until: datetime | None  # window.end
    evidence: tuple[Evidence, ...]
    approx: bool


@dataclass(frozen=True)
class Path:
    coords: tuple[LngLat, ...]  # WGS84, 출발점 → 도착점 (그래프 밖 접근 구간 포함)
    distance_m: float
    duration_s: float
    legs: tuple[RouteLeg, ...]
    avoided: tuple[AvoidedCrosswalk, ...]
    node_ids: tuple[str, ...]
