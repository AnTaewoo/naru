"""naru_contracts — docs/INTERFACE.md v0.5의 유일한 코드 구현 (pydantic v2).

AI(naru_ai)와 BE(naru_be)는 서로를 import하지 않고 이 패키지만 import한다.
FE 타입은 `make schema`로 여기서 생성한다. 문서와 코드가 다르면 테스트가 깨진다(T2.1).
"""

from naru_contracts.closure import (
    CandidateBatch,
    CandidateBatchResponse,
    ClosureCandidate,
    ClosureState,
    Evidence,
    Geometry,
    LineGeom,
    NoticeRef,
    PlacePoint,
    PointGeom,
    SegmentGeom,
    Window,
    ZoneGeom,
)
from naru_contracts.closures_api import (
    ClosureEvent,
    ClosureEventsQuery,
    ClosureEventsResponse,
    ClosuresQuery,
    FeatureCollection,
)
from naru_contracts.enums import (
    ClosureType,
    EvidenceKind,
    GeometryKind,
    Impact,
    LegKind,
    RoadClass,
    Source,
    Status,
)
from naru_contracts.errors import ErrorBody
from naru_contracts.route import Avoided, Baseline, Leg, RouteQuery, RouteResponse

__all__ = [
    "Avoided",
    "Baseline",
    "CandidateBatch",
    "CandidateBatchResponse",
    "ClosureCandidate",
    "ClosureEvent",
    "ClosureEventsQuery",
    "ClosureEventsResponse",
    "ClosureState",
    "ClosureType",
    "ClosuresQuery",
    "ErrorBody",
    "Evidence",
    "EvidenceKind",
    "FeatureCollection",
    "Geometry",
    "GeometryKind",
    "Impact",
    "Leg",
    "LegKind",
    "LineGeom",
    "NoticeRef",
    "PlacePoint",
    "PointGeom",
    "RoadClass",
    "RouteQuery",
    "RouteResponse",
    "SegmentGeom",
    "Source",
    "Status",
    "Window",
    "ZoneGeom",
]
