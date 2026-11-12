"""T6.1 — TOPIS 실시간 돌발(OA-13315 AccInfo) → 후보 (ADR-011 E·ADR-013 H).

입력은 기록 원문만:
- incident/20261107T154053_AccInfo.json — 2026-11-07 15:40 수신, 53건 (MANIFEST recorded/incident)
- links/20261108T180400_{LinkInfo,LinkVerInfo}_<id>.json — 세종대로 1010005900·1010006000,
  사직로 1000012500 (2026-11-08 live 기록), links/20261107T154055_* — 서초대로 1210020200 등
기대값은 기록을 열어 확인한 값이다 (줄마다 주석).
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from naru_ai.ingest.incident import IncidentIngestor, LinkBook, parse_accinfo
from naru_contracts import (
    ClosureType,
    EvidenceKind,
    Impact,
    LineGeom,
    PointGeom,
    Source,
    Status,
)

KST = ZoneInfo("Asia/Seoul")
ACCINFO = "incident/20261107T154053_AccInfo.json"


@pytest.fixture(scope="module")
def accinfo(recorded_dir: Path) -> dict[str, str]:
    rec: dict[str, str] = json.loads((recorded_dir / ACCINFO).read_text("utf-8"))
    return rec


def test_parse_accinfo_rows_and_times(accinfo: dict[str, str]) -> None:
    rows = parse_accinfo(accinfo["raw"])
    assert len(rows) == 53  # <list_total_count>53
    by_id = {r.acc_id: r for r in rows}
    r = by_id["1109106"]  # "세종대로 (숭례문 ↔ 덕수궁) 집회로 양방향 전면통제"
    assert (r.acc_type, r.acc_dtype, r.link_id) == ("A10", "10B02", "1010006000")
    assert r.start == datetime(2026, 11, 7, 14, 44, tzinfo=KST)  # occr 20261107 · 1444 (HHMM)
    assert r.end == datetime(2026, 11, 7, 18, 0, tzinfo=KST)  # exp_clr 20261107 · 180000
    assert by_id["1108990"].start == datetime(2026, 11, 7, 15, 0, tzinfo=KST)  # 150000 (HHMMSS)
    assert r.info.startswith("세종대로 (숭례문 ↔ 덕수궁) 집회로 양방향 전면통제")


def test_rally_candidates_from_recorded_feed(accinfo: dict[str, str], recorded_dir: Path) -> None:
    rows = parse_accinfo(accinfo["raw"])
    received = datetime.fromisoformat(accinfo["called_at"])
    ingestor = IncidentIngestor(LinkBook(recorded_dir / "links"))
    built = ingestor.build(rows, f"data/recorded/{ACCINFO}", received)
    cands = {c.candidate_id: c for c in built}
    # 집회(10B02) 12건 중 1109001 "서울역광장 內(인도)" 는 보도 집회라 빼고(README impact),
    # 1108990·1108991·1108992 는 같은 링크·같은 시각(15:00~17:00 서울시의회~숭례문)이라 하나로.
    # 행사(차 없는 거리 1107882 등)·공사·기타(버스 무정차)·사고는 후보가 아니다
    ids = (1108983, 1108984, 1108989, 1108990, 1108999, 1109004, 1109026, 1109079, 1109106)
    assert set(cands) == {f"incident-{i}" for i in ids}
    c = cands["incident-1109106"]
    assert (c.source, c.type, c.impact, c.status_hint) == (
        Source.incident,
        ClosureType.rally,
        Impact.blocks,
        Status.scheduled,
    )
    assert c.confidence == 0.9 and not c.review_required
    assert (c.window.start, c.window.end) == (
        datetime(2026, 11, 7, 14, 44, tzinfo=KST),
        datetime(2026, 11, 7, 18, 0, tzinfo=KST),
    )
    assert isinstance(c.geometry, LineGeom)
    # LinkVerInfo 1010006000: 꼭짓점 4개, 첫 점 (197850, 451225) EPSG:5181 → pyproj 4326
    assert len(c.geometry.coordinates) == 4
    assert c.geometry.coordinates[0] == pytest.approx((126.9756661, 37.5605527), abs=1e-6)
    # LinkInfo 1010006000: road_name 세종대로, st_node_nm 숭례문 → ed_node_nm 시청역
    assert c.summary is not None
    assert [(s.from_, s.to) for s in c.summary.segments] == [("숭례문", "시청역")]
    assert c.summary.roads == ["세종대로"]
    (ev,) = c.evidence
    assert ev.kind is EvidenceKind.topis_incident
    assert ev.ref == f"data/recorded/{ACCINFO}#1109106"
    assert ev.at == received  # 수신 시각 2026-11-07T15:40:53+09:00 (data_as_of 의 topis_incident)
    group = cands["incident-1108990"]
    assert [e.ref.rsplit("#", 1)[1] for e in group.evidence] == ["1108990", "1108991", "1108992"]
    # 링크 기록이 없는 여의대로 1180002300 은 돌발 좌표 점 (grs80tm 193765.5, 447746.4 → 4326)
    far = cands["incident-1108989"]
    assert isinstance(far.geometry, PointGeom)
    assert far.geometry.coordinates == pytest.approx((126.9294672, 37.5291921), abs=1e-6)
