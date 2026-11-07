"""2026 서울마라톤 코스·통제 시각표 수집 CLI — `make fetch SRC=course` (ROADMAP T0.4).

산출 (data/raw/course/):
  seoul_marathon_2026_timetable.json    구간별 통제·해제 시각 (서울시 '내 손안에 서울' 기사 표 파싱)
  seoul_marathon_2026_mediahub.html     그 기사 원문 바이트 (증거)
  seoul_marathon_2026_poster.jpg        서울시 교통통제 안내 포스터 (코스 설명 문장 + 같은 표)
  seoul_marathon_2026.gpx               코스 폴리라인 (디지타이즈)
  seoul_marathon_2026_course_meta.json  디지타이즈 기록 (구간별 노드·도로·길이·폴백)

공식 GPX는 없다 (seoul-marathon.com 코스도는 이미지뿐). 그래서 포스터의 코스 설명 순서
  이순신동상 앞(출발) → 남대문 → 을지로1가 → 동대문역사문화공원 → 시청삼거리 → 청계천로
  → 고산자교(U턴) → 모전교 → 종로구청입구 → 종로 → 신설동 → 천호대로 → 군자역
  → 어린이대공원역 → 광나루로 → 성동교 → 서울숲 → 잠실대교 → 잠실역 → 잠실종합운동장(도착)
를 표준노드링크 서울 추출본(nodelink_seoul_<date>)의 교차로 노드로 옮기고,
구간마다 그 도로명 링크만으로 최단경로를 이어 붙인다.
결과 길이가 42.195 km ±2%여야 한다 (테스트). 코스 지도의 km 표지와 대조함.
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import geopandas as gpd
import gpxpy
import gpxpy.gpx
import httpx
import networkx as nx

log = logging.getLogger("fetch_course")
KST = timezone(timedelta(hours=9))

MEDIAHUB_URL = "https://mediahub.seoul.go.kr/archives/2017411"
NOTICE_URL = "https://news.seoul.go.kr/culture/archives/531848"
POSTER_URL = "https://news.seoul.go.kr/culture/files/2026/03/69abc0050fb8b8.44799486.jpg"
LICENSE = "공공누리 제4유형 (출처표시·상업적 이용 금지·변경 금지) — 기사 하단 표기"
EVENT = {
    "name": "2026 서울마라톤",
    "start": "광화문광장",
    "finish": "잠실종합운동장(동문)",
    "start_time": "07:30",  # 기사: "오전 7시 30분 출발"
    "official_site": "https://www.seoul-marathon.com",
}
OFFICIAL_LENGTH_KM = 42.195

# 디지타이즈 구간 (설명, 시작 노드, 끝 노드, 허용 도로명).
# 노드 ID는 nodelink_seoul의 NODE_NAME 또는 두 도로명 링크가 공유하는 노드로 찾음 (2026-11-07).
# 허용 도로명만으로 길이 없으면 전체 그래프로 폴백하고 meta에 남긴다
LEGS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "출발 광화문광장 미국대사관 앞 → 세종대로사거리",
        "1000013704",
        "1000009001",
        ("세종대로", "일반국도48호선", "종로"),
    ),
    (
        "세종대로사거리 → 숭례문앞교차로",
        "1000009001",
        "1010013802",
        ("세종대로", "일반국도48호선", "소공로", "소월로"),
    ),
    (
        "숭례문앞교차로 → 을지로1가사거리",
        "1010013802",
        "1010027601",
        ("남대문로", "세종대로", "소월로"),
    ),
    (
        "을지로1가사거리 → 동대문역사문화공원앞교차로",
        "1010027601",
        "1010027501",
        ("을지로", "남대문로"),
    ),
    (
        "동대문역사문화공원앞교차로 → 청계6가사거리",
        "1010027501",
        "1010034701",
        ("장충단로", "을지로"),
    ),
    ("청계6가사거리 → 청계광장(시청삼거리)", "1010034701", "1000031000", ("청계천로", "장충단로")),
    ("청계광장 → 고산자교(시설관리공단교차로)", "1000031000", "1030035203", ("청계천로",)),
    ("고산자교 U턴 → 무교동사거리(모전교)", "1030035203", "1010034101", ("청계천로", "고산자로")),
    ("무교동사거리 → 종로구청입구교차로", "1010034101", "1000008606", ("무교로", "청계천로")),
    (
        "종로구청입구교차로 → 신설동역교차로",
        "1000008606",
        "1000001305",
        ("종로", "무교로", "왕산로"),
    ),
    ("신설동역교차로 → 군자역사거리", "1000001305", "1040001901", ("왕산로", "천호대로", "종로")),
    ("군자역사거리 → 어린이대공원역교차로", "1040001901", "1040021501", ("능동로", "천호대로")),
    ("어린이대공원역교차로 → 성동교사거리", "1040021501", "1030020502", ("광나루로", "능동로")),
    (
        "성동교사거리 → 서울숲입구교차로",
        "1030020502",
        "1030010201",
        ("왕십리로", "고산자로", "광나루로", "뚝섬로"),
    ),
    ("서울숲입구교차로 → 잠실대교북단앞교차로", "1030010201", "1040008101", ("뚝섬로", "왕십리로")),
    (
        "잠실대교북단앞교차로 → 잠실대교 → 잠실역사거리",
        "1040008101",
        "1230001801",
        ("자양로", "송파대로", "뚝섬로"),
    ),
    (
        "잠실역사거리 → 종합운동장역(동문, 도착)",
        "1230001801",
        "1230188204",
        ("올림픽로", "송파대로"),
    ),
)


class _Text(HTMLParser):
    """script/style를 뺀 보이는 글자만 줄 단위로 모은다."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = " ".join(data.split())
            if text:
                self.lines.append(text)


