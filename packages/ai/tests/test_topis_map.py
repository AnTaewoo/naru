"""T7.3 TOPIS 교통통제 지도 예정 통제 (ADR-014 B) — T6.5 기록으로.

- 목록 recorded topis_web/20261109T083719_selectAccAllListASC.json (11/9 08:37, 6행): 예정(N) 3 —
  1107885 덕수궁길 차 없는 거리(행사 10B03), 1109233 국회대로 집회(10B02, 11:00~15:30, 부분 통제),
  1109234 강남대로 집회(10B02, 14:00~15:30) — 통제 중(Y) 3 — 봉은교·탄천동로 공사,
  남이장군사당제(기타)
- 통제 도로 topis_web/20261109T084734_selectAccLinkList_1109233.json (19 링크, 도로 10개)
- 링크 꼭짓점 recorded links/*_LinkVerInfo_<id>.json (OA-13311 — 17개는 2026-11-09 18:2x 기록)
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString

from naru_ai.ingest.topis_api import LinkBook
from naru_ai.ingest.topis_map import (
    TopisMapFeed,
    TopisMapIngestor,
    chains,
    next_request,
    parse_controls,
    parse_links,
)
from naru_contracts import ClosureType, EvidenceKind, LineGeom, Source

KST = timezone(timedelta(hours=9))
LIST = "topis_web/20261109T083719_selectAccAllListASC.json"
LINKS = "topis_web/20261109T084734_selectAccLinkList_1109233.json"
ROUTE = ["국회대로", "여의서로", "여의대로", "마포대로", "신촌로", "충정로", "새문안로", "세종대로"]
ROUTE += ["사직로", "효자로"]


def _raw(recorded_dir: Path, name: str) -> str:
    return str(json.loads((recorded_dir / name).read_text("utf-8"))["raw"])


def test_controls_and_targets(recorded_dir: Path) -> None:
    controls = parse_controls(_raw(recorded_dir, LIST))
    assert [(c.acc_id, c.live) for c in controls] == [
        ("1107885", False),
        ("1109233", False),
        ("1109234", False),
        ("1071788", True),
        ("1071792", True),
        ("1108643", True),
    ]
    targets = TopisMapIngestor.targets(controls)  # 예정 집회만 — 행사·공사·기타·통제 중은 빼고
    assert [c.acc_id for c in targets] == ["1109233", "1109234"]
    c = targets[0]
    assert (c.start, c.end) == (
        datetime(2026, 11, 9, 11, 0, tzinfo=KST),
        datetime(2026, 11, 9, 15, 30, tzinfo=KST),
    )
    assert c.full is False and c.link_id == "1180036500"  # '부분 통제', 대표 링크 국회대로
    # 원문의 물결은 U+223C TILDE OPERATOR 그대로
    assert c.info.startswith(
        "- 11:00\u223c15:30 의사당역 2出 앞(1개차로)→청와대 사랑채 동측 건너편"
    )


def test_links_chain_into_one_route(recorded_dir: Path) -> None:
    (route,) = chains(parse_links(_raw(recorded_dir, LINKS)))  # 노드 이름으로 이으면 한 줄
    assert len(route) == 19
    assert (route[0].start_name, route[-1].end_name) == ("국회의사당앞", "효자동삼거리")
    roads: list[str] = []
    for link in route:
        if link.road not in roads:
            roads.append(link.road)
    assert roads == ROUTE


def test_candidates(recorded_dir: Path) -> None:
    controls = parse_controls(_raw(recorded_dir, LIST))
    links = {"1109233": parse_links(_raw(recorded_dir, LINKS))}
    fetched = datetime(2026, 11, 9, 8, 37, 19, tzinfo=KST)
    ingestor = TopisMapIngestor(LinkBook(recorded_dir / "links"))
    got = {c.candidate_id: c for c in ingestor.build(controls, links, LIST, fetched)}
    # 1109233 은 통제 도로 19 링크를 이은 선 하나, 1109234 는 통제 도로를 아직 안 받아
    # 대표 링크 하나
    assert list(got) == ["topismap-1109233-0", "topismap-1109234-0"]
    march = got["topismap-1109233-0"]
    assert isinstance(march.geometry, LineGeom)
    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True).transform
    line = LineString([to5179(*p) for p in march.geometry.coordinates])
    # 국회의사당앞~효자동삼거리 9,489 m — 공지 accInfo 의 '9.5km 행진'(의사당역~사랑채)과 맞다
    assert round(line.length) == 9489
    assert (march.source, march.type, march.confidence) == (Source.topis, ClosureType.march, 0.85)
    assert march.evidence[0].kind is EvidenceKind.notice
    assert march.evidence[0].ref == f"{LIST}#acc-1109233"
    assert march.notice_ref is not None and march.notice_ref.notice_id == "topismap-1109233"
    assert march.summary is not None and march.summary.roads == ROUTE
    (seg,) = march.summary.segments
    assert (seg.from_, seg.to) == ("국회의사당앞", "효자동삼거리")
    assert seg.via == [  # 도로가 바뀌는 곳
        "서강대교남단",
        "마포대교남단",
        "마포대교북단",
        "아현교차로",
        "충정로사거리",
        "서대문역",
        "세종대로사거리",
        "광화문",
        "정부서울청사",
    ]
    rally = got["topismap-1109234-0"]
    assert rally.type is ClosureType.march  # '※행진: 논현역→…→교대역 7出'
    assert isinstance(rally.geometry, LineGeom) and rally.summary is not None
    # 통제 도로가 없으면 대표 링크 이름 — links LinkInfo_1220027800(강남대로
    # 논현역~교보타워사거리)
    assert [(x.from_, x.to) for x in rally.summary.segments] == [("논현역", "교보타워사거리")]
    assert rally.summary.roads == ["강남대로"]


def test_next_request() -> None:
    # 같은 곳(topis.seoul.go.kr)은 한 번에 요청 하나 — 목록과 아직 없는 통제 도로를 번갈아
    assert next_request(None, ["1109234"]) == "list"
    assert next_request("list", ["1109234"]) == "1109234"
    assert next_request("links", ["1109234"]) == "list"
    assert next_request("list", []) == "list"


def test_feed_recorded(recorded_dir: Path) -> None:
    feed = TopisMapFeed(recorded_dir, live=False, pinned=recorded_dir / LIST)
    got = feed.controls()
    assert got is not None
    controls, ref, fetched = got
    assert len(controls) == 6 and ref.endswith(LIST)
    assert fetched == datetime(2026, 11, 9, 8, 37, 19, tzinfo=KST)
    found = feed.links_of("1109233")
    assert found is not None and len(found) == 19
    assert feed.links_of("1109234") is None  # T6.5 는 1109233 통제 도로만 받았다
