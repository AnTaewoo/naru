"""CourseIngestor — 마라톤 코스 GPX + 구간별 통제 시각표 → ClosureCandidate (ARCHITECTURE AI, T2.2).

입력 (T0.4, data/raw/course/):
  seoul_marathon_2026_timetable.json  구간 16개 (출발지 + 1~15구간) — 통제·해제 시각, 출처
  seoul_marathon_2026.gpx             풀코스 (웨이포인트 = 디지타이즈 구간 시작점)
  seoul_marathon_2026_10km.gpx        10 km 코스 (12·13·14·15구간은 여기 위에 있다)
후보 하나 = 시각표 구간 하나. geometry는 그 구간을 덮는 GPX 조각(line), status_hint=scheduled,
confidence 0.9, evidence kind=timetable. 모델(LLM)은 안 쓴다. 좌표는 전부 GPX에서 온다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import gpxpy
import gpxpy.gpx

from naru_contracts import (
    ClosureCandidate,
    Evidence,
    EvidenceKind,
    LineGeom,
    Source,
    Status,
    Window,
)
from naru_contracts.enums import ClosureType

LngLat = tuple[float, float]
COURSE_CONFIDENCE = 0.9  # 주최측 시각표 — 공지보다 확실하고 실측(confirmed)보다는 낮다
WAYPOINT_SNAP_M = 10.0  # 웨이포인트는 트랙 꼭짓점이라 0 m 여야 한다. 여유 10 m


@dataclass(frozen=True)
class SegmentLine:
    """시각표 구간 → (코스, 시작·끝 웨이포인트). 시작 웨이포인트가 몇 번째 등장인지도 센다."""

    course: str  # "full" | "10km"
    start: str
    end: str
    start_occurrence: int = 1


# 시각표 label → GPX 조각. 웨이포인트 이름 = scripts/fetch_course.py LEGS·LEGS_10K 의 구간 시작 이름
SEGMENT_LINES: dict[str, SegmentLine] = {
    "출발지": SegmentLine("full", "출발 광화문광장 미국대사관 앞", "세종대로사거리"),
    "1구간": SegmentLine("full", "세종대로사거리", "숭례문앞교차로"),
    "2구간": SegmentLine("full", "숭례문앞교차로", "청계광장"),
    "3구간": SegmentLine("full", "청계광장", "무교동사거리"),
    "4구간": SegmentLine("full", "무교동사거리", "신설동역교차로"),
    "5구간": SegmentLine("full", "신설동역교차로", "군자역사거리"),
    "6구간": SegmentLine("full", "군자역사거리", "어린이대공원역교차로"),
    "7구간": SegmentLine("full", "어린이대공원역교차로", "성동교사거리"),
    "8구간": SegmentLine("full", "성동교사거리", "서울숲입구교차로"),
    "9구간": SegmentLine("full", "서울숲입구교차로", "잠실대교북단앞교차로"),
    "10구간": SegmentLine("full", "잠실대교북단앞교차로", "잠실역사거리"),
    "11구간": SegmentLine("full", "잠실역사거리", "도착 종합운동장역(동문)"),
    "12구간": SegmentLine("10km", "잠실역사거리", "가락시장역사거리 U턴"),  # 송파대로 바깥쪽
    "13구간": SegmentLine("10km", "가락시장역사거리 U턴", "잠실역사거리"),  # 송파대로 안쪽
    "14구간": SegmentLine("10km", "출발 종합운동장역(동문)", "잠실역사거리"),
    "15구간": SegmentLine("10km", "종합운동장교차로", "출발 종합운동장역(동문)"),  # 동문 앞~사거리
}


@dataclass(frozen=True)
class Track:
    points: tuple[LngLat, ...]
    waypoints: tuple[tuple[str, LngLat], ...]  # (이름, 좌표) GPX 순서

    @classmethod
    def load(cls, path: Path) -> Track:
        gpx = gpxpy.parse(path.read_text("utf-8"))
        points = tuple(
            (p.longitude, p.latitude) for t in gpx.tracks for s in t.segments for p in s.points
        )
        waypoints = tuple((w.name or "", (w.longitude, w.latitude)) for w in gpx.waypoints)
        return cls(points, waypoints)

    def index_of(self, name: str, occurrence: int = 1, after: int = 0) -> int:
        """`occurrence`번째 그 이름 웨이포인트에 가장 가까운 트랙 점 인덱스 (after 이후)."""
        seen = 0
        for wp_name, xy in self.waypoints:
            if wp_name != name:
                continue
            seen += 1
            if seen < occurrence:
                continue
            best = min(range(after, len(self.points)), key=lambda i: _dist_m(self.points[i], xy))
            if _dist_m(self.points[best], xy) > WAYPOINT_SNAP_M:
                raise ValueError(f"웨이포인트 '{name}'가 트랙에서 {WAYPOINT_SNAP_M} m 밖")
            return best
        raise ValueError(f"웨이포인트 없음: {name} (#{occurrence})")

    def slice(self, line: SegmentLine) -> tuple[LngLat, ...]:
        i = self.index_of(line.start, line.start_occurrence)
        j = self.index_of(line.end, 1, after=i + 1)
        return self.points[i : j + 1]


def _dist_m(a: LngLat, b: LngLat) -> float:
    kx = 111_320 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 110_574)


class CourseIngestor:
    def __init__(self, confidence: float = COURSE_CONFIDENCE) -> None:
        self.confidence = confidence

    def ingest(
        self, gpx: Path, timetable: Path, gpx_10km: Path | None = None
    ) -> list[ClosureCandidate]:
        data = json.loads(timetable.read_text("utf-8"))
        tracks = {"full": Track.load(gpx)}
        if gpx_10km is not None:
            tracks["10km"] = Track.load(gpx_10km)
        event_date = str(data["event"]["date"]).replace("-", "")
        published_at = datetime.fromisoformat(data["published_at"])
        ref_base = f"{timetable.as_posix()}#segments"
        out: list[ClosureCandidate] = []
        for seg in data["segments"]:
            line = SEGMENT_LINES.get(seg["label"])
            if line is None:
                raise ValueError(f"시각표 구간에 GPX 조각이 없다: {seg['label']} {seg['section']}")
            if line.course not in tracks:
                raise ValueError(f"{seg['label']}: {line.course} GPX가 없다")
            coords = tracks[line.course].slice(line)
            # 12·13구간은 송파대로 왕복 — 13구간 끝은 잠실역사거리의 두 번째 등장
            out.append(
                ClosureCandidate(
                    candidate_id=f"course-{event_date}-seg{int(seg['seq']):02d}",
                    source=Source.course,
                    type=ClosureType.marathon,
                    status_hint=Status.scheduled,
                    geometry=LineGeom(coordinates=list(coords)),
                    window=Window(
                        start=datetime.fromisoformat(seg["control_start"]),
                        end=datetime.fromisoformat(seg["control_end"]),
                    ),
                    confidence=self.confidence,
                    evidence=[
                        Evidence(
                            kind=EvidenceKind.timetable,
                            ref=f"{ref_base}/{seg['seq']}",
                            at=published_at,
                            detail={
                                "label": seg["label"],
                                "section": seg["section"],
                                "course": line.course,
                            },
                        )
                    ],
                    review_required=False,
                )
            )
        return out