def page_lines(html: bytes) -> list[str]:
    p = _Text()
    p.feed(html.decode("utf-8", errors="replace"))
    return p.lines


def parse_timetable(lines: list[str], fetched_at: str) -> dict[str, object]:
    """기사 표 '구간 / 통제~해제시간' → segments. 표 머리글에서 월·일, 발행일에서 published_at."""
    head = next(line for line in lines if "구간별 교통 통제·해제 시간" in line)
    m = re.search(r"서울마라톤\((\d{1,2})\.(\d{1,2})\)", head)
    year = re.search(r"(20\d\d) 서울마라톤", head)
    if not (m and year):
        raise SystemExit(f"표 머리글에서 날짜를 못 읽음: {head}")
    date = f"{year.group(1)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    pub = lines[lines.index("발행일") + 1]  # 예: 2026.03.12. 16:07
    pm = re.match(r"(\d{4})\.(\d{2})\.(\d{2})\. (\d{2}):(\d{2})", pub)
    if not pm:
        raise SystemExit(f"발행일을 못 읽음: {pub}")
    y, mo, d, hh, mm = (int(v) for v in pm.groups())
    published_at = datetime(y, mo, d, hh, mm, tzinfo=KST).isoformat()

    i = lines.index(head) + 1
    segments: list[dict[str, object]] = []
    time_re = re.compile(r"^(\d{2}):(\d{2})~(\d{2}):(\d{2})$")
    while i + 2 < len(lines):
        label, section, span = lines[i], lines[i + 1], lines[i + 2]
        tm = time_re.match(span)
        if not (re.match(r"^(출발지|\d+구간)$", label) and tm):
            if segments:
                break
            i += 1
            continue
        h1, m1, h2, m2 = (int(v) for v in tm.groups())
        segments.append(
            {
                "seq": len(segments),
                "label": label,
                "section": section,
                "control_start": f"{date}T{h1:02d}:{m1:02d}:00+09:00",
                "control_end": f"{date}T{h2:02d}:{m2:02d}:00+09:00",
                "source_url": MEDIAHUB_URL,
                "published_at": published_at,
                "fetched_at": fetched_at,
            }
        )
        i += 3
    if len(segments) < 4:
        raise SystemExit(f"구간이 {len(segments)}개뿐 — 기사 표 구조가 바뀌었는지 확인")
    return {
        "event": {**EVENT, "date": date},
        "source_url": MEDIAHUB_URL,
        "notice_url": NOTICE_URL,
        "poster_url": POSTER_URL,
        "published_at": published_at,
        "fetched_at": fetched_at,
        "license": LICENSE,
        "segments": segments,
    }


def latest_nodelink(raw: Path) -> Path:
    dirs = sorted(raw.glob("nodelink_seoul_*"))
    if not dirs:
        raise SystemExit("표준노드링크 추출본 없음 — make fetch SRC=nodelink 먼저 (T0.3)")
    return dirs[-1]


