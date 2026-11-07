"""T2.2 — CourseIngestor: 시각표 16구간 + 코스 GPX(풀·10 km) → ClosureCandidate 16개 (실데이터).

기대값은 2026-11-07 시각표 json과 GPX를 열어 확인한 값.
"""

import itertools
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from naru_ai.ingest.course import SEGMENT_LINES, CourseIngestor, Track
from naru_contracts import CandidateBatch, ClosureCandidate, LineGeom, Source, Status

SEOUL = (126.76, 37.41, 127.19, 37.72)
# 노드링크 노드 (fetch_course LEGS 구간 끝점): 세종대로사거리 1000009001, 숭례문앞교차로 1010013802
SEJONGDAERO_SAGEORI = (126.97712, 37.57023)
SUNGNYEMUN = (126.97576, 37.56051)


def _min_dist_m(points: list[tuple[float, float]], target: tuple[float, float]) -> float:
    kx = 111_320 * math.cos(math.radians(target[1]))
    return min(math.hypot((x - target[0]) * kx, (y - target[1]) * 110_574) for x, y in points)


def _length_m(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        kx = 111_320 * math.cos(math.radians((y0 + y1) / 2))
        total += math.hypot((x1 - x0) * kx, (y1 - y0) * 110_574)
    return total


@pytest.fixture(scope="module")
def candidates(course_dir: Path) -> list[ClosureCandidate]:
    return CourseIngestor().ingest(
        gpx=course_dir / "seoul_marathon_2026.gpx",
        timetable=course_dir / "seoul_marathon_2026_timetable.json",
        gpx_10km=course_dir / "seoul_marathon_2026_10km.gpx",
    )


def test_one_candidate_per_timetable_segment(
    candidates: list[ClosureCandidate], course_dir: Path
) -> None:
    timetable = json.loads((course_dir / "seoul_marathon_2026_timetable.json").read_text("utf-8"))
    assert len(candidates) == len(timetable["segments"]) == 16  # ROADMAP T2.2
    assert len({c.candidate_id for c in candidates}) == 16
    for c, seg in zip(candidates, timetable["segments"], strict=True):
        assert c.candidate_id == f"course-20260315-seg{seg['seq']:02d}"
        assert (
            c.source is Source.course and c.status_hint is Status.scheduled and c.type == "marathon"
        )
        assert c.confidence == 0.9 and c.review_required is False
        assert c.window.start == datetime.fromisoformat(
            seg["control_start"]
        )  # ROADMAP: window 일치
        assert c.window.end == datetime.fromisoformat(seg["control_end"])
        assert c.evidence[0].kind == "timetable" and c.evidence[0].ref.endswith(
            f"#segments/{seg['seq']}"
        )
        assert c.evidence[0].at == datetime.fromisoformat(timetable["published_at"])
        assert c.evidence[0].detail == {
            "label": seg["label"],
            "section": seg["section"],
            "course": SEGMENT_LINES[seg["label"]].course,
        }
        assert isinstance(c.geometry, LineGeom) and len(c.geometry.coordinates) >= 2
        assert all(
            SEOUL[0] < x < SEOUL[2] and SEOUL[1] < y < SEOUL[3] for x, y in c.geometry.coordinates
        )
        assert ClosureCandidate.model_validate(c.model_dump(mode="json")) == c


def test_segment_lines_cover_the_course(
    candidates: list[ClosureCandidate], course_dir: Path
) -> None:
    by_label: dict[str, ClosureCandidate] = {}
    for c in candidates:
        detail = c.evidence[0].detail
        assert detail is not None
        by_label[str(detail["label"])] = c
    seg1 = by_label["1구간"].geometry
    assert isinstance(seg1, LineGeom)
    assert _min_dist_m(seg1.coordinates, SEJONGDAERO_SAGEORI) < 10  # 세종대로 사거리~숭례문 오거리
    assert _min_dist_m(seg1.coordinates, SUNGNYEMUN) < 10
    assert 1000 < _length_m(seg1.coordinates) < 1300  # T0.4 디지타이즈 구간 1.10 km
    # 출발지 + 1~11구간 조각을 이으면 풀코스 트랙 전체 (42.53 km) 가 된다
    full = Track.load(course_dir / "seoul_marathon_2026.gpx")
    full_labels = ["출발지", *[f"{i}구간" for i in range(1, 12)]]
    pieces = 0.0
    for lbl in full_labels:
        g = by_label[lbl].geometry
        assert isinstance(g, LineGeom)
        pieces += _length_m(list(g.coordinates))
    assert abs(pieces - _length_m(list(full.points))) < 50
    # 12·13구간은 송파대로(잠실역 ↔ 가락시장) 왕복, 14·15구간은 종합운동장 쪽
    for lbl in ("12구간", "13구간"):
        g = by_label[lbl].geometry
        assert isinstance(g, LineGeom)
        xs = [x for x, _ in g.coordinates]
        ys = [y for _, y in g.coordinates]
        assert min(xs) > 127.09 and max(xs) < 127.125 and min(ys) > 37.488 and max(ys) < 37.516
        assert 2500 < _length_m(g.coordinates) < 3500
    g15 = by_label["15구간"].geometry
    assert (
        isinstance(g15, LineGeom) and 150 < _length_m(g15.coordinates) < 500
    )  # 동문 앞~종합운동장 사거리


def test_recorded_course_batch(recorded_dir: Path) -> None:
    files = sorted((recorded_dir / "candidates" / "course").glob("*.json"))
    assert files, "기록 없음: make record-candidates SOURCE=course 먼저"
    batch = CandidateBatch.model_validate(json.loads(files[-1].read_text("utf-8")))
    assert batch.producer == "course" and len(batch.candidates) == 16
    assert batch.produced_at.utcoffset() is not None
