"""AI 테스트 공용 픽스처 — 실데이터 경로만 준다 (.claude/skills/real-data-testing/SKILL.md §4).

데이터가 없으면 실패한다. skip하지 않는다.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture(scope="session")
def notices_dir() -> Path:
    """`data/raw/notices/` — sentences.jsonl (scripts/build_notices.py 산출)."""
    d = DATA / "raw" / "notices"
    assert (d / "sentences.jsonl").exists(), (
        "실데이터 없음: uv run python scripts/build_notices.py 먼저"
    )
    return d


@pytest.fixture(scope="session")
def smpa_dir() -> Path:
    """`data/raw/notices/smpa/` — 서울경찰청 '오늘의 주요집회' PDF (태우가 수동으로 받음)."""
    d = DATA / "raw" / "notices" / "smpa"
    assert list(d.glob("*.pdf")), "실데이터 없음: 오늘의 집회 PDF를 notices/smpa 에 넣는다"
    return d


@pytest.fixture(scope="session")
def topis_recorded() -> list[tuple[str, datetime]]:
    """`data/recorded/topis_notice/*.json` — TOPIS NoticeList 응답 기록 (status 200만)."""
    d = DATA / "recorded" / "topis_notice"
    files = sorted(d.glob("*.json"))
    assert files, "기록 없음: uv run python scripts/build_notices.py --topis 먼저"
    out = []
    for p in files:
        rec = json.loads(p.read_text("utf-8"))
        if rec["status"] == 200:
            out.append((rec["raw"], datetime.fromisoformat(rec["called_at"])))
    assert out, "status 200 기록이 없다"
    return out


@pytest.fixture(scope="session")
def recorded_dir() -> Path:
    """`data/recorded/` — scripts/record_api.py 기록 (incident·links·rtd)."""
    d = DATA / "recorded"
    assert (d / "incident").is_dir(), "기록 없음: make record API=incident 먼저"
    return d


@pytest.fixture(scope="session")
def course_dir() -> Path:
    """`data/raw/course/` (MANIFEST: course) — 2026 서울마라톤 GPX·시각표."""
    d = DATA / "raw" / "course"
    assert (d / "seoul_marathon_2026.gpx").exists(), "실데이터 없음: make fetch SRC=course 먼저"
    return d


@pytest.fixture(scope="session")
def seoul_spatial_dir() -> Path:
    """가장 최근 `data/raw/seoul_spatial_<YYYYMMDD>/` — OA-23081.xlsx (교차로 지명사전)."""
    dirs = sorted((DATA / "raw").glob("seoul_spatial_*"))
    assert dirs, "실데이터 없음: make fetch SRC=seoul_spatial 먼저"
    return dirs[-1]


@pytest.fixture(scope="session")
def nodelink_seoul_dir() -> Path:
    """가장 최근 `data/raw/nodelink_seoul_<YYYYMMDD>/` — link.gpkg ROAD_NAME (도로명 사전)."""
    dirs = sorted((DATA / "raw").glob("nodelink_seoul_*"))
    assert dirs, "실데이터 없음: make fetch SRC=nodelink 먼저"
    return dirs[-1]