def digitize(nodelink_dir: Path) -> tuple[list[tuple[float, float]], list[dict[str, object]]]:
    """LEGS를 도로명 제한 최단경로로 이어 WGS84 좌표열과 구간 기록을 돌려준다."""
    nodes = gpd.read_file(nodelink_dir / "node.gpkg")
    links = gpd.read_file(nodelink_dir / "link.gpkg").to_crs(4326)
    pos = {r.NODE_ID: (r.geometry.x, r.geometry.y) for r in nodes.to_crs(4326).itertuples()}
    road = links["ROAD_NAME"].fillna("")

    def graph(allowed: tuple[str, ...] | None) -> nx.Graph:
        g = nx.Graph()
        sub = links if allowed is None else links[road.isin(allowed)]
        for r in sub.itertuples():
            w = float(r.LENGTH)
            if not g.has_edge(r.F_NODE, r.T_NODE) or g[r.F_NODE][r.T_NODE]["w"] > w:
                g.add_edge(r.F_NODE, r.T_NODE, w=w, geom=r.geometry, road=r.ROAD_NAME or "")
        return g

    full = graph(None)
    coords: list[tuple[float, float]] = []
    records: list[dict[str, object]] = []
    for title, a, b, allowed in LEGS:
        g, fallback = graph(allowed), False
        try:
            path = nx.shortest_path(g, a, b, weight="w")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            g, fallback = full, True
            path = nx.shortest_path(g, a, b, weight="w")
        length = 0.0
        roads: list[str] = []
        for u, v in itertools.pairwise(path):
            e = g[u][v]
            pts = list(e["geom"].coords)
            if abs(pts[0][0] - pos[u][0]) + abs(pts[0][1] - pos[u][1]) > abs(
                pts[-1][0] - pos[u][0]
            ) + abs(pts[-1][1] - pos[u][1]):
                pts.reverse()
            for p in pts:
                if not coords or coords[-1] != (p[0], p[1]):
                    coords.append((p[0], p[1]))
            length += e["w"]
            if not roads or roads[-1] != e["road"]:
                roads.append(e["road"])
        records.append(
            {
                "leg": title,
                "from_node": a,
                "to_node": b,
                "allowed_roads": list(allowed),
                "roads_used": roads,
                "length_m": round(length, 1),
                "fallback_full_graph": fallback,
            }
        )
        log.info("%6.2f km %s%s", length / 1000, title, " (폴백)" if fallback else "")
    return coords, records


def write_gpx(
    path: Path,
    coords: list[tuple[float, float]],
    records: list[dict[str, object]],
    pos_of: dict[str, tuple[float, float]],
) -> None:
    gpx = gpxpy.gpx.GPX()
    gpx.name = f"{EVENT['name']} 풀코스 (디지타이즈)"
    gpx.description = (
        "표준노드링크 서울 추출본 위에서 공식 코스 설명 순서대로 이은 선. 출처는 _course_meta.json"
    )
    track = gpxpy.gpx.GPXTrack(name=gpx.name)
    seg = gpxpy.gpx.GPXTrackSegment()
    seg.points = [gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lng) for lng, lat in coords]
    track.segments.append(seg)
    gpx.tracks.append(track)
    for rec in records:
        node = str(rec["from_node"])
        lng, lat = pos_of[node]
        gpx.waypoints.append(gpxpy.gpx.GPXWaypoint(lat, lng, name=str(rec["leg"]).split(" → ")[0]))
    last = str(records[-1]["to_node"])
    gpx.waypoints.append(
        gpxpy.gpx.GPXWaypoint(pos_of[last][1], pos_of[last][0], name="도착 종합운동장역(동문)")
    )
    path.write_text(gpx.to_xml(), "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="2026 서울마라톤 코스·시각표 수집 (T0.4)")
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    out = args.raw / "course"
    out.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(KST).isoformat(timespec="seconds")

    with httpx.Client(
        timeout=60.0, follow_redirects=True, headers={"User-Agent": "naru-fetch/0.5"}
    ) as client:
        html_path = out / "seoul_marathon_2026_mediahub.html"
        if not html_path.exists():
            r = client.get(MEDIAHUB_URL)
            r.raise_for_status()
            html_path.write_bytes(r.content)
        poster = out / "seoul_marathon_2026_poster.jpg"
        if not poster.exists():
            r = client.get(POSTER_URL)
            r.raise_for_status()
            poster.write_bytes(r.content)
    timetable = parse_timetable(page_lines(html_path.read_bytes()), fetched_at)
    (out / "seoul_marathon_2026_timetable.json").write_text(
        json.dumps(timetable, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    log.info("시각표 %d구간 (%s)", len(timetable["segments"]), timetable["event"]["date"])  # type: ignore[arg-type,index]

    nodelink_dir = latest_nodelink(args.raw)
    coords, records = digitize(nodelink_dir)
    nodes = gpd.read_file(nodelink_dir / "node.gpkg").to_crs(4326)
    pos_of = {r.NODE_ID: (r.geometry.x, r.geometry.y) for r in nodes.itertuples()}
    write_gpx(out / "seoul_marathon_2026.gpx", coords, records, pos_of)
    total_m = sum(float(r["length_m"]) for r in records)
    meta = {
        "fetched_at": fetched_at,
        "method": "포스터 코스 설명 순서로 교차로 노드를 잇는 도로명 제한 최단경로 (무방향)",
        "sources": {"poster": POSTER_URL, "notice": NOTICE_URL, "article": MEDIAHUB_URL},
        "nodelink_dir": str(nodelink_dir),
        "official_length_km": OFFICIAL_LENGTH_KM,
        "digitized_length_km": round(total_m / 1000, 3),
        "deviation_pct": round(100 * (total_m / 1000 / OFFICIAL_LENGTH_KM - 1), 2),
        "points": len(coords),
        "legs": records,
    }
    (out / "seoul_marathon_2026_course_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    log.info(
        "코스 %.3f km (공식 %.3f, %+.1f%%), 점 %d개 → %s",
        total_m / 1000,
        OFFICIAL_LENGTH_KM,
        meta["deviation_pct"],
        len(coords),
        out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
