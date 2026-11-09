"""T2.3 — ClosureEngine: 기록된 코스 후보(T2.2) → 횡단보도 상태, 시각에 따른 전이 (실데이터).

입력은 recorded/candidates/course/<최신>.json. naru_ai 는 import 하지 않는다 (스킬 §4.2).
기대값은 2026-11-07 기록·시각표를 열어 확인한 값.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_contracts import (
    CandidateBatch,
    ClosureCandidate,
    Evidence,
    EvidenceKind,
    Impact,
    LineGeom,
    Status,
    Window,
)

KST = timedelta(hours=9)


@pytest.fixture(scope="module")
def index(seoul_spatial_dir: Path) -> CrosswalkIndex:
    return CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", Settings())


@pytest.fixture(scope="module")
def engine(index: CrosswalkIndex) -> ClosureEngine:
    return ClosureEngine(index, Settings())


@pytest.fixture(scope="module")
def course_batch(recorded_dir: Path) -> CandidateBatch:
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    assert files, "기록 없음: make record-candidates SOURCE=course 먼저"
    return CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))


def _seg(batch: CandidateBatch, seq: int) -> ClosureCandidate:
    return next(c for c in batch.candidates if c.candidate_id == f"course-20260315-seg{seq:02d}")


def test_course_candidates_become_scheduled_then_confirmed_then_released(
    engine: ClosureEngine, index: CrosswalkIndex, course_batch: CandidateBatch
) -> None:
    assert len(course_batch.candidates) == 16
    seg1 = _seg(course_batch, 1)  # 1구간 세종대로 사거리~숭례문 오거리 07:20~08:08
    assert isinstance(seg1.geometry, LineGeom)
    ids = index.from_line(seg1.geometry.coordinates)  # 버퍼 15 m
    # 15 m 버퍼 안 6개, 세종대로사거리 06-0000023206 포함 (2026-11-07). 029520은 중심선에서 15 m 밖
    assert len(ids) == 6 and "06-0000023206" in ids
    assert any(index.get(i).intersection_name == "세종대로사거리" for i in ids)
    start, end = seg1.window.start, seg1.window.end
    assert start == datetime(2026, 3, 15, 7, 20, tzinfo=start.tzinfo) and end is not None

    before = engine.apply(seg1, ids, at=start - timedelta(minutes=1))
    assert {s.status for s in before} == {Status.scheduled} and len(before) == len(ids)
    assert all(s.confidence == 0.9 and s.window == seg1.window for s in before)
    assert all(
        len(s.evidence) == 1 and s.evidence[0].kind is EvidenceKind.timetable for s in before
    )
    assert all(s.reason == "marathon 1구간 세종대로 사거리~숭례문 오거리" for s in before)
    sejong = next(s for s in before if s.crosswalk_id == "06-0000023206")
    c = index.get("06-0000023206")
    assert (sejong.lng, sejong.lat) == (c.lng, c.lat)

    during = engine.apply(
        seg1, ids, at=start + timedelta(minutes=1)
    )  # 시각표 시작 경과 → confirmed
    assert {s.status for s in during} == {Status.confirmed}
    assert all(
        len(s.evidence) == 2
        and s.evidence[1].detail == {"transition": "scheduled→confirmed", "rule": "window_start"}
        for s in during
    )
    assert all(s.evidence[1].at == start for s in during)

    still = engine.apply(seg1, ids, at=end + timedelta(minutes=29))  # 종료 + 30분 전까지 confirmed
    assert {s.status for s in still} == {Status.confirmed}

    after = engine.apply(seg1, ids, at=end + timedelta(minutes=31))  # 종료 + 30분 → released
    assert {s.status for s in after} == {Status.released}
    assert all(
        s.evidence[-1].detail == {"transition": "confirmed→released", "rule": "window_end+grace"}
        for s in after
    )
    assert all(s.evidence[-1].at == end for s in after)


def test_every_course_segment_has_crosswalks_and_consistent_states(
    engine: ClosureEngine, index: CrosswalkIndex, course_batch: CandidateBatch
) -> None:
    # 종로·중구 인덱스라 송파 구간(10~15)은 횡단보도가 없을 수 있다. 도심(출발지~4구간)은 있다
    counts = {}
    for c in course_batch.candidates:
        assert isinstance(c.geometry, LineGeom)
        ids = index.from_line(c.geometry.coordinates)
        counts[c.candidate_id] = len(ids)
        start = c.window.start
        assert start is not None
        states = engine.apply(
            c, ids, at=datetime(2026, 3, 15, 4, 0, tzinfo=start.tzinfo)
        )  # 첫 통제 05:00 전
        assert len(states) == len(ids) and all(s.status is Status.scheduled for s in states)
    for seq in range(0, 5):
        assert counts[f"course-20260315-seg{seq:02d}"] > 0
    assert sum(counts.values()) > 100


def test_notice_only_candidate_is_not_confirmed_by_time(
    engine: ClosureEngine, course_batch: CandidateBatch
) -> None:
    # 공지(notice) 증거뿐인 후보는 시작 시각이 지나도 scheduled. 실측이 와야 confirmed
    seg1 = _seg(course_batch, 1)
    notice_only = seg1.model_copy(
        update={
            "evidence": [
                Evidence(kind=EvidenceKind.notice, ref="smpa-20260315", at=seg1.evidence[0].at)
            ],
            "confidence": 0.75,
        }
    )
    start = seg1.window.start
    assert start is not None
    states = engine.apply(notice_only, ["06-0000029520"], at=start + timedelta(minutes=10))
    assert [s.status for s in states] == [Status.scheduled]
    end = seg1.window.end
    assert end is not None
    released = engine.apply(notice_only, ["06-0000029520"], at=end + timedelta(minutes=31))
    assert released[0].status is Status.released
    assert released[0].evidence[-1].detail == {
        "transition": "scheduled→released",
        "rule": "window_end+grace",
    }


def test_unknown_end_uses_six_hours(engine: ClosureEngine, course_batch: CandidateBatch) -> None:
    seg1 = _seg(course_batch, 1)
    start = seg1.window.start
    assert start is not None
    open_ended = seg1.model_copy(update={"window": Window(start=start, end=None)})
    states = engine.apply(open_ended, ["06-0000029520"], at=start + timedelta(hours=6, minutes=31))
    assert states[0].window.end == start + timedelta(hours=6)
    assert states[0].status is Status.released
    assert states[0].evidence[1].detail == {
        "rule": "unknown_end",
        "end": (start + timedelta(hours=6)).isoformat(),
    }
    assert (
        engine.apply(open_ended, ["06-0000029520"], at=start + timedelta(hours=6, minutes=29))[
            0
        ].status
        is Status.confirmed
    )


def test_bus_evidence_changes_no_status(
    engine: ClosureEngine, course_batch: CandidateBatch
) -> None:
    # ADR-013 보류(태우 2026-11-09): 통제 중 근거는 시간표·TOPIS 돌발 둘만. 버스 근거만 있는 후보는
    # 시작이 지나도 예정, 시간표 통제에 버스 복귀가 붙어도 창 안이면 통제 중 그대로
    seg1 = _seg(course_batch, 1)
    start = seg1.window.start
    assert start is not None
    record = "data/recorded/bus/20261107T155630_getBusPosByRtid.json"
    skip = Evidence(kind=EvidenceKind.bus_skip, ref=record, at=start)
    only_bus = seg1.model_copy(update={"evidence": [skip]})
    after = start + timedelta(minutes=1)
    assert engine.apply(only_bus, ["06-0000029520"], at=after)[0].status is Status.scheduled
    state = engine.apply(seg1, ["06-0000029520"], at=after)[0]
    back = Evidence(kind=EvidenceKind.bus_return, ref=record, at=start + timedelta(minutes=40))
    with_back = state.model_copy(
        update={"status": Status.released, "evidence": [*state.evidence, back]}
    )
    assert engine.status_of_state(with_back, back.at) is Status.confirmed  # 1구간 07:20~08:08


def test_rtd_spike_bumps_confidence(engine: ClosureEngine, course_batch: CandidateBatch) -> None:
    seg1 = _seg(course_batch, 1)
    start = seg1.window.start
    assert start is not None
    spike = Evidence(
        kind=EvidenceKind.rtd_spike, ref="data/recorded/rtd/20261107T154125_citydata.json", at=start
    )
    scheduled = engine.apply(
        seg1.model_copy(update={"confidence": 0.65, "review_required": True}),
        ["06-0000029520"],
        at=start - timedelta(hours=1),
    )[0]
    bumped = engine.bump_confidence(scheduled, spike)
    assert (
        bumped.status is Status.scheduled
        and bumped.confidence == 0.7
        and bumped.evidence[-1] == spike
    )


def test_unknown_impact_stays_zone_scheduled_and_approx_passes_through(
    engine: ClosureEngine, course_batch: CandidateBatch
) -> None:
    # ADR-008: impact unknown 은 승격 전까지 zone_scheduled, approx 는 상태에 그대로
    seg1 = _seg(course_batch, 1)
    start = seg1.window.start
    assert start is not None
    unknown = seg1.model_copy(
        update={
            "impact": Impact.unknown,
            "confidence": 0.45,
            "review_required": True,
            "approx": True,
        }
    )
    states = engine.apply(unknown, ["06-0000023206"], at=start + timedelta(minutes=1))
    assert states[0].status is Status.zone_scheduled and states[0].impact is Impact.unknown
    assert states[0].approx is True and states[0].window == seg1.window
    blocks = engine.apply(seg1, ["06-0000023206"], at=start + timedelta(minutes=1))[0]
    assert (
        blocks.impact is Impact.blocks
        and blocks.approx is False
        and blocks.status is Status.confirmed
    )
