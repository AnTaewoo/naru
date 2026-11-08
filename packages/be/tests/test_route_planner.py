"""T3.2 — RoutePlanner: 실제 MySQL(naru_test) 의 폐쇄 상태 + 두 라우터 → RouteResult (실데이터).

기록된 코스 후보 16건을 엔진으로 07:21 KST 기준 상태로 만들어 저장(1구간·출발지 구간 confirmed,
나머지 scheduled). 기대 거리는 T3.1 과 같다 (기준 808.3 m, 지하보도 우회 839.6 m, 2026-11-07).
"""

import json
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from naru_be.config import Settings
from naru_be.db import make_engine, make_sessions
from naru_be.errors import InvalidQueryError
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import EdgeKind, PedGraph
from naru_be.models.domain.route_planner import RoutePlanner, parse_latlng
from naru_be.models.domain.routers import BaselineRouter, TimeDependentRouter
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_contracts import CandidateBatch, LineGeom, RouteQuery, Status

KST = timezone(timedelta(hours=9))
BE_DIR = Path(__file__).resolve().parents[1]
# 카카오 기록: '광화문교보빌딩' id 24020019, '덕수궁 대한문' id 17582477 (test_routers 와 같은 점)
KYOBO = "37.5709686446227,126.9779039768265"  # INTERFACE §2: from=lat,lng
DAEHANMUN = "37.5650416322942,126.976542945622"


def query(depart_at: datetime) -> RouteQuery:
    return RouteQuery.model_validate({"from": KYOBO, "to": DAEHANMUN, "depart_at": depart_at})


@pytest.fixture(scope="module")
def planner(seoul_spatial_dir: Path, recorded_dir: Path) -> Iterator[RoutePlanner]:
    settings = Settings()
    assert settings.test_database_url.endswith("/naru_test")
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={settings.test_database_url}"]})()
    command.upgrade(cfg, "head")
    engine = make_engine(settings.test_database_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT @@time_zone")).scalar() == "+00:00"
    repo = ClosureRepository(make_sessions(engine), settings)
    repo.truncate()

    ped = PedGraph.from_seoul_spatial(seoul_spatial_dir, settings)
    index = CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", settings)
    closure_engine = ClosureEngine(index, settings)
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    batch = CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))
    at = datetime(2026, 3, 15, 7, 21, tzinfo=KST)  # 1구간(07:20~) 막 시작
    statuses: set[Status] = set()
    for c in batch.candidates:
        assert isinstance(c.geometry, LineGeom)
        states = closure_engine.apply(c, index.from_line(c.geometry.coordinates), at=at)
        statuses |= {s.status for s in states}
        repo.upsert_many(states, c.candidate_id)
    assert statuses == {Status.scheduled, Status.confirmed} and repo.count() > 100
    yield RoutePlanner(
        repo, TimeDependentRouter(ped, closure_engine, settings), BaselineRouter(ped, settings)
    )
    engine.dispose()


def test_after_closure_path_equals_baseline(planner: RoutePlanner) -> None:
    depart = datetime(2026, 3, 15, 13, 30, tzinfo=KST)  # 통제 전부 끝남
    result = planner.plan(query(depart))
    assert result.depart_at == depart
    assert result.computed_at.tzinfo is not None
    assert 800 < result.baseline.distance_m < 830 and result.baseline.avoided == ()
    assert result.path.coords == result.baseline.coords  # ROADMAP: baseline == 통제 전 경로
    assert result.path.distance_m == result.baseline.distance_m and result.path.avoided == ()
    assert result.path.coords[0] == parse_latlng(KYOBO, "from")
    assert result.path.coords[-1] == parse_latlng(DAEHANMUN, "to")


