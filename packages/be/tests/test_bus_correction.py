"""T6.3 — 버스 확신도 보정 부품 (ADR-013): 순수 함수 + 감지 부품(노선 경로·경로 거리·구간).

실데이터:
- 노선 경로 raw bus_routes/20261109/path_<노선>.json — getRoutePath 2026-11-09 07:5x 8노선
- 버스 위치 recorded bus/20261108T18*_getBusPosByRtid_<노선>.json — 2026-11-08(일) 18:38~18:48,
  T6.2 가 11/7 공지 창으로 고른 8노선 94대
- 횡단보도 OA-23081 — TOPIS 6300 세종대로 7곳(test_e2e_worker)
순수 함수의 확신도·시각은 기록된 후보에서: smpa-20261107-r04 0.75(15:00~16:00), topis-6300 0.8,
smpa-20261108-r03 0.45(unknown, test_e2e_worker). 차량 ID 는 100100001 기록의 실제 차량.
통제일 버스 기록이 없어 '2회 연속 이탈'·정류소 건너뜀·통과 시간은 실측 대기다.
"""

import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.bus_correction import (
    NORMAL,
    OFF_ROUTE_M,
    SKIP_PAIR,
    Observations,
    RoutePath,
    correction,
    final_confidence,
    items,
    off_route_twice,
    recent,
    released_at,
    to_5179,
)
from naru_be.models.domain.crosswalk_index import CrosswalkIndex

DATA = Path(__file__).resolve().parents[3] / "data"
ROUTES = DATA / "raw" / "bus_routes" / "20261109"
KST = timezone(timedelta(hours=9))
R04 = datetime(2026, 11, 7, 15, 0, tzinfo=KST)  # smpa-20261107-r04 시작
CAR_A, CAR_B = "106024536", "106024187"  # 100100001 11/8 18:38 기록의 두 차량
# TOPIS 6300 세종대로 7곳 — 숭례문 23254·23247, 삼성본관 45236, 시청 40204, 덕수궁앞 40206,
# 프레스센터 42121, 세종대로사거리 23206 (OA-23081 교차로명)
SEJONG = [f"06-00000{n}" for n in (23254, 23247, 45236, 40204, 40206, 42121, 23206)]


def test_correction_table() -> None:
    def obs(
        skips: dict[str, datetime] | None = None,
        stop_skippers: int = 0,
        slow: int = 0,
        normal: int = 0,
    ) -> float:
        return correction(items(Observations(skips or {}, stop_skippers, slow, normal)))

    pair = {CAR_A: R04 + timedelta(minutes=2), CAR_B: R04 + timedelta(minutes=6)}
    apart = {CAR_A: R04, CAR_B: R04 + timedelta(minutes=16)}
    assert obs(skips=pair) == 0.20  # 서로 다른 2대가 15분 안에
    assert obs(skips={CAR_A: R04}) == 0.05  # 1대만
    assert obs(skips=apart) == 0.05  # 15분 넘게 떨어진 2대 — 약한 근거(정한 것)
    assert obs(skips=pair, normal=2) == -0.10  # ADR-013 A 의 예: 이탈 2대 + 정상 통과 2대
    assert obs(skips=pair, stop_skippers=2, slow=2) == 0.25  # 0.40 → 위 끝
    assert obs(normal=3) == -0.30 and obs(normal=1) == 0.0 and obs() == 0.0


def test_final_confidence() -> None:
    assert final_confidence(0.75, 0.20) == 0.95  # r04 + 2대 이탈
    assert final_confidence(0.8, 0.25) == 0.95  # 6300 — 0.95 위 끝
    assert final_confidence(0.8, -0.30) == 0.5  # 정상 통과 → 0.7 아래(길찾기에 안 씀)
    assert final_confidence(0.45, 0.25, promoted_unknown=True) == 0.65  # 11/8 r03
    assert final_confidence(0.45, 0.25, promoted_unknown=True, skip_near_point=True) == 0.7


def test_twenty_minute_window() -> None:
    times = [R04 - timedelta(minutes=20), R04 - timedelta(minutes=19), R04, R04 + timedelta(1)]
    assert recent(times, R04) == [R04 - timedelta(minutes=19), R04]  # (at - 20분, at]


def test_early_release_and_undo() -> None:
    def every(start: datetime, n: int, names: list[str]) -> list[tuple[datetime, list[str]]]:
        return [(start + timedelta(minutes=5 * i), names) for i in range(n)]

    normal, skip = [NORMAL[0]], [SKIP_PAIR[0]]
    # 15:00 부터 5분마다 정상 통과 — 20분이 되는 15:20 에 해제
    assert released_at(every(R04, 5, normal)) == R04 + timedelta(minutes=20)
    broken = [*every(R04, 3, normal), (R04 + timedelta(minutes=15), [])]
    broken += every(R04 + timedelta(minutes=20), 4, normal)  # 15:15 에 끊겼다 → 15:20 부터 다시
    assert released_at(broken) is None
    undo = [*every(R04, 5, normal), (R04 + timedelta(minutes=30), skip)]
    assert released_at(undo) is None  # 해제 뒤 2대 이탈 → 무른다
    again = undo + every(R04 + timedelta(minutes=35), 5, normal)
    assert released_at(again) == R04 + timedelta(minutes=55)


def test_off_route_twice() -> None:
    assert off_route_twice([0.5, 61.0, 62.0])  # 2회 연속
    assert not off_route_twice([61.0, 0.5, 62.0]) and not off_route_twice([OFF_ROUTE_M] * 3)


@pytest.fixture(scope="module")
def routes() -> dict[str, RoutePath]:
    paths = sorted(ROUTES.glob("path_*.json"))
    assert len(paths) == 8, "getRoutePath 기록 없음 — MANIFEST raw bus_routes"
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
    # 있다. 노선에 맞춘 좌표로 보인다(ADR-013 결과의 미확인 1) → 60 m 이탈은 통제일 기록으로
    # 확인하기 전엔 못 믿는다
    dist = []
    for route_id, r in routes.items():
        for b in _buses(route_id):
            dist.append(r.distance_m(*to_5179(float(b["gpsX"]), float(b["gpsY"]))))
    assert len(dist) == 94 and round(max(dist), 1) == 17.0  # 100100046 의 한 대
    assert round(statistics.median(dist), 2) == 0.49 and max(dist) < OFF_ROUTE_M


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
