"""도메인 결과 타입 — frozen dataclass. Model 은 contracts 응답 타입을 만들지 않는다 (View 몫)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from naru_be.models.domain.ped_graph import EdgeKind
from naru_contracts import Evidence, Status

LngLat = tuple[float, float]
KST = timezone(timedelta(hours=9))  # 응답 시각 표기 (CONVENTIONS §4.5). 저장은 UTC


@dataclass(frozen=True)
class RouteLeg:
    kind: EdgeKind
    name: str | None
    distance_m: float
    coord_range: tuple[int, int]  # ADR-009: Path.coords 인덱스 [i, j], 양끝 포함


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


@dataclass(frozen=True)
class RouteResult:
    """RoutePlanner.plan 결과. View 가 RouteResponse(INTERFACE §2)로 바꾼다."""

    path: Path  # 통제 반영 경로
    baseline: Path  # 같은 그래프, 통제 미적용 (avoided 는 항상 비어 있다)
    depart_at: datetime
    computed_at: datetime


@dataclass(frozen=True)
class IntakeResult:
    """CandidateIntake.accept 결과 (INTERFACE §1.1 응답). duplicate = 같은 batch_id 재전송."""

    batch_id: str
    accepted: int
    review_required: int
    crosswalks_updated: int
    duplicate: bool = False
