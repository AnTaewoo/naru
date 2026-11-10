"""BE 테스트 공용 픽스처 — 실데이터 경로만 준다 (.claude/skills/real-data-testing/SKILL.md §4).

데이터가 없으면 실패한다. skip하지 않는다.
"""

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from naru_be.config import Settings
from naru_be.db import make_engine, make_sessions
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import PedGraph
from naru_be.models.domain.road_graph import RoadGraph
from naru_be.models.repositories.report_repository import ReportRepository
from naru_contracts import CandidateBatch, ClosureState, LineGeom, Status

DATA = Path(__file__).resolve().parents[3] / "data"
BE_DIR = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))


class CourseWorld(NamedTuple):
    settings: Settings
    ped: PedGraph
    index: CrosswalkIndex
    engine: ClosureEngine
    states: list[ClosureState]  # 기록된 코스 후보 16건 → 04:00 KST 기준(전부 scheduled)
    by_candidate: dict[str, list[ClosureState]]  # candidate_id → 상태 (upsert 용)


@pytest.fixture(scope="session")
def seoul_spatial_dir() -> Path:
    """가장 최근 `data/raw/seoul_spatial_<YYYYMMDD>/` (MANIFEST: seoul_spatial)."""
    dirs = sorted((DATA / "raw").glob("seoul_spatial_*"))
    assert dirs, "실데이터 없음: data/raw/seoul_spatial_<date>/ — make fetch SRC=seoul_spatial 먼저"
    return dirs[-1]


@pytest.fixture(scope="session")
def nodelink_seoul_dir() -> Path:
    """가장 최근 `data/raw/nodelink_seoul_<YYYYMMDD>/` (MANIFEST: nodelink_seoul)."""
    dirs = sorted((DATA / "raw").glob("nodelink_seoul_*"))
    assert dirs, "실데이터 없음: data/raw/nodelink_seoul_<date>/ — make fetch SRC=nodelink 먼저"
    return dirs[-1]


@pytest.fixture(scope="session")
def course_dir() -> Path:
    """`data/raw/course/` (MANIFEST: course) — 2026 서울마라톤 GPX·시각표 (T0.4)."""
    d = DATA / "raw" / "course"
    assert (d / "seoul_marathon_2026.gpx").exists(), "실데이터 없음: make fetch SRC=course 먼저"
    return d


@pytest.fixture(scope="session")
def recorded_dir() -> Path:
    """recorded 폴더 — scripts/record_*.py 산출 (AI 후보 배치, API 응답)."""
    d = DATA / "recorded"
    assert (d / "candidates").is_dir(), "기록 없음: make record-candidates SOURCE=course 먼저"
    return d


@pytest.fixture(scope="session")
def course_world(seoul_spatial_dir: Path, recorded_dir: Path) -> CourseWorld:
    """도보망 + 횡단보도 색인 + 엔진 + 코스 후보 상태 (라우터·뷰 테스트 공용, 무거워서 세션 1회)."""
    settings = Settings()
    ped = PedGraph.from_seoul_spatial(seoul_spatial_dir, settings)
    index = CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", settings)
    engine = ClosureEngine(index, settings)
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    batch = CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))
    by_candidate: dict[str, list[ClosureState]] = {}
    at = datetime(2026, 3, 15, 4, 0, tzinfo=KST)  # 첫 통제 전 — 라우터가 도착 시각으로 다시 판정
    for c in batch.candidates:
        assert isinstance(c.geometry, LineGeom)
        ids = index.from_line(c.geometry.coordinates)
        by_candidate[c.candidate_id] = engine.apply(c, ids, at=at)
    states = [s for group in by_candidate.values() for s in group]
    assert len(states) > 100 and {s.status for s in states} == {Status.scheduled}
    return CourseWorld(settings, ped, index, engine, states, by_candidate)


@pytest.fixture(scope="session")
def road_index(seoul_spatial_dir: Path, nodelink_seoul_dir: Path) -> CrosswalkIndex:
    """횡단보도 색인 + 표준노드링크 도로 그래프 — 구간 후보(from_segment)·행진 경로(T7.16)용."""
    settings = Settings()
    road_graph = RoadGraph.from_gpkg(nodelink_seoul_dir / "link.gpkg")
    return CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", settings, road_graph)


@pytest.fixture(scope="session")
def notice_batch(recorded_dir: Path) -> CandidateBatch:
    """기록된 공지 후보 배치(최신) — 11/7 r01·r04·r06, 11/9 r01·r02 (MANIFEST candidates/notice)."""
    files = sorted((recorded_dir / "candidates" / "notice").glob("*.json"))
    assert files, "기록 없음: make record-candidates SOURCE=notice 먼저"
    return CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))


@pytest.fixture(scope="module")
def report_repo() -> Iterator[ReportRepository]:
    """통제 제보 표(T7.15) — 실제 MySQL naru_test, Alembic head. 모듈 앞뒤로 비운다."""
    settings = Settings()
    assert settings.test_database_url.endswith("/naru_test"), settings.test_database_url
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={settings.test_database_url}"]})()
    command.upgrade(cfg, "head")
    engine = make_engine(settings.test_database_url)
    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("reports")}
    # 좌표·기기 토큰 원문 칸은 없다 (INTERFACE §8 — 저장 안 함)
    assert cols == {
        "id",
        "crosswalk_id",
        "state",
        "reported_at",
        "accuracy_m",
        "source",
        "device_hash",
    }
    repo = ReportRepository(make_sessions(engine))
    repo.truncate()
    yield repo
    repo.truncate()
    engine.dispose()
