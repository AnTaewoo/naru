"""T7.16 — 행진 확률을 라우터(비용 = P x 예정 비용, P ≥ 0.8 제외)·현장 도구(blocked_at)가 같이 쓴다.

프로필·상태는 test_march 와 같은 기록(11/7 r01 고리 — 세종대로사거리 06-0000036391 s 185.5 ·
06-0000023206 s 205.2 · 06-0000029520 s 225.0, 종로구청입구 06-0000002104 s 1,036.0). 경로는
교보빌딩 → 대한문(카카오 점, test_routers 와 같다): 기준 808 m, 세종대로사거리를 피하면 816 m 이상.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest
from conftest import CourseWorld
from test_march import JONGNO_GU, SEJONG_A, SEJONG_B, SEJONG_C, by_prefix, profile_of

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.march import MarchProfile, p_at
from naru_be.models.domain.prediction import blocked_at
from naru_be.models.domain.routers import TimeDependentRouter
from naru_contracts import CandidateBatch, ClosureState, SegmentGeom, Status

KST = timezone(timedelta(hours=9))
KYOBO = (126.9779039768265, 37.5709686446227)  # 카카오 '광화문교보빌딩'
DAEHANMUN = (126.976542945622, 37.5650416322942)  # 카카오 '덕수궁 대한문'


@pytest.fixture(scope="module")
def r01(road_index: CrosswalkIndex, notice_batch: CandidateBatch) -> MarchProfile:
    found = profile_of(road_index, by_prefix(notice_batch, "smpa-20261107-r01-"), Settings())
    assert found is not None
    return found


@pytest.fixture(scope="module")
def r01_states(
    course_world: CourseWorld, road_index: CrosswalkIndex, notice_batch: CandidateBatch
) -> list[ClosureState]:
    """r01 구간 후보 → 13곳 상태 (접수 시각 11/6 20:00 → scheduled, 확신도 0.85)."""
    (c,) = by_prefix(notice_batch, "smpa-20261107-r01-")
    engine = ClosureEngine(road_index, course_world.settings)
    assert isinstance(c.geometry, SegmentGeom)
    ids = road_index.from_segment(c.geometry)
    states = engine.apply(c, ids, at=datetime(2026, 11, 6, 20, 0, tzinfo=KST))
    assert len(states) == 13 and {s.status for s in states} == {Status.scheduled}
    return states


def test_router_uses_p_instead_of_whole_window(
    course_world: CourseWorld, r01: MarchProfile, r01_states: list[ClosureState]
) -> None:
    w = course_world
    router = TimeDependentRouter(w.ped, w.engine, w.settings)
    key = (r01_states[0].reason, r01_states[0].window.start, r01_states[0].window.end)
    marches = {key: r01}
    # 12:00 시작 — 기준 경로가 지나는 세종대로사거리 셋(s 185·205·225 < 선행 300)은 P 1.0 → 제외
    # → 지하보도 우회, 피한 곳 셋 (마라톤 1구간은 둘 — 고리 경로가 06-0000029520 도 고른다)
    at = datetime(2026, 11, 7, 12, 0, tzinfo=KST)
    detour = router.route(KYOBO, DAEHANMUN, at, r01_states, marches=marches)
    sejong = {SEJONG_A, SEJONG_B, SEJONG_C}
    assert {(a.crosswalk_id, a.status) for a in detour.avoided} == {
        (cid, Status.scheduled) for cid in sejong
    }
    # 16:01 창 밖 — P 0, 기준 경로(808 m) 그대로 (옛 규칙도 창 밖은 보통). 12:00 은 그보다 돌아간다
    # (816.1 m — 세 곳을 다 피하는 길, route_avoid_0430 기록과 같은 거리)
    late = router.route(
        KYOBO, DAEHANMUN, at + timedelta(hours=4, minutes=1), r01_states, marches=marches
    )
    assert late.avoided == () and 800 < late.distance_m < 830
    assert 810 < detour.distance_m < 830 and detour.distance_m > late.distance_m
    # 15:59 — 머리 x_i = 0.1009 x 14,340 x (1 + 0.5u) = 724~2,172 m, 꼬리 = 머리 - 1,453:
    # 세종대로사거리 셋은 x < s + 1,453 ↔ u < 0.27~0.32 → 13~14/21 = 0.62~0.67 → 제외는 아니고
    # 비용 223~240 m 씩. 라우터는 비용이 붙은 곳 중 일부만 피한 길을 고를 수 있다
    # — 피한 곳은 셋 안에서 하나 이상, 전부 scheduled
    near_end = router.route(
        KYOBO, DAEHANMUN, at + timedelta(hours=3, minutes=59), r01_states, marches=marches
    )
    assert near_end.avoided and {a.crosswalk_id for a in near_end.avoided} <= sejong
    assert {a.status for a in near_end.avoided} == {Status.scheduled}
    assert near_end.distance_m > late.distance_m
    window = (r01_states[0].window.start, r01_states[0].window.end)
    assert window[0] is not None and window[1] is not None
    p = p_at(r01, window[0], window[1], SEJONG_C, at + timedelta(hours=3, minutes=59), w.settings)
    assert p == pytest.approx(14 / 21)


def test_blocked_at_with_march(
    course_world: CourseWorld, r01: MarchProfile, r01_states: list[ClosureState]
) -> None:
    w = course_world
    jongno = next(s for s in r01_states if s.crosswalk_id == JONGNO_GU)
    sejong = next(s for s in r01_states if s.crosswalk_id == SEJONG_A)
    at = datetime(2026, 11, 7, 12, 0, tzinfo=KST)
    # 옛 규칙: 창 안 예정은 전부 막힘. 행진 모델: 종로구청입구(s 1,036)는 12:00 에 P 0.2(하한)
    # → 막힘 아님
    assert blocked_at(jongno, at, w.engine, w.settings) is Status.scheduled
    assert blocked_at(jongno, at, w.engine, w.settings, march=r01) is None
    assert (
        blocked_at(sejong, at, w.engine, w.settings, march=r01) is Status.scheduled
    )  # P 1.0 ≥ 0.8
    # 14:00 — 머리 x_i = 0.1009 x 7,200 x (1 + 0.5u) = 363~1,090:
    # 종로구청입구 1,036 - 300 ≤ x ↔ u ≥ 0.055
    # → u = 0.1 … 1 → 10/21 = 0.48 < 0.8 → 막힘 아님(비용만)
    assert blocked_at(jongno, at + timedelta(hours=2), w.engine, w.settings, march=r01) is None
    assert math.isclose(
        p_at(
            r01,
            jongno.window.start,
            jongno.window.end,
            JONGNO_GU,
            at + timedelta(hours=2),
            w.settings,
        )
        or 0,
        10 / 21,
    )
