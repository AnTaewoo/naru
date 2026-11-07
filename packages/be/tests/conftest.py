"""BE 테스트 공용 픽스처 — 실데이터 경로만 준다 (.claude/skills/real-data-testing/SKILL.md §4).

데이터가 없으면 실패한다. skip하지 않는다.
"""

from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[3] / "data"


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
