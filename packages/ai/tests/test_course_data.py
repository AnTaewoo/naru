"""T0.4 — 2026 서울마라톤 코스 GPX(디지타이즈)와 구간별 통제 시각표 (실데이터).

기대값은 2026-11-07에 서울시 기사(mediahub 2017411)·포스터와 산출 파일을 열어 확인한 값.
"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import gpxpy

OFFICIAL_KM = 42.195
# 세종대로사거리 — nodelink_seoul 노드 1000009001 (NODE_NAME '세종대로사거리', 2026-11-07 확인)
SEJONGDAERO_SAGEORI = (126.97712, 37.57023)
# 고산자교 U턴 지점 — nodelink 노드 1030035203 (청계천로와 고산자로가 만나는 '시설관리공단교차로')
GOSANJA_BRIDGE = (127.03787, 37.57173)


def _min_dist_m(points: list[tuple[float, float]], target: tuple[float, float]) -> float:
    """등장방형 근사 (서울 위도에서 수 km 이내면 충분)."""
    lng0, lat0 = target
    kx = 111_320 * math.cos(math.radians(lat0))
    ky = 110_574
    return min(math.hypot((lng - lng0) * kx, (lat - lat0) * ky) for lng, lat in points)


def test_gpx_is_a_full_marathon_through_sejongdaero(course_dir: Path) -> None:
    gpx = gpxpy.parse((course_dir / "seoul_marathon_2026.gpx").read_text("utf-8"))
    pts = [(p.longitude, p.latitude) for t in gpx.tracks for s in t.segments for p in s.points]
    assert len(pts) > 500
    km = gpx.length_2d() / 1000
    # ROADMAP T0.4: 42.195 km ± 2%. 디지타이즈 결과 42.53 km (course_meta.json, 2026-11-07)
    assert abs(km - OFFICIAL_KM) / OFFICIAL_KM < 0.02, km
    assert _min_dist_m(pts, SEJONGDAERO_SAGEORI) < 15  # 코스가 세종대로사거리를 지난다
    assert _min_dist_m(pts, GOSANJA_BRIDGE) < 15  # 청계천로 끝 U턴
    names = " ".join(w.name or "" for w in gpx.waypoints)
    assert "세종대로사거리" in names and "잠실대교" in names
    meta = json.loads((course_dir / "seoul_marathon_2026_course_meta.json").read_text("utf-8"))
    assert len(meta["legs"]) == 17 and not any(leg["fallback_full_graph"] for leg in meta["legs"])


def test_timetable_segments_have_sources(course_dir: Path) -> None:
    tt = json.loads((course_dir / "seoul_marathon_2026_timetable.json").read_text("utf-8"))
    assert tt["event"]["date"] == "2026-03-15"  # 기사 표 머리글 "2026 서울마라톤(3.15)"
    segs = tt["segments"]
    assert len(segs) >= 4  # ROADMAP T0.4
    assert len(segs) == 16  # 출발지 + 1~15구간 (기사 표, 2026-11-07)
    for s in segs:
        start = datetime.fromisoformat(s["control_start"])
        end = datetime.fromisoformat(s["control_end"])
        assert start.utcoffset() == timedelta(hours=9) and start < end, s
        assert start.date().isoformat() == "2026-03-15"
        assert s["source_url"].startswith("https://mediahub.seoul.go.kr/archives/")
        assert s["published_at"] == "2026-03-12T16:07:00+09:00"  # 기사 발행일
        assert s["fetched_at"]
    # 1구간 세종대로 사거리~숭례문 오거리 07:20~08:08 (기사 표)
    assert segs[1]["section"] == "세종대로 사거리~숭례문 오거리"
    assert segs[1]["control_start"] == "2026-03-15T07:20:00+09:00"
    assert segs[1]["control_end"] == "2026-03-15T08:08:00+09:00"
    assert segs[0]["label"] == "출발지" and segs[15]["label"] == "15구간"
