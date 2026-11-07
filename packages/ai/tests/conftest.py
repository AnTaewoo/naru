"""AI 테스트 공용 픽스처 — 실데이터 경로만 준다 (.claude/skills/real-data-testing/SKILL.md §4).

데이터가 없으면 실패한다. skip하지 않는다.
"""

from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture(scope="session")
def course_dir() -> Path:
    """`data/raw/course/` (MANIFEST: course) — 2026 서울마라톤 GPX·시각표."""
    d = DATA / "raw" / "course"
    assert (d / "seoul_marathon_2026.gpx").exists(), "실데이터 없음: make fetch SRC=course 먼저"
    return d
