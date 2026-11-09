"""T2.1 — docs/INTERFACE.md v0.6 의 예시와 표를 naru_contracts 코드로 고정한다 (ADR-008 반영).

문서의 ```json 블록을 그대로 model_validate 한다. 문서가 바뀌면(블록 수·예시·enum 표) 여기가 깨진다.
§3 `/closures` 예시는 자리표시자(`...`)가 있어 JSON이 아니다 — 2026-11-07 태우에게 보고, 검증 안 함.
§1.1 요청 예시도 candidates 가 자리표시자라 §1 후보를 끼워서 검증한다.
§3.1 `/closures/events` 예시(v0.8, ADR-010)는 2026-11-08 개발 DB 의 실제 사건 두 개
(bbox 는 소수 4자리). §7 지오코딩 예시(v0.11, ADR-011 B)는 2026-11-08 카카오 로컬 기록
(recorded kakao/local, MANIFEST) 에서 BE 가 만드는 응답.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from naru_contracts import (
    BusPositionBatch,
    BusPositionBatchResponse,
    CandidateBatch,
    CandidateBatchResponse,
    ClosureCandidate,
    ClosureEventsQuery,
    ClosureEventsResponse,
    ErrorBody,
    Evidence,
    EvidenceKind,
    GeocodeReverseQuery,
    GeocodeReverseResponse,
    GeocodeSearchQuery,
    GeocodeSearchResponse,
    Geometry,
    GeometryKind,
    Impact,
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


def test_document_has_eleven_json_blocks() -> None:
    # §1.1·§1.2·§3.1·§7.1·§7.2 는 ### 소제목이라 상위 § 로 잡힌다
    assert [s for s, _ in BLOCKS] == [
        *("§1", "§1", "§1", "§1", "§1"),
        *("§2", "§3", "§3", "§6", "§7", "§7"),
    ]


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
    # v0.12 summary — 구조화 칸만 (ADR-012)
    assert c.summary is not None
    seg = c.summary.segments[0]
    assert (seg.from_, seg.to, seg.via) == ("KB금융지주", "KB증권", ["여의도역"])
    assert c.summary.points == [] and c.summary.reported_people is None and c.summary.roads == []
    assert c.impact is Impact.blocks and c.toward is None and c.approx is False  # v0.6
    assert ClosureCandidate.model_validate(c.model_dump(mode="json")) == c


def test_candidate_batch_request_example() -> None:  # §1.1 요청
    raw = _json(1)
    assert set(raw) == {"batch_id", "produced_at", "producer", "candidates"}
    assert raw["candidates"] == [{"...": "§1 ClosureCandidate"}]  # 문서의 자리표시자
    producers = [p.strip() for p in raw["producer"].split("|")]
    assert producers == ["course", "incident", "notice", "congestion"]  # 버스는 §1.2 (ADR-013)
    batch = CandidateBatch.model_validate({**raw, "producer": "notice", "candidates": [_json(0)]})
    assert batch.batch_id == "worker-20270321-080015-bus" and len(batch.candidates) == 1
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate(raw)  # 자리표시자 그대로는 후보가 아니다


def test_candidate_batch_response_example() -> None:  # §1.1 응답
    r = CandidateBatchResponse.model_validate(_json(2))
    assert (r.accepted, r.review_required, r.crosswalks_updated) == (3, 1, 12)


def test_bus_position_batch_example() -> None:  # §1.2 요청 (v0.13, ADR-013 D)
    # 2026-11-08 18:38 실제 기록 recorded/bus/20261108T183832_getBusPosByRtid_100100001.json 첫 차량
    b = BusPositionBatch.model_validate(_json(3))
    assert (b.route_id, b.batch_id) == ("100100001", "bus-100100001-67062dc1ad5c")
    (p,) = b.positions
    assert (p.veh_id, p.sect_ord, p.stop_flag, p.is_run) == ("106024536", 3, False, True)
    assert p.data_tm.utcoffset() == timedelta(hours=9)
    assert (p.lng, p.lat, p.sect_dist) == (126.998005, 37.562053, 0.327)
    assert BusPositionBatch.model_validate(b.model_dump(mode="json")) == b


def test_bus_position_batch_response_example() -> None:  # §1.2 응답
    r = BusPositionBatchResponse.model_validate(_json(4))
    assert (r.batch_id, r.accepted) == ("bus-100100001-67062dc1ad5c", 1)


def test_route_response_example() -> None:  # §2
    r = RouteResponse.model_validate(_json(5))
    assert r.duration_s == 840 and r.distance_m == 1120
    assert [leg.kind for leg in r.legs] == [LegKind.sidewalk, LegKind.underpass, LegKind.sidewalk]
    assert r.legs[1].name == "시청역 지하보도" and r.legs[1].coord_range == (1, 2)
    assert (
        r.avoided[0].status is Status.confirmed
        and r.avoided[0].evidence[0].kind is EvidenceKind.topis_incident
    )
    assert r.avoided[0].until is not None and r.avoided[0].until.utcoffset() is not None
    assert r.baseline.route.coordinates == [] and r.computed_at.utcoffset() is not None
    assert RouteResponse.model_validate(r.model_dump(mode="json")) == r


def test_error_body_example() -> None:  # §6
    e = ErrorBody.model_validate(_json(8))
    assert e.error.code == "invalid_query" and e.error.field == "depart_at"
    assert set(ErrorCode.__args__) == {
        "invalid_query",
        "unauthorized",
        "not_found",
        "no_route",
        "out_of_coverage",  # v0.9, ADR-011 그래프 밖 — 그래프에 붙일 거리 150 m 초과
        "geocode_unavailable",  # v0.11, ADR-011 B — 카카오 로컬을 못 불렀다 (503)
        "internal",
    }


def test_closures_example_is_not_json_yet() -> None:  # §3 — 태우 보고용 사실 고정
    section, raw = BLOCKS[6]
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
        "`impact`": Impact,
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


def test_adr_008_impact_toward_approx() -> None:
    raw = _json(0)
    with pytest.raises(ValidationError, match="impact"):
        ClosureCandidate.model_validate({k: v for k, v in raw.items() if k != "impact"})  # 필수
    with pytest.raises(ValidationError, match="ADR-008"):
        ClosureCandidate.model_validate({**raw, "impact": "unknown"})  # 0.72 > 0.65
    unknown = {**raw, "impact": "unknown", "confidence": 0.45, "review_required": True}
    assert ClosureCandidate.model_validate(unknown).impact is Impact.unknown
    with pytest.raises(ValidationError):
        ClosureCandidate.model_validate({**raw, "impact": "none"})  # none 은 BE로 오지 않는다
    line = {"kind": "line", "coordinates": [[126.9751, 37.5658], [126.9769, 37.5725]]}
    with pytest.raises(ValidationError, match="toward"):
        ClosureCandidate.model_validate({**raw, "geometry": line, "toward": "을지로입구역"})
    seg = ClosureCandidate.model_validate({**raw, "toward": "을지로입구역", "approx": True})
    assert seg.toward == "을지로입구역" and seg.approx is True
    assert RouteResponse.model_validate(_json(5)).avoided[0].approx is False


def test_route_legs_must_partition_route() -> None:  # §2 v0.7, ADR-009
    raw = _json(5)
    RouteResponse.model_validate(raw)

    def broken(**leg_changes: object) -> dict[str, object]:
        legs = [dict(leg) for leg in raw["legs"]]
        for k, v in leg_changes.items():
            idx, field = k.split("_", 1)
            legs[int(idx[1:])][field] = v
        return {**raw, "legs": legs}

    with pytest.raises(ValidationError, match="시작해야"):  # 빈틈: 1 → 2 사이가 비었다
        RouteResponse.model_validate(broken(l1_coord_range=[2, 2]))
    with pytest.raises(ValidationError, match="끝"):  # 마지막 레그가 끝까지 안 간다
        RouteResponse.model_validate(broken(l2_coord_range=[2, 2]))
    with pytest.raises(ValidationError, match="밖"):  # 범위 밖
        RouteResponse.model_validate(broken(l2_coord_range=[2, 9]))
    with pytest.raises(ValidationError, match="밖"):  # i > j
        RouteResponse.model_validate(broken(l1_coord_range=[2, 1]))
    with pytest.raises(ValidationError, match="distance_m"):  # 합이 총거리와 다르다
        RouteResponse.model_validate(broken(l0_distance_m=10))
    with pytest.raises(ValidationError):  # 필수
        RouteResponse.model_validate({**raw, "legs": [{"kind": "sidewalk", "distance_m": 1120}]})
    # 레그가 없으면 규칙 없음 (출발·도착이 같은 노드)
    assert RouteResponse.model_validate({**raw, "legs": []}).legs == []


def test_closure_events_example() -> None:  # §3.1 v0.8, ADR-010
    r = ClosureEventsResponse.model_validate(_json(7))
    assert [e.crosswalks for e in r.events] == [31, 6]
    rally, seg1 = r.events
    assert rally.reason.startswith("15:00~16:00 시의회~숭례문R")
    assert seg1.reason == "marathon 1구간 세종대로 사거리~숭례문 오거리"
    assert seg1.window.start is not None and seg1.window.start.utcoffset() is not None
    assert seg1.window.start.isoformat() == "2026-03-15T07:20:00+09:00"
    assert seg1.bbox == (126.9757, 37.5608, 126.9772, 37.5701) and seg1.approx is False
    # v0.10 — 보행망 bbox (2026-11-08 종로·중구 그래프 노드 15,183개의 경위도 범위)
    assert r.coverage == (126.948108, 37.54265, 127.026684, 37.631483)
    # v0.12 (ADR-012) — 공지 사건: 종류·출처·파서 요약(recorded LLM smpa-20261107-r04)·공지 원문
    assert (rally.type, rally.source) == (ClosureType.march, Source.smpa)
    assert rally.summary is not None and rally.summary.reported_people == 50000
    assert [(x.from_, x.to) for x in rally.summary.segments] == [
        ("시의회", "숭례문오거리"),
        ("숭례문오거리", "광화문"),
        ("숭례문오거리", "고용노동청"),
    ]
    assert rally.summary.roads == ["태평로"]
    assert rally.notice is not None and rally.notice.sentence_id == "smpa-20261107-r04"
    assert rally.notice.excerpt == rally.reason
    assert (seg1.type, seg1.source, seg1.summary, seg1.notice) == (
        ClosureType.marathon,
        Source.course,
        None,
        None,
    )
    # data_as_of — 2026-11-08 개발 DB: 서울경찰청 11/6 18:00 공지, 서울마라톤 3/12 16:07 시각표
    kst = timezone(timedelta(hours=9))
    assert r.data_as_of.smpa == datetime(2026, 11, 6, 18, 0, tzinfo=kst)
    assert r.data_as_of.course == datetime(2026, 3, 12, 16, 7, tzinfo=kst)
    assert r.data_as_of.topis_incident is None and r.data_as_of.topis_notice is None
    assert ClosureEventsResponse.model_validate(r.model_dump(mode="json")) == r


def test_closure_events_rules() -> None:  # §3.1 — 순서·bbox·개수, 질의 bbox 는 선택
    data = _json(7)
    cov = data["coverage"]
    asof = data["data_as_of"]
    swapped = {
        "events": [data["events"][1], data["events"][0]],
        "coverage": cov,
        "data_as_of": asof,
    }
    with pytest.raises(ValidationError, match="늦은 것 먼저"):
        ClosureEventsResponse.model_validate(swapped)
    no_start = {**data["events"][1], "window": {"end": data["events"][1]["window"]["end"]}}
    ClosureEventsResponse.model_validate(
        {"events": [data["events"][0], no_start], "coverage": cov, "data_as_of": asof}
    )  # start 없으면 끝
    with pytest.raises(ValidationError, match="늦은 것 먼저"):
        ClosureEventsResponse.model_validate(
            {"events": [no_start, data["events"][0]], "coverage": cov, "data_as_of": asof}
        )
    bad_bbox = {**data["events"][1], "bbox": [126.9772, 37.5608, 126.9757, 37.5701]}
    with pytest.raises(ValidationError, match="bbox"):
        ClosureEventsResponse.model_validate(
            {"events": [bad_bbox], "coverage": cov, "data_as_of": asof}
        )
    with pytest.raises(ValidationError):
        ClosureEventsResponse.model_validate(
            {
                "events": [{**data["events"][1], "crosswalks": 0}],
                "coverage": cov,
                "data_as_of": asof,
            }
        )
    with pytest.raises(ValidationError):
        ClosureEventsResponse.model_validate(
            {"events": [{**data["events"][1], "status": "confirmed"}]}
        )
    with pytest.raises(ValidationError):  # coverage 필수 (v0.10)
        ClosureEventsResponse.model_validate({"events": [], "data_as_of": asof})
    with pytest.raises(ValidationError):  # data_as_of 필수 (v0.12)
        ClosureEventsResponse.model_validate({"events": [], "coverage": cov})
    with pytest.raises(ValidationError, match="오프셋"):  # 시각은 오프셋 필수
        ClosureEventsResponse.model_validate(
            {"events": [], "coverage": cov, "data_as_of": {**asof, "smpa": "2026-11-06T18:00:00"}}
        )
    # v0.12 전에 저장된 상태라 type·source·summary·notice 를 모르면 null 그대로
    legacy = {k: v for k, v in data["events"][1].items() if k not in ("type", "source")}
    old = ClosureEventsResponse.model_validate(
        {"events": [legacy], "coverage": cov, "data_as_of": asof}
    )
    assert old.events[0].type is None and old.events[0].source is None
    with pytest.raises(ValidationError, match="coverage"):
        ClosureEventsResponse.model_validate(
            {"events": [], "coverage": [127.0, 37.6, 126.9, 37.5], "data_as_of": asof}
        )
    assert ClosureEventsQuery().bbox is None
    assert ClosureEventsQuery.model_validate({"bbox": "126.965,37.555,126.990,37.580"}).bbox


def test_geocode_examples() -> None:  # §7 v0.11, ADR-011 B
    found = GeocodeSearchResponse.model_validate(_json(9))
    kyobo, foundation = found.places
    # 카카오 기록(q=교보빌딩, near 126.98,37.57, 반경 5 km 정확도 순)의 1·2위
    assert (kyobo.id, kyobo.name, kyobo.address) == (
        "24020019",
        "광화문교보빌딩",
        "서울 종로구 종로 1",
    )
    assert kyobo.coord == (126.9779039768265, 37.5709686446227)  # = route_0745 출발점
    assert foundation.name == "교보재단빌딩"
    assert GeocodeSearchResponse.model_validate(found.model_dump(mode="json")) == found
    rev = GeocodeReverseResponse.model_validate(_json(10))
    assert rev.label == "종로구 종로 1" and rev.road_address == "서울특별시 종로구 종로 1"
    assert rev.address == "서울 종로구 종로1가 1"


def test_geocode_rules() -> None:  # §7 — 검색어 2~50자(앞뒤 공백 뺌), near 선택, 결과 10개까지
    assert GeocodeSearchQuery.model_validate({"q": "  시청 "}).q == "시청"
    assert GeocodeSearchQuery.model_validate({"q": "시청"}).near is None
    for bad in ("시", "   시  ", "가" * 51):
        with pytest.raises(ValidationError):
            GeocodeSearchQuery.model_validate({"q": bad})
    place = _json(9)["places"][0]
    with pytest.raises(ValidationError):
        GeocodeSearchResponse.model_validate({"places": [place] * 11})
    with pytest.raises(ValidationError):
        GeocodeSearchResponse.model_validate({"places": [{**place, "coord": [126.97]}]})
    q = GeocodeReverseQuery.model_validate({"lat": "37.5709686446227", "lng": "126.9779039768265"})
    assert (q.lat, q.lng) == (37.5709686446227, 126.9779039768265)
    for lat, lng in (("91", "126.97"), ("37.57", "181"), ("nan", "126.97"), ("37.57", "")):
        with pytest.raises(ValidationError):
            GeocodeReverseQuery.model_validate({"lat": lat, "lng": lng})
    # 주소가 없는 점은 셋 다 null, label 은 주소에서만 나온다
    assert GeocodeReverseResponse(label=None, road_address=None, address=None).label is None
    with pytest.raises(ValidationError, match="label"):
        GeocodeReverseResponse(label="중구", road_address=None, address=None)
    with pytest.raises(ValidationError, match="label"):
        GeocodeReverseResponse(label=None, road_address=None, address="서울 중구 남대문로2가 9-9")


def test_candidate_summary_rules() -> None:  # §1 v0.12 — 구조화 칸만, 문장 칸 없음
    c = _json(0)
    assert (
        ClosureCandidate.model_validate({k: v for k, v in c.items() if k != "summary"}).summary
        is None
    )
    with pytest.raises(ValidationError):  # 인원은 0 이상 숫자
        ClosureCandidate.model_validate({**c, "summary": {**c["summary"], "reported_people": -1}})
    with pytest.raises(ValidationError):  # 문장 칸(title 등)은 없다
        ClosureCandidate.model_validate({**c, "summary": {**c["summary"], "title": "행진"}})
