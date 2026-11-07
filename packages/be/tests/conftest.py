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
