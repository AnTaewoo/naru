"""T6.2 — 버스 위치 파싱·노선 고르기·하루 상한 (ADR-013 D·G). 입력은 실제 기록만.

- bus/20261107T155630_getBusPosByRtid.json — 가이드 예시 노선 100100118, 12대 (T0.7)
- bus/20261108T183832_getBusPosByRtid_<노선>.json — 2026-11-08(일) 18:38 통제 없는 날,
  종로11 100900007 4대 · 종로09 100900003 5대 · 01A 100100001 7대 (live 3)
- raw/bus_routes_20261108/OA-1095.xlsx — 서울시 버스노선별 정류소(2026-09-02, 41,688행, WGS84)
- naru_api/closures_1107_1500.json — 11/7 15:00 광화문 /closures (r04 피처 38)
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from naru_ai.ingest.topis_api import LinkBook
from naru_ai.signal.bus_feed import BusApi, RoutePaths, parse_bus_positions
from naru_ai.signal.bus_poller import RouteStops

KST = ZoneInfo("Asia/Seoul")
DATA = Path(__file__).resolve().parents[3] / "data"


def _raw(recorded_dir: Path, name: str) -> str:
    return str(json.loads((recorded_dir / "bus" / name).read_text("utf-8"))["raw"])


def test_parse_recorded_positions(recorded_dir: Path) -> None:
    old = parse_bus_positions(_raw(recorded_dir, "20261107T155630_getBusPosByRtid.json"))
    assert len(old) == 12  # itemList 12대 (itemCount 는 0 으로 온다 — 믿지 않는다)
    p = old[0]  # vehId 111033056, dataTm 20261107155417, gpsX 126.912234, gpsY 37.614271
    assert (p.veh_id, p.plain_no) == ("111033056", "서울74사7236")
    assert p.data_tm == datetime(2026, 11, 7, 15, 54, 17, tzinfo=KST)
    assert (p.lng, p.lat, p.sect_ord, p.stop_flag, p.is_run) == (
        126.912234,
        37.614271,
        1,
        False,
        True,
    )
    a01 = parse_bus_positions(_raw(recorded_dir, "20261108T183832_getBusPosByRtid_100100001.json"))
    assert len(a01) == 7 and a01[0].veh_id == "106024536"  # INTERFACE §1.2 예시와 같은 차량
    assert (a01[0].section_id, a01[0].sect_dist, a01[0].next_st_id) == (
        "101600172",
        0.327,
        "101000117",
    )
    jongno11 = parse_bus_positions(
        _raw(recorded_dir, "20261108T183832_getBusPosByRtid_100900007.json")
    )
    # 마을버스는 nextStId "0"
    assert len(jongno11) == 4 and {q.next_st_id for q in jongno11} == {"0"}


@pytest.fixture(scope="module")
def stops() -> RouteStops:
    xlsx = DATA / "raw" / "bus_routes_20261108" / "OA-1095.xlsx"
    assert xlsx.exists(), "실데이터 없음: make fetch SRC=bus_routes"
    return RouteStops.load(xlsx)


def test_routes_near_rally_crosswalks(stops: RouteStops, recorded_dir: Path) -> None:
    body = json.loads((recorded_dir / "naru_api" / "closures_1107_1500.json").read_text("utf-8"))
    r04 = [
        tuple(f["geometry"]["coordinates"])
        for f in body["body"]["features"]
        if str(f["properties"]["reason"]).startswith("15:00~16:00 시의회~숭례문R")
    ]
    assert len(r04) == 38  # MANIFEST: r04 피처 38
    # 횡단보도 100 m 안 정류소(NODE_ID) 수 — 종로11 8 · 종로09 7 · 01A 6 (N·새벽 노선 뺌)
    assert stops.near(r04, 3) == ["100900007", "100900003", "100100001"]
    assert stops.near([], 3) == []
    # 심야·새벽 노선은 처음부터 뺌
    names = {s.route_id: s.route_name for s in stops.stops}
    assert not any(n.startswith(("N", "새벽")) for n in names.values())


def test_routes_near_incident_link(stops: RouteStops, recorded_dir: Path) -> None:
    # 돌발 1109106 "세종대로 (숭례문 ↔ 덕수궁) 집회로 양방향 전면통제" 의 링크 1010006000
    # (links/20261108T180400_LinkVerInfo_1010006000.json 꼭짓점 4개, 세종대로 숭례문→시청역)
    link = LinkBook(recorded_dir / "links").get("1010006000")
    assert link is not None and len(link.coords) == 4
    ranked = stops.near_line(link.coords)
    # 링크 100 m 안 정류소가 많은 순 — 172·402·472·1711 … 29개 (OA-1095 2026-09-02)
    assert ranked[:4] == ["100100037", "100100063", "100100075", "100100185"]
    assert len(ranked) == 29


def test_route_paths_go_to_raw_by_day() -> None:
    paths = RoutePaths(DATA / "raw")  # 키 없음 = 부르지 않는다
    at = datetime(2026, 11, 8, 19, 0, tzinfo=KST)
    expect = DATA / "raw" / "bus_routes" / "20261108" / "path_100100001.json"  # 태우 지시 경로
    assert paths.path("100100001", at) == expect
    assert paths.ensure("100100001", at) is None and not expect.exists()


def test_daily_cap_counts_recorded_calls(recorded_dir: Path) -> None:
    api = BusApi(recorded_dir)  # 키 없음 = 기록 재생
    assert not api.live
    day = datetime(2026, 11, 7, 20, 0, tzinfo=KST)
    assert api.calls_today(day) == 1  # 11/7 기록 1개 — 나누기 전(bus/ 바로 아래)이라 notice 로 센다
    assert (api.calls_today(day, "notice"), api.calls_today(day, "incident")) == (1, 0)
    legacy = api.call("100100118", "incident")  # incident 폴더에 없으면 나누기 전 기록을 재생
    assert legacy.path.name == "20261108T184839_getBusPosByRtid_100100118.json"
    with pytest.raises(ValueError):
        api.call("100100118", "bus")  # 폴더는 notice·incident 둘뿐
    rec = api.call("100900003")  # 그 노선의 가장 최근 기록
    assert rec.path.name == "20261108T183832_getBusPosByRtid_100900003.json"
    assert len(parse_bus_positions(rec.raw)) == 5
    with pytest.raises(FileNotFoundError):
        api.call("999999999")  # 기록 없는 노선은 지어내지 않는다
