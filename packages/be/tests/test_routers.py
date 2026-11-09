"""T3.1 — TimeDependentRouter: 교보빌딩 앞 → 덕수궁 대한문 (도보망·기록된 코스 후보·카카오 좌표).

기대값은 2026-11-07 에 그래프를 돌려 확인한 값 (기준 755 m, 우회 777 m + 접근 구간).
"""

import itertools
import math
from datetime import datetime, timedelta, timezone

import pytest
from conftest import CourseWorld

from naru_be.errors import OutOfCoverageError
from naru_be.models.domain.ped_graph import EdgeKind
from naru_be.models.domain.routers import BaselineRouter, TimeDependentRouter
from naru_be.models.domain.types import Path, RouteLeg
from naru_contracts import ClosureState, Status

KST = timezone(timedelta(hours=9))
# 카카오 기록: '광화문교보빌딩' id 24020019 (종로 1), '덕수궁 대한문' id 17582477
KYOBO = (126.9779039768265, 37.5709686446227)
DAEHANMUN = (126.976542945622, 37.5650416322942)


@pytest.fixture(scope="module")
def world(course_world: CourseWorld) -> tuple[TimeDependentRouter, list[ClosureState]]:
    w = course_world
    return TimeDependentRouter(w.ped, w.engine, w.settings), w.states


def test_no_closure_route_is_short(world: tuple[TimeDependentRouter, list[ClosureState]]) -> None:
    router, states = world
    path = router.route(
        KYOBO, DAEHANMUN, datetime(2026, 3, 15, 13, 30, tzinfo=KST), states
    )  # 통제 다 끝난 뒤
    assert path.distance_m < 1500  # ROADMAP (a)
    assert 800 < path.distance_m < 830  # 기준 755 m + 접근 44.7 + 8.8 m
    assert path.avoided == ()
    assert [leg.kind for leg in path.legs] == [
        EdgeKind.sidewalk,
        EdgeKind.crosswalk,
        EdgeKind.sidewalk,
        EdgeKind.crosswalk,
        EdgeKind.sidewalk,
    ]
    assert path.coords[0] == KYOBO and path.coords[-1] == DAEHANMUN and len(path.coords) > 10
    assert path.duration_s == round(path.distance_m / 1.2)
    free = BaselineRouter(router.ped, router.settings).route(KYOBO, DAEHANMUN)  # T3.2
    assert free.coords == path.coords and free.distance_m == path.distance_m
    assert free.legs == path.legs and free.avoided == ()


def test_during_closure_detours_via_underpass(
    world: tuple[TimeDependentRouter, list[ClosureState]],
) -> None:
    router, states = world
    path = router.route(
        KYOBO, DAEHANMUN, datetime(2026, 3, 15, 7, 45, tzinfo=KST), states
    )  # 1구간 07:20~08:08
    kinds = {leg.kind for leg in path.legs}
    assert EdgeKind.underpass in kinds and EdgeKind.stairs in kinds  # ROADMAP (b)
    assert 820 < path.distance_m < 860  # 우회 777 m + 접근
    avoided = {a.crosswalk_id: a for a in path.avoided}
    # 기준 경로의 세종대로사거리 횡단보도 둘이 07:45 에 confirmed (1구간)
    assert {"06-0000023206", "06-0000036391"} <= set(avoided)
    assert all(a.status is Status.confirmed for a in avoided.values())
    assert avoided["06-0000023206"].reason == "marathon 1구간 세종대로 사거리~숭례문 오거리"
    assert avoided["06-0000023206"].until == datetime(2026, 3, 15, 8, 8, tzinfo=KST)
    assert all(not a.approx and a.evidence for a in avoided.values())
    underpass = next(leg for leg in path.legs if leg.kind is EdgeKind.underpass)
    assert underpass.name is not None and underpass.name.endswith("지하보도")
    # confirmed 횡단보도는 경로에 없다
    used = {
        cid
        for u, v in zip(path.node_ids, path.node_ids[1:], strict=False)
        for cid in router.ped.graph[u][v]["edge"].crosswalk_ids
    }
    assert not (used & set(avoided))


