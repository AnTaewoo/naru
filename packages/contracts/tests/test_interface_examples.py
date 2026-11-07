"""T2.1 — docs/INTERFACE.md v0.5 의 예시와 표를 naru_contracts 코드로 고정한다.

문서의 ```json 블록을 그대로 model_validate 한다. 문서가 바뀌면(블록 수·예시·enum 표) 여기가 깨진다.
§3 `/closures` 예시는 자리표시자(`...`)가 있어 JSON이 아니다 — 2026-11-07 태우에게 보고, 검증 안 함.
§1.1 요청 예시도 candidates 가 자리표시자라 §1 후보를 끼워서 검증한다.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from naru_contracts import (
    CandidateBatch,
    CandidateBatchResponse,
    ClosureCandidate,
    ErrorBody,
    Evidence,
    EvidenceKind,
    Geometry,
    GeometryKind,
    LegKind,
    LineGeom,
    PlacePoint,
    PointGeom,
    RoadClass,
    RouteQuery,
    RouteResponse,
    SegmentGeom,
    Source,
    Status,
    Window,
    ZoneGeom,
)
from naru_contracts.enums import ClosureType
from naru_contracts.errors import ErrorCode

INTERFACE = Path(__file__).resolve().parents[3] / "docs" / "INTERFACE.md"


def _blocks() -> list[tuple[str, str]]:
    """(섹션 제목, json 원문) — 문서 순서."""
    md = INTERFACE.read_text("utf-8")
    out = []
    for m in re.finditer(r"```json\n(.*?)```", md, re.S):
        section = re.findall(r"^## (§[\d.]+)", md[: m.start()], re.M)[-1]
        out.append((section, m.group(1)))
    return out


BLOCKS = _blocks()


def _json(i: int) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(BLOCKS[i][1])
    return data


def test_document_has_six_json_blocks() -> None:
    assert [s for s, _ in BLOCKS] == ["§1", "§1", "§1", "§2", "§3", "§6"]


def test_closure_candidate_example() -> None:  # §1
    c = ClosureCandidate.model_validate(_json(0))
    assert (
        c.source is Source.smpa
        and c.type is ClosureType.march
        and c.status_hint is Status.scheduled
    )
    assert isinstance(c.geometry, SegmentGeom) and c.geometry.kind == "segment"
    assert c.geometry.from_.canonical == "KB금융지주" and len(c.geometry.via) == 1
    assert c.geometry.road is None and c.geometry.road_class is None
    assert c.window.start is not None and c.window.start.utcoffset() is not None
    assert c.evidence[0].kind is EvidenceKind.notice and c.evidence[0].detail is None
    assert c.notice_ref is not None and c.notice_ref.sentence_id == "s_000412"
    assert c.confidence == 0.72 and c.review_required is False
    assert ClosureCandidate.model_validate(c.model_dump(mode="json")) == c


def test_candidate_batch_request_example() -> None:  # §1.1 요청
    raw = _json(1)
    assert set(raw) == {"batch_id", "produced_at", "producer", "candidates"}
    assert raw["candidates"] == [{"...": "§1 ClosureCandidate"}]  # 문서의 자리표시자
    producers = [p.strip() for p in raw["producer"].split("|")]
    assert producers == ["bus_deviation", "course", "incident", "notice", "congestion"]
    batch = CandidateBatch.model_validate({**raw, "producer": "notice", "candidates": [_json(0)]})
    assert batch.batch_id == "worker-20270321-080015-bus" and len(batch.candidates) == 1
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate(raw)  # 자리표시자 그대로는 후보가 아니다


def test_candidate_batch_response_example() -> None:  # §1.1 응답
    r = CandidateBatchResponse.model_validate(_json(2))
    assert (r.accepted, r.review_required, r.crosswalks_updated) == (3, 1, 12)


def test_route_response_example() -> None:  # §2
    r = RouteResponse.model_validate(_json(3))
    assert r.duration_s == 840 and r.distance_m == 1120
    assert r.legs[0].kind is LegKind.underpass and r.legs[0].name == "시청역 지하보도"
    assert (
        r.avoided[0].status is Status.confirmed
        and r.avoided[0].evidence[0].kind is EvidenceKind.bus_skip
    )
    assert r.avoided[0].until is not None and r.avoided[0].until.utcoffset() is not None
    assert r.baseline.route.coordinates == [] and r.computed_at.utcoffset() is not None
    assert RouteResponse.model_validate(r.model_dump(mode="json")) == r


def test_error_body_example() -> None:  # §6
    e = ErrorBody.model_validate(_json(5))
    assert e.error.code == "invalid_query" and e.error.field == "depart_at"
    assert set(ErrorCode.__args__) == {
        "invalid_query",
        "unauthorized",
        "not_found",
        "no_route",
        "internal",
    }


def test_closures_example_is_not_json_yet() -> None:  # §3 — 태우 보고용 사실 고정
    section, raw = BLOCKS[4]
    assert section == "§3"
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    assert '"..."' in raw and "[ ... ]" in raw


def test_enum_table_matches_code() -> None:  # §4
    md = INTERFACE.read_text("utf-8")
    table = md[md.index("## §4 enum") : md.index("## §5")]
    rows: dict[str, list[str]] = {}
    for line in table.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows[cells[0]] = re.findall(r"`([^`]+)`", cells[1])
    expect = {
        "`status` / `status_hint`": Status,
        "`source`": Source,
        "`type`": ClosureType,
        "`geometry.kind`": GeometryKind,
        "`geometry.road_class`": RoadClass,
        "`evidence[].kind`": EvidenceKind,
        "`legs[].kind`": LegKind,
    }
    assert set(rows) == set(expect)
    for label, enum in expect.items():
        assert rows[label] == [e.value for e in enum], label


def test_extra_fields_are_rejected() -> None:
    raw = _json(0)
    with pytest.raises(ValidationError):
        ClosureCandidate.model_validate({**raw, "lng": 126.9})
    with pytest.raises(ValidationError):
        ClosureCandidate.model_validate(
            {**raw, "geometry": {**raw["geometry"], "coordinates": [1, 2]}}
        )
    with pytest.raises(ValidationError):
        PlacePoint.model_validate({**raw["geometry"]["from_"], "x": 1})


def test_review_rule_confidence_below_0_7() -> None:
    raw = _json(0)
    with pytest.raises(ValidationError, match="review_required"):
        ClosureCandidate.model_validate({**raw, "confidence": 0.69})
    ok = ClosureCandidate.model_validate({**raw, "confidence": 0.69, "review_required": True})
    assert ok.review_required is True
    assert ClosureCandidate.model_validate({**raw, "confidence": 0.7}).review_required is False


def test_geometry_four_kinds_round_trip() -> None:
    raw = _json(0)
    seg = SegmentGeom.model_validate(raw["geometry"])
    # 좌표는 INTERFACE §2·§3 예시의 값 (route LineString, closures Point)
    point = PointGeom(coordinates=(126.9769, 37.5725))
    line = LineGeom(coordinates=[(126.9751, 37.5658), (126.9769, 37.5725)])
    zone = ZoneGeom(
        zone_name="광화문·덕수궁",
        polygon=[
            [(126.9751, 37.5658), (126.9769, 37.5658), (126.9769, 37.5725), (126.9751, 37.5658)]
        ],
    )
    adapter: TypeAdapter[Any] = TypeAdapter(Geometry)
    for geom in (point, line, seg, zone):
        dumped = adapter.dump_python(geom, mode="json")
        assert dumped["kind"] == geom.kind
        assert adapter.validate_python(dumped) == geom
    assert {g.kind for g in (point, line, seg, zone)} == {k.value for k in GeometryKind}
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "polyline", "coordinates": []})
    with pytest.raises(ValidationError):
        LineGeom(coordinates=[(126.9751, 37.5658)])  # 점 하나는 선이 아니다


def test_time_needs_offset_and_window_needs_a_bound() -> None:
    with pytest.raises(ValidationError, match="오프셋"):
        Window(start=datetime(2026, 11, 7, 19, 0))
    with pytest.raises(ValidationError, match="start·end"):
        Window()
    with pytest.raises(ValidationError, match="오프셋"):
        Evidence(kind=EvidenceKind.notice, ref="x", at=datetime(2026, 11, 7))
    q = RouteQuery.model_validate(
        {
            "from": "37.5658,126.9751",
            "to": "37.5725,126.9769",
            "depart_at": "2026-11-07T15:00:00+09:00",
        }
    )
    assert q.from_ == "37.5658,126.9751" and q.mode == "walk"
    with pytest.raises(ValidationError, match="오프셋"):
        RouteQuery.model_validate({"from": "a", "to": "b", "depart_at": "2026-11-07T15:00:00"})
