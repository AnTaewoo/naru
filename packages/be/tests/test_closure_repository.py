"""T2.4 — ClosureRepository: 실제 MySQL(naru_test) 에 upsert → active_at(t, bbox) (실데이터).

입력은 T2.3 엔진이 기록된 코스 후보로 만든 상태. DB 는 docker compose 의 MySQL 8.4(호스트 3307),
스키마 naru_test. Alembic 으로 테이블을 만들고 테스트마다 비운다. SQLite 대체 금지 (스킬 §4).
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from naru_be.config import Settings
from naru_be.db import make_engine, make_sessions
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_contracts import CandidateBatch, LineGeom, Status

KST = timezone(timedelta(hours=9))
GWANGHWAMUN = (126.965, 37.555, 126.990, 37.580)  # minLng, minLat, maxLng, maxLat
BE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="module")
def repo(settings: Settings) -> Iterator[ClosureRepository]:
    assert settings.test_database_url.endswith("/naru_test"), settings.test_database_url
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={settings.test_database_url}"]})()
    command.upgrade(cfg, "head")
    engine = make_engine(settings.test_database_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT @@time_zone")).scalar() == "+00:00"
        assert "closure_states" in inspect(conn).get_table_names()
    repo = ClosureRepository(make_sessions(engine), settings)
    repo.truncate()
    yield repo
    engine.dispose()


@pytest.fixture(scope="module")
def states(seoul_spatial_dir: Path, recorded_dir: Path, settings: Settings) -> dict[str, object]:
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    batch = CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))
    index = CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", settings)
    engine = ClosureEngine(index, settings)
    seg1 = next(c for c in batch.candidates if c.candidate_id == "course-20260315-seg01")
    assert isinstance(seg1.geometry, LineGeom)
    ids = index.from_line(seg1.geometry.coordinates)
    start = seg1.window.start
    assert start is not None
    return {
        "candidate": seg1,
        "ids": ids,
        "scheduled": engine.apply(seg1, ids, at=start - timedelta(minutes=1)),
        "confirmed": engine.apply(seg1, ids, at=start + timedelta(minutes=1)),
    }


def test_upsert_then_active_at_returns_engine_states(
    repo: ClosureRepository, states: dict[str, object]
) -> None:
    repo.truncate()
    scheduled = states["scheduled"]
    assert (
        isinstance(scheduled, list) and len(scheduled) == 6
    )  # 1구간 15 m 버퍼 안 횡단보도 6개 (T2.3)
    n = repo.upsert_many(scheduled, "course-20260315-seg01")
    assert n == 6 and repo.count() == 6
    # 1구간 통제 07:20~08:08 KST. 07:30 에 광화문 bbox → 6개 그대로 (KST 입력 → UTC 저장 → KST 반환)
    at = datetime(2026, 3, 15, 7, 30, tzinfo=KST)
    got = repo.active_at(at, GWANGHWAMUN)
    assert sorted(s.crosswalk_id for s in got) == sorted(s.crosswalk_id for s in scheduled)
    by_id = {s.crosswalk_id: s for s in scheduled}
    for s in got:
        o = by_id[s.crosswalk_id]
        assert (
            s.status is Status.scheduled and s.confidence == o.confidence and s.reason == o.reason
        )
        assert s.window.start == o.window.start and s.window.end == o.window.end
        assert s.window.start is not None and s.window.start.utcoffset() == timedelta(hours=9)
        assert s.evidence == o.evidence and s.impact is o.impact and s.approx is o.approx
        assert abs(s.lng - o.lng) < 1e-6 and abs(s.lat - o.lat) < 1e-6
    # 같은 (candidate_id, crosswalk_id) 로 confirmed 를 upsert → 덮어쓴다, 행 수 그대로
    confirmed = states["confirmed"]
    assert isinstance(confirmed, list)
    repo.upsert_many(confirmed, "course-20260315-seg01")
    assert repo.count() == 6
    assert {s.status for s in repo.active_at(at, GWANGHWAMUN)} == {Status.confirmed}
    assert all(len(s.evidence) == 2 for s in repo.active_at(at, GWANGHWAMUN))


def test_active_at_respects_window_and_bbox(
    repo: ClosureRepository, states: dict[str, object]
) -> None:
    repo.truncate()
    scheduled = states["scheduled"]
    assert isinstance(scheduled, list)
    repo.upsert_many(scheduled, "course-20260315-seg01")
    # 통제 시작 전(07:19)은 아직 아님, 종료+30분 안(08:37)은 포함, 그 뒤(08:39)는 제외
    assert repo.active_at(datetime(2026, 3, 15, 7, 19, tzinfo=KST), GWANGHWAMUN) == []
    assert len(repo.active_at(datetime(2026, 3, 15, 8, 37, tzinfo=KST), GWANGHWAMUN)) == 6
    assert repo.active_at(datetime(2026, 3, 15, 8, 39, tzinfo=KST), GWANGHWAMUN) == []
    # 여의도 bbox 에는 없다. UTC 로 같은 시각을 줘도 결과 같다
    yeouido = (126.910, 37.515, 126.940, 37.535)
    assert repo.active_at(datetime(2026, 3, 15, 7, 30, tzinfo=KST), yeouido) == []
    utc = datetime(2026, 3, 14, 22, 30, tzinfo=UTC)
    assert len(repo.active_at(utc, GWANGHWAMUN)) == 6
    with pytest.raises(ValueError):
        repo.active_at(datetime(2026, 3, 15, 7, 30), GWANGHWAMUN)