def test_scheduled_penalty_only_inside_notice_window(
    world: tuple[TimeDependentRouter, list[ClosureState]],
) -> None:  # ADR-011 A — 예정은 닿는 시각이 공지 창 안일 때만 횡단보도당 +300초, 창 밖은 보통
    router, states = world
    # 04:30: 첫 통제(출발지 05:00) 전 — 끝까지 걸어도 창 밖이라 기준 경로 그대로
    # (808.3 m, 2026-11-07)
    at = datetime(2026, 3, 15, 4, 30, tzinfo=KST)
    early = router.route(KYOBO, DAEHANMUN, at, states)
    assert early.avoided == () and 800 < early.distance_m < 830
    # 07:00: 출발지(05:00~)는 confirmed 라 차단, 1구간(07:20~)은 닿는 시각(07:0x)이 창 밖이라 보통
    mixed = {
        a.crosswalk_id: a.status
        for a in router.route(KYOBO, DAEHANMUN, at + timedelta(hours=2, minutes=30), states).avoided
    }
    assert mixed == {"06-0000036391": Status.confirmed}
    # 확신도 0.75(≥ 0.7, 확인 기준 0.8 미만) 면 창 안에서도 scheduled — 07:45 엔 출발지·1구간 창 안
    # → 횡단보도당 +300초라 지하보도로 피하고, 피한 곳은 scheduled
    soft = [s.model_copy(update={"confidence": 0.75}) for s in states]
    inside = router.route(KYOBO, DAEHANMUN, datetime(2026, 3, 15, 7, 45, tzinfo=KST), soft)
    assert EdgeKind.underpass in {leg.kind for leg in inside.legs}
    assert {(a.crosswalk_id, a.status) for a in inside.avoided} == {
        ("06-0000023206", Status.scheduled),
        ("06-0000036391", Status.scheduled),
    }
    # 확신도 0.7 미만 예정은 무시 → 기준 경로 그대로
    low = [s.model_copy(update={"confidence": 0.5}) for s in states]
    free = router.route(KYOBO, DAEHANMUN, datetime(2026, 3, 15, 7, 45, tzinfo=KST), low)
    assert free.avoided == () and 800 < free.distance_m < 830
    assert router.settings.scheduled_penalty_s == 300


def test_outside_graph_is_out_of_coverage(
    world: tuple[TimeDependentRouter, list[ClosureState]],
) -> None:  # ADR-011 그래프 밖 — T6.9 부터 그래프가 서울 전체라 서울 밖(경기 성남, 태우 11/9)
    router, states = world
    out_from, out_to = (127.1112, 37.3947), (127.1150, 37.3960)
    at = datetime(2026, 3, 15, 10, 0, tzinfo=KST)
    with pytest.raises(OutOfCoverageError) as e:
        router.route(out_from, out_to, at, states)
    assert e.value.field == "from" and e.value.code == "out_of_coverage"
    with pytest.raises(OutOfCoverageError) as e:
        router.route(KYOBO, out_to, at, states)
    assert e.value.field == "to"
    assert router.settings.max_snap_m == 150


def leg_length_m(path: Path, leg: RouteLeg) -> float:
    """coords[i..j] 의 측지 길이 (구면 근사)."""
    i, j = leg.coord_range
    total = 0.0
    for (lng1, lat1), (lng2, lat2) in itertools.pairwise(path.coords[i : j + 1]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        h = (
            math.sin((p2 - p1) / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
        )
        total += 2 * 6_371_008.8 * math.asin(math.sqrt(h))
    return total


def test_legs_partition_route_with_coord_range(
    world: tuple[TimeDependentRouter, list[ClosureState]],
) -> None:
    """ADR-009: 레그가 coords 를 빈틈없이 나누고, 레그 선 길이 = 레그 거리, 합 = 총거리."""
    router, states = world
    for hh, mm in ((7, 45), (13, 30)):
        path = router.route(KYOBO, DAEHANMUN, datetime(2026, 3, 15, hh, mm, tzinfo=KST), states)
        assert path.legs[0].coord_range[0] == 0
        assert path.legs[-1].coord_range[1] == len(path.coords) - 1
        for a, b in itertools.pairwise(path.legs):
            assert a.coord_range[1] == b.coord_range[0] and a.kind is not b.kind
        assert abs(sum(leg.distance_m for leg in path.legs) - path.distance_m) < 0.1
        for leg in path.legs:  # 2026-11-08 확인: 레그마다 차이 최대 0.7 m
            assert abs(leg_length_m(path, leg) - leg.distance_m) <= 1.0, leg
    # 07:45 지하보도 레그 — 광화문(세종문화회관) 지하보도, coords[3..8] (2026-11-08 그래프로 확인)
    path = router.route(KYOBO, DAEHANMUN, datetime(2026, 3, 15, 7, 45, tzinfo=KST), states)
    k = next(n for n, leg in enumerate(path.legs) if leg.kind is EdgeKind.underpass)
    underpass, before = path.legs[k], path.legs[k - 1]
    assert underpass.name == "광화문(세종문화회관) 지하보도" and underpass.coord_range == (3, 8)
    # 입구 = 지하보도 레그 시작점 = 앞 계단 레그의 끝 (경계 공유)
    assert before.kind is EdgeKind.stairs and before.coord_range[1] == underpass.coord_range[0]
    # 첫 레그는 교보빌딩 → 첫 노드 접근 구간(약 45 m)을 포함한 sidewalk
    assert path.legs[0].kind is EdgeKind.sidewalk and path.legs[0].distance_m > 44
