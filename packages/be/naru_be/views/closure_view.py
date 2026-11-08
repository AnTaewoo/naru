"""closure_view — list[ClosureState] → GeoJSON FeatureCollection(INTERFACE §3) → JSON.

횡단보도 하나 = Point Feature. 예정-구역 Polygon Feature 는 ZoneMatcher(v1, AI 레인)가 폴리곤을
주기 전까지 만들지 않는다 (T3.3 보고). DB 를 모른다.
"""

from __future__ import annotations

from collections.abc import Sequence

from flask import Response, jsonify

from naru_be.views._time import evidence_kst, kst
from naru_contracts import (
    ClosureEvent,
    ClosureEventsResponse,
    ClosureState,
    DataAsOf,
    FeatureCollection,
)
from naru_contracts.closures_api import Feature, FeatureProperties, PointGeometry


def render(states: Sequence[ClosureState]) -> Response:
    return jsonify(to_collection(states).model_dump(mode="json"))


def render_events(
    events: Sequence[ClosureEvent],
    coverage: tuple[float, float, float, float],
    data_as_of: DataAsOf,
) -> Response:
    """통제 사건 + 보행망 bbox + 출처별 기준 시각 (INTERFACE §3.1 v0.12). 계약이 검증한다."""
    body = ClosureEventsResponse(events=list(events), coverage=coverage, data_as_of=data_as_of)
    return jsonify(body.model_dump(mode="json"))


def to_collection(states: Sequence[ClosureState]) -> FeatureCollection:
    return FeatureCollection(features=[_feature(s) for s in states])


def _feature(s: ClosureState) -> Feature:
    return Feature(
        geometry=PointGeometry(coordinates=(s.lng, s.lat)),
        properties=FeatureProperties(
            crosswalk_id=s.crosswalk_id,
            status=s.status,
            confidence=s.confidence,
            impact=s.impact,
            approx=s.approx,
            window={"start": kst(s.window.start), "end": kst(s.window.end)},
            reason=s.reason,
            evidence=[ev.model_dump(mode="json") for ev in evidence_kst(s.evidence)],
        ),
    )
