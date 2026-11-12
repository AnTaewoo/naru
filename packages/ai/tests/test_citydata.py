"""T7.19 — 간접 신호 기록(citydata). 입력은 실데이터만.

- raw/citydata_areas_20261111/…/서울시 주요 121장소 영역.shp — 121 폴리곤, EPSG:4326 (MANIFEST)
- recorded/rtd/20261107T154129_citydata.json · 20261109T082844_citydata.json — 광화문·덕수궁(POI009)
  (11/9: LIVE_PPLTN 여유 20,000~22,000 08:00, AVG_ROAD 서행 16 km/h 08:25, 링크 159,
  1000000301 종로 23.0)
- recorded/naru_api/closure_events_live_1107_1530.json — 11/7 15:30 사건 13건(중심 있음)
기대값은 파일을 열어 확인한 값(아래 주석).
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from naru_ai.signal.citydata import CitydataWatcher
from naru_ai.signal.citydata_areas import AreaBook
from naru_ai.signal.citydata_feed import CitydataApi, parse_signals
from naru_contracts import ClosureEventsResponse

KST = ZoneInfo("Asia/Seoul")
DATA = Path(__file__).resolve().parents[3] / "data"
# T7.19 기록(11/7·11/9)까지만 재생 — 운영 워커가 11/11 부터 rtd/signals/ 에 새 기록을 쌓는다
UNTIL = datetime(2026, 11, 9, 23, 59, 59, tzinfo=KST)


@pytest.fixture(scope="module")
def areas() -> AreaBook:
    return AreaBook.load(DATA / "raw")


def test_area_book_near_real_points(areas: AreaBook) -> None:
    assert len(areas.areas) == 121
    # 교보빌딩(카카오 24020019) — 광화문·덕수궁·광화문광장 영역 안(거리 0), 시의회 앞 62 m,
    # 종로·청계 70 m
    near = areas.near((126.9779039768265, 37.5709686446227), 1000, 4)
    assert [a.code for a in near] == ["POI009", "POI088", "POI130", "POI006"]
    assert near[0].name == "광화문·덕수궁" and near[0].category == "고궁·문화유산"
    assert [a.code for a in areas.near((126.9779, 37.5709), 1000, 2)] == ["POI009", "POI088"]
    # 논현역(카카오 좌표 127.0219, 37.5110) — 신논현역·논현역 안, 가로수길 605 m, 강남역 763 m
    assert [a.code for a in areas.near((127.0219, 37.5110), 1000, 3)] == [
        "POI037",
        "POI059",
        "POI014",
    ]
    # 반경 밖이면 비어 있다 — 국회의사당(126.9176, 37.5319)에서 100 m 는 여의도(안)·여의서로(85 m)뿐
    assert [a.code for a in areas.near((126.9176, 37.5319), 100, 5)] == ["POI072", "POI126"]


def test_parse_recorded_signals(recorded_dir: Path) -> None:
    api = CitydataApi(recorded_dir, until=UNTIL)  # key 없음 → recorded
    assert not api.live
    [area] = AreaBook.load(DATA / "raw").near((126.9779, 37.5709), 0, 1)
    rec = api.call(area)
    assert rec.path.name == "20261109T082844_citydata.json"  # 그 장소의 가장 최근 기록
    s = parse_signals(rec.raw, rec.received_at)
    assert (s.area_code, s.area_name) == ("POI009", "광화문·덕수궁")
    assert (s.congestion, s.people_min, s.people_max, s.people_time) == (
        "여유",
        20000,
        22000,
        "2026-11-09 08:00",
    )
    assert (s.road_index, s.road_speed_kmh, s.road_time) == ("서행", 16.0, "2026-11-09 08:25")
    assert len(s.links) == 159
    jongno = next(x for x in s.links if x.link_id == "1000000301")
    assert (jongno.speed_kmh, jongno.index) == (23.0, "서행")
    assert (
        api.calls_today(datetime(2026, 11, 9, 8, 30, tzinfo=KST)) == 0
    )  # 기록 재생은 호출이 아니다


def test_watcher_targets_and_recorded_round(recorded_dir: Path, areas: AreaBook) -> None:
    body = json.loads(
        (recorded_dir / "naru_api" / "closure_events_live_1107_1530.json").read_text("utf-8")
    )["body"]
    events = ClosureEventsResponse.model_validate(body)
    watcher = CitydataWatcher(
        areas, CitydataApi(recorded_dir, until=UNTIL), lambda: events, radius_m=1000, per_event=2
    )
    now = datetime(2026, 11, 7, 15, 30, tzinfo=KST)
    codes = [a.code for a in watcher.targets(now)]
    # 11/7 15:30 창 안 사건 13건, 사건마다 가까운 2곳(겹치면 한 번) — 의사당역 16:00(1시간 전 창)
    # → 여의도·여의서로, 내자R~사직공원 → 서촌·광화문·덕수궁, 시의회~숭례문R → 광화문·덕수궁·
    # 시의회 앞, 세종대로 시청역→숭례문 → 숭례문·명동, 서초역↔강남역 → 강남역·역삼역, 동화면세점
    # 고리 → 종로·청계, 여의대로 → 여의도한강공원, 서초대로 법원검찰청→서초역 → 교대역·서리풀공원
    assert codes == [
        "POI072", "POI126", "POI067", "POI009", "POI130", "POI131", "POI003",
        "POI014", "POI042", "POI006", "POI105", "POI018", "POI098",
    ]  # fmt: skip
    got = watcher.round(now)
    # 기록은 광화문·덕수궁(POI009)뿐 — 다른 장소는 건너뛴다(지어내지 않는다)
    assert [s.area_code for s in got] == ["POI009"]
    assert got[0].congestion == "여유" and len(got[0].links) == 159
    # 창 밖(11/7 20:00)이면 대상이 없다
    assert watcher.targets(datetime(2026, 11, 7, 20, 0, tzinfo=KST)) == []
