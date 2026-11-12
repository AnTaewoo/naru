"""노선 경로(RoutePath) — getRoutePath 를 노선 위 거리로, 버스 위치·통제 횡단보도를 노선 위에.

확신도 보정은 뺐다(ADR-013 보류, 태우 2026-11-09) — 보정 순수 함수의 테스트도 같이 뺐다.
실데이터:
- 노선 경로 raw bus_routes/20261109/path_<노선>.json — getRoutePath 2026-11-09 07:5x 8노선
- 버스 위치 recorded bus/20261108T18*_getBusPosByRtid_<노선>.json — 2026-11-08(일) 18:38~18:48,
  T6.2 가 11/7 공지 창으로 고른 8노선 94대
- 횡단보도 OA-23081 — TOPIS 6300 세종대로 7곳(test_e2e_worker)
"""

import json
import math
import statistics
from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.bus_route import RoutePath, to_5179
from naru_be.models.domain.crosswalk_index import CrosswalkIndex

DATA = Path(__file__).resolve().parents[3] / "data"
ROUTES = DATA / "raw" / "bus_routes" / "20261109"
T63_ROUTES = (
    "100100001",
    "100100033",
    "100100042",
    "100100046",
    "100100118",
    "100100185",
    "100900003",
    "100900007",
)
# TOPIS 6300 세종대로 7곳 — 숭례문 23254·23247, 삼성본관 45236, 시청 40204, 덕수궁앞 40206,
# 프레스센터 42121, 세종대로사거리 23206 (OA-23081 교차로명)
SEJONG = [f"06-00000{n}" for n in (23254, 23247, 45236, 40204, 40206, 42121, 23206)]


@pytest.fixture(scope="module")
def routes() -> dict[str, RoutePath]:
    # 이 폴더엔 운영 워커도 그날 노선 경로를 받는다(ADR-013 I, 11/9 11:04 100100032·100100567) —
    # 07:56 에 받은 8노선만 (ls 로 확인)
    paths = [ROUTES / f"path_{r}.json" for r in T63_ROUTES]
    assert all(p.exists() for p in paths), "getRoutePath 기록 없음 — MANIFEST raw bus_routes"
    return {r.route_id: r for r in (RoutePath.load(p) for p in paths)}


def _buses(route_id: str) -> list[dict[str, str]]:
    path = sorted((DATA / "recorded" / "bus").glob(f"20261108T18*_getBusPosByRtid_{route_id}.json"))
    raw = json.loads(path[-1].read_text("utf-8"))["raw"]
    buses: list[dict[str, str]] = json.loads(raw)["msgBody"]["itemList"]
    return buses


def test_route_paths(routes: dict[str, RoutePath]) -> None:
    r = routes["100100001"]
    assert len(r.xy) == 599 and round(r.length_m) == 15160  # itemList 599점
    assert {b["rtDist"] for b in _buses("100100001")} == {"16"}  # 노선 길이 km — 경로 15.16 km
    assert round(routes["100100118"].length_m) == 48785  # rtDist 49.2


def test_bus_positions_sit_on_the_route(routes: dict[str, RoutePath]) -> None:
    # 94대 전부 경로에서 17 m 안, 가운데값 0.49 m — 원시 GPS 라면 흩어질 텐데 경로 위에 붙어
    # 있다. 노선에 맞춘 좌표다 — 11/9 통제일에도 그랬다(docs/eval/bus_20261109.md, ADR-013 보류)
    dist = []
    for route_id, r in routes.items():
        for b in _buses(route_id):
            dist.append(r.distance_m(*to_5179(float(b["gpsX"]), float(b["gpsY"]))))
    assert len(dist) == 94 and round(max(dist), 1) == 17.0  # 100100046 의 한 대
    assert round(statistics.median(dist), 2) == 0.49


def test_route_position_follows_stop_order(routes: dict[str, RoutePath]) -> None:
    # 한 방향으로만 가는 100100001: 차량마다 경로 위 거리 하나, 그 순서가 정류소 순번(sectOrd) 순서
    r = routes["100100001"]
    located = []
    for b in _buses("100100001"):
        (m,) = r.near_measures(*to_5179(float(b["gpsX"]), float(b["gpsY"])), within=15.0)
        located.append((m, int(b["sectOrd"])))
    orders = [o for _, o in sorted(located)]
    assert orders == sorted(orders) == [3, 7, 9, 13, 16, 16, 20]


def test_sejong_passes(routes: dict[str, RoutePath], seoul_spatial_dir: Path) -> None:
    index = CrosswalkIndex.from_xlsx(seoul_spatial_dir / "OA-23081.xlsx", Settings())
    cws = {i: (index.get(i).x, index.get(i).y) for i in SEJONG}
    a, b = cws["06-0000023254"], cws["06-0000023206"]
    straight = math.hypot(a[0] - b[0], a[1] - b[1])  # 숭례문 → 세종대로사거리 1,038 m

    def lengths(route_id: str) -> list[int]:
        return [round(e - s) for s, e in routes[route_id].passes(cws)]

    assert round(straight) == 1038
    assert lengths("100100001") == [1095]  # 한 번 지나감 — 직선의 1.05배
    assert lengths("100100185") == [1051, 1066]  # 같은 길을 오가는 노선 — 가는 길·오는 길
    assert lengths("100900003") == [1103, 1055]  # 숭례문에서 되돌아 나온다 — 같은 횡단보도로 끊음
    assert lengths("100100033") == [0, 0]  # 세종대로사거리에서 가로지르기만 두 번
    assert lengths("100100118") == []  # 세종대로를 안 지난다
