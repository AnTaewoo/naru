"""BE 테스트 공용 픽스처 — 실데이터 경로만 준다 (.claude/skills/real-data-testing/SKILL.md §4).

데이터가 없으면 실패한다. skip하지 않는다.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import pytest

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.ped_graph import PedGraph
from naru_contracts import CandidateBatch, ClosureState, LineGeom, Status

DATA = Path(__file__).resolve().parents[3] / "data"
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