def test_during_closure_avoids_repository_confirmed(planner: RoutePlanner) -> None:
    result = planner.plan(query(datetime(2026, 3, 15, 7, 45, tzinfo=KST)))  # 1구간 07:20~08:08
    assert EdgeKind.underpass in {leg.kind for leg in result.path.legs}
    assert 835 < result.path.distance_m < 845  # 839.6 m
    assert result.path.coords != result.baseline.coords  # 우회 경로는 기준과 다르다
    assert 800 < result.baseline.distance_m < 830
    avoided = {a.crosswalk_id: a for a in result.path.avoided}
    assert {"06-0000023206", "06-0000036391"} <= set(avoided)  # 저장소의 confirmed 가 avoided 에
    assert all(a.status is Status.confirmed for a in avoided.values())
    assert avoided["06-0000023206"].reason == "marathon 1구간 세종대로 사거리~숭례문 오거리"
    assert avoided["06-0000023206"].until == datetime(2026, 3, 15, 8, 8, tzinfo=KST)


def test_horizon_catches_closure_starting_after_departure(planner: RoutePlanner) -> None:
    # ADR-011 A: 예정은 닿는 시각이 공지 창 안일 때만 친다. 지평(60분) 조회는 "걷는 동안 시작하는"
    # 통제를 잡는다 — 04:59 출발이면 출발지 구간(05:00~08:30, 36391)은 출발 때 active_at 에 없지만
    # 36391 에 닿을 때(약 75초 뒤, 첫 보도 89.8 m)는 시작해 confirmed → 막혀서 돌아간다
    depart = datetime(2026, 3, 15, 4, 59, tzinfo=KST)
    assert planner.repo.active_at(depart, planner.bbox_of(query(depart))) == []
    result = planner.plan(query(depart))
    assert {(a.crosswalk_id, a.status) for a in result.path.avoided} == {
        ("06-0000036391", Status.confirmed)
    }
    assert result.path.coords != result.baseline.coords
    # 04:45 출발: 끝까지 걸어도 05:00 전 → 창 밖이라 원래 길 그대로 (808.3 m)
    early = planner.plan(query(datetime(2026, 3, 15, 4, 45, tzinfo=KST)))
    assert early.path.avoided == () and early.path.coords == early.baseline.coords
    # 06:30 출발: 출발지(진행 중)는 confirmed 로 막히고, 1구간(07:20~, 23206)은 닿는 시각이
    # 창 밖이라 피하지 않는다 — 지평 조회엔 들어오지만 비용은 0. 그래서 지하보도까지 가지 않고
    # 36391 만 비켜 다른 횡단보도로 건넌다 (예전 x3 규칙에선 23206 도 피해 지하보도였다)
    depart = datetime(2026, 3, 15, 6, 30, tzinfo=KST)
    active = planner.repo.active_at(depart, planner.bbox_of(query(depart)))
    at_ids = {c.crosswalk_id for c in active}
    assert "06-0000036391" in at_ids and "06-0000023206" not in at_ids
    result = planner.plan(query(depart))
    assert {(a.crosswalk_id, a.status) for a in result.path.avoided} == {
        ("06-0000036391", Status.confirmed)
    }
    assert result.path.coords != result.baseline.coords
    assert EdgeKind.underpass not in {leg.kind for leg in result.path.legs}


def test_invalid_query_and_no_flask() -> None:
    bad = {"from": "37.57", "to": DAEHANMUN, "depart_at": "2026-03-15T07:00:00+09:00"}
    with pytest.raises(InvalidQueryError) as e:
        parse_latlng(bad["from"], "from")
    assert e.value.code == "invalid_query" and e.value.field == "from"
    with pytest.raises(InvalidQueryError):
        parse_latlng("126.9779,37.5709", "to")  # lng,lat 순서 바꿔 쓴 것 — lat 범위 밖
    assert parse_latlng(" 37.5709686446227 , 126.9779039768265 ", "from") == (
        126.9779039768265,
        37.5709686446227,
    )
    # ROADMAP: Flask import 없음 — 새 인터프리터에서 planner 만 import 해도 flask 가 안 올라온다
    code = "import sys, naru_be.models.domain.route_planner; assert 'flask' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
