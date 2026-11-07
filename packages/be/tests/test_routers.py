"""T3.1 — TimeDependentRouter: 교보빌딩 앞 → 덕수궁 대한문 (도보망·기록된 코스 후보·카카오 좌표).

기대값은 2026-11-07 에 그래프를 돌려 확인한 값 (기준 755 m, 우회 777 m + 접근 구간).
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import EdgeKind, PedGraph
from naru_be.models.domain.routers import BaselineRouter, TimeDependentRouter
from naru_contracts import CandidateBatch, ClosureState, LineGeom, Status

KST = timezone(timedelta(hours=9))
# 카카오 기록: '광화문교보빌딩' id 24020019 (종로 1), '덕수궁 대한문' id 17582477
KYOBO = (126.9779039768265, 37.5709686446227)
DAEHANMUN = (126.976542945622, 37.5650416322942)


@pytest.fixture(scope="module")
def world(
    seoul_spatial_dir: Path, recorded_dir: Path
) -> tuple[TimeDependentRouter, list[ClosureState]]:
    settings = Settings()
    ped = PedGraph.from_seoul_spatial(seoul_spatial_dir, settings)
    index = CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", settings)
    engine = ClosureEngine(index, settings)
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    batch = CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))
    states: list[ClosureState] = []
    for c in (
        batch.candidates
    ):  # 상태는 06:00 기준(전부 scheduled)으로 저장된 셈 — 라우터가 도착 시각으로 다시 판정
        assert isinstance(c.geometry, LineGeom)
        states += engine.apply(
            c, index.from_line(c.geometry.coordinates), at=datetime(2026, 3, 15, 4, 0, tzinfo=KST)
        )
    assert len(states) > 100 and {s.status for s in states} == {Status.scheduled}
    return TimeDependentRouter(ped, engine, settings), states


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


def test_scheduled_is_penalized_not_excluded(
    world: tuple[TimeDependentRouter, list[ClosureState]],
) -> None:
    router, states = world
    # 04:30: 첫 통제(출발지 05:00) 전이라 전부 scheduled → x3. 세종대로사거리를 피해 지하도가 싸다
    at = datetime(2026, 3, 15, 4, 30, tzinfo=KST)
    path = router.route(KYOBO, DAEHANMUN, at, states)
    assert EdgeKind.underpass in {leg.kind for leg in path.legs}
    assert 835 < path.distance_m < 845  # 839.6 m (2026-11-07)
    assert {(a.crosswalk_id, a.status) for a in path.avoided} == {
        ("06-0000023206", Status.scheduled),
        ("06-0000036391", Status.scheduled),
    }
    # 07:00: 출발지 구간(05:00~)은 confirmed, 1구간(07:20~)은 scheduled — 횡단보도마다 다르게
    mixed = {
        a.crosswalk_id: a.status
        for a in router.route(KYOBO, DAEHANMUN, at + timedelta(hours=2, minutes=30), states).avoided
    }
    assert mixed == {"06-0000023206": Status.scheduled, "06-0000036391": Status.confirmed}
    # confidence < 0.7 인 scheduled 는 무시 → 기준 경로 그대로 (808.3 m)
    low = [s.model_copy(update={"confidence": 0.5}) for s in states]
    free = router.route(KYOBO, DAEHANMUN, at, low)
    assert free.avoided == () and 800 < free.distance_m < 830
