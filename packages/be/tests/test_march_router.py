"""T7.16 → 태우 11/12 — 행진도 횡단보도 통제는 사건 전 구역(창 내내). 군집(P)은 표시만
(키프레임 API·지도). 라우터·현장 도구(blocked_at)는 P 를 보지 않는다 (ADR-015 E 개정).

프로필·상태는 test_march 와 같은 기록(11/7 r01 고리 — 세종대로사거리 06-0000036391 s 185.5 ·
06-0000023206 s 205.2 · 06-0000029520 s 225.0, 종로구청입구 06-0000002104 s 1,036.0). 경로는
교보빌딩 → 대한문(카카오 점, test_routers 와 같다): 기준 808 m, 세종대로사거리를 피하면 816 m 이상.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from conftest import CourseWorld
from test_march import JONGNO_GU, SEJONG_A, SEJONG_B, SEJONG_C, by_prefix, profile_of

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.march import MarchProfile, p_at
from naru_be.models.domain.ped_graph import PedEdge
from naru_be.models.domain.prediction import blocked_at
from naru_be.models.domain.routers import TimeDependentRouter
from naru_contracts import (
    CandidateBatch,
    ClosureState,
    Evidence,
    EvidenceKind,
    SegmentGeom,
    Status,
)

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


def test_march_blocks_whole_window_like_any_closure(
    course_world: CourseWorld, r01_states: list[ClosureState]
) -> None:
    w = course_world
    router = TimeDependentRouter(w.ped, w.engine, w.settings)
    sejong = {SEJONG_A, SEJONG_B, SEJONG_C}
    # 12:00 시작·15:30 — 창 안 예정(확신도 0.85)은 횡단보도마다 +300초 → 세종대로사거리 셋을
    # 피해 돌아간다(816.1 m, route_avoid_0430 기록과 같은 길). 군집(12:00 출발점, 15:30 거의 한
    # 바퀴)이 어디 있든 같다. 15:59 는 걸어서 닿을 때 16:00 이 지나 창 밖인 곳이 생긴다(시각 의존)
    at = datetime(2026, 11, 7, 12, 0, tzinfo=KST)
    start = router.route(KYOBO, DAEHANMUN, at, r01_states)
    near_end = router.route(KYOBO, DAEHANMUN, at + timedelta(hours=3, minutes=30), r01_states)
    for r in (start, near_end):
        assert {(a.crosswalk_id, a.status) for a in r.avoided} == {
            (cid, Status.scheduled) for cid in sejong
        }
        assert 810 < r.distance_m < 830
    assert near_end.distance_m == start.distance_m
    # 16:01 창 밖 — 기준 경로(808 m)
    late = router.route(KYOBO, DAEHANMUN, at + timedelta(hours=4, minutes=1), r01_states)
    assert late.avoided == () and late.distance_m < start.distance_m


def _edge_with(w: CourseWorld, crosswalk_id: str) -> PedEdge:
    for _, _, data in w.ped.graph.edges(data=True):
        edge: PedEdge = data["edge"]
        if crosswalk_id in edge.crosswalk_ids:
            return edge
    raise AssertionError(f"그래프에 {crosswalk_id} 간선이 없다")


def test_confirmed_march_excludes_crosswalk_away_from_cluster(
    course_world: CourseWorld, r01: MarchProfile, r01_states: list[ClosureState]
) -> None:
    """태우 11/12 운영 확인: 통제 중 행진인데 군집에서 먼 횡단보도는 P 하한 0.5(비용 180 m)라
    건널 수 있었다. 이제 통제 중이면 사건 전 구역 제외 — 종로구청입구(s 1,036, 12:00 군집은
    출발점)."""
    w = course_world
    at = datetime(2026, 11, 7, 12, 0, tzinfo=KST)
    jongno = next(s for s in r01_states if s.crosswalk_id == JONGNO_GU)
    start, end = jongno.window.start, jongno.window.end
    assert start is not None and end is not None
    # 표시용 P 는 그대로 — 예정 0.2(하한), 통제 중 0.5 (키프레임 API·지도 군집)
    assert p_at(r01, start, end, JONGNO_GU, at, w.settings) == 0.2
    assert p_at(r01, start, end, JONGNO_GU, at, w.settings, confirmed=True) == 0.5
    incident = Evidence(kind=EvidenceKind.topis_incident, ref="test", at=at)
    confirmed = [
        s.model_copy(update={"confidence": 0.9, "evidence": [*s.evidence, incident]})
        for s in r01_states
    ]
    router = TimeDependentRouter(w.ped, w.engine, w.settings)
    by = router._by_crosswalk(confirmed)
    assert w.engine.status_of_state(by[JONGNO_GU][0], at) is Status.confirmed
    assert router._closure_cost(_edge_with(w, JONGNO_GU), at, by) is None  # 제외
    # 예정이면 창 안 +300초(360 m) — 옛 행진 비용 P x 360 = 72 m 가 아니다
    scheduled = router._by_crosswalk(r01_states)
    assert router._closure_cost(_edge_with(w, JONGNO_GU), at, scheduled) == pytest.approx(360.0)
    # 현장 도구도 같은 규칙
    assert blocked_at(jongno, at, w.engine, w.settings) is Status.scheduled
    assert blocked_at(by[JONGNO_GU][0], at, w.engine, w.settings) is Status.confirmed
