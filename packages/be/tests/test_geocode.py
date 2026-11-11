"""T5.8 — Geocoder·GET /geocode/* (INTERFACE §7, ADR-011 B). 카카오 로컬 기록을 재생한다(live 없음).

기대값은 recorded kakao/local 을 열어 확인한 값 (MANIFEST "recorded/kakao/local", 2026-11-08 기록):
교보빌딩 점 → 도로명 "서울특별시 종로구 종로 1"·지번 "서울 종로구 종로1가 1", 세종대로 건너기 도착점
(태우 실서버 요청) → 도로명 없음·지번 "서울 중구 남대문로2가 9-9", 키워드 반경 5 km 정확도 순 1위
교보빌딩 → 광화문교보빌딩 24020019, 덕수궁 → 덕수궁 10305191, 시청 → 서울특별시청 8430129.
2026-11-11 기록(태우 "멀리 있는 것도 알려 줘야지"): near 반경 5 km 안 앞 5개 뒤를 서울 전체(rect)
정확도 순으로 채운다 — `9da3f3aa…`(교보빌딩 rect)·`3090ce42…`(시청 rect)·`dc7b93c1…`(용산 rect)·
`a4cfa6ef…`(용산 near 126.99,37.42 = 태우 실서버 검색 11:26 의 지도 가운데 — 0건).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from flask.testing import FlaskClient

from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.errors import GeocodeUnavailableError
from naru_be.models.domain.geocoder import Geocoder
from naru_be.models.repositories.kakao_local import RecordedKakaoLocal
from naru_contracts import ErrorBody, GeocodeReverseResponse, GeocodeSearchResponse

BE_DIR = Path(__file__).resolve().parents[1]
KYOBO = (126.9779039768265, 37.5709686446227)  # [lng, lat] 카카오 24020019 (route_0745 출발)
NAMDAEMUN = (126.98193, 37.56368)  # 태우 실서버 요청(2026-11-08) 세종대로 건너기 도착
JAMSIL = (127.0980, 37.5133)  # 태우 실서버 요청 — 기록하지 않은 점
CENTER = (126.9775, 37.5675)  # FE 지도 기본 중심 (near)


@pytest.fixture(scope="module")
def geocoder(recorded_dir: Path) -> Geocoder:
    return Geocoder(RecordedKakaoLocal(recorded_dir / "kakao" / "local"))


def test_search_near_center_is_relevance_within_radius(geocoder: Geocoder) -> None:
    places = geocoder.search("교보빌딩", CENTER)
    assert len(places) == 10
    first = places[0]
    assert (first.id, first.name, first.address) == (
        "24020019",
        "광화문교보빌딩",
        "서울 종로구 종로 1",
    )
    assert first.coord == KYOBO
    assert geocoder.search("덕수궁", CENTER)[0].name == "덕수궁"
    assert geocoder.search("시청", CENTER)[0].name == "서울특별시청"
    # 지도가 조금 움직여도(소수 2자리 같음) 같은 요청 — 같은 결과
    assert geocoder.search("교보빌딩", (126.9791, 37.5718))[0].id == "24020019"


def test_search_near_puts_radius_first_then_seoul_wide(geocoder: Geocoder) -> None:
    places = geocoder.search("교보빌딩", CENTER)
    assert [p.name for p in places[:5]] == [  # 4826147a 0~4 (반경 5 km 정확도 순)
        "광화문교보빌딩",
        "교보재단빌딩",
        "교보생명빌딩",
        "광화문교보빌딩 교보컨벤션홀",
        "교보문고사옥",
    ]
    assert [p.name for p in places[5:]] == [  # 9da3f3aa 0·2·3·4·5 — 1·8 은 앞 5개와 같은 id 라 뺌
        "교보타워",
        "교보증권빌딩",
        "교보생명 상계동사옥",
        "교보생명빌딩",
        "교보생명 영등포사옥",
    ]
    assert places[5].address == "서울 서초구 강남대로 465" and len({p.id for p in places}) == 10
    # 태우 실서버 검색(11/11 11:26) — 지도 가운데가 과천 쪽이라 반경 안 0건. 전엔 빈 목록이었다
    far = geocoder.search("용산", (126.99, 37.42))
    assert [p.name for p in far[:3]] == ["이태원거리", "YTN서울타워", "노들섬"]  # dc7b93c1 0~2
    assert len(far) == 10
    # 시청 — 뒤 5개는 서울 전체 rect 라 경기 시청이 들어오고(3090ce42 1~4·6) 부산·제주는 없다
    names = [p.name for p in geocoder.search("시청", CENTER)]
    assert names[:2] == ["서울특별시청", "시청역 1호선"]
    assert names[5:] == ["고양시청", "광명시청", "구리시청", "남양주시청 제2청사", "시청앞주유소"]


def test_reverse_road_then_jibun_label(geocoder: Geocoder) -> None:
    kyobo = geocoder.reverse(*KYOBO)
    assert kyobo == GeocodeReverseResponse(
        label="종로구 종로 1",
        road_address="서울특별시 종로구 종로 1",
        address="서울 종로구 종로1가 1",
    )
    no_road = geocoder.reverse(*NAMDAEMUN)
    assert no_road.road_address is None and no_road.address == "서울 중구 남대문로2가 9-9"
    assert no_road.label == "중구 남대문로2가 9-9"


def test_missing_record_is_unavailable_not_made_up(geocoder: Geocoder) -> None:
    with pytest.raises(GeocodeUnavailableError) as e:
        geocoder.reverse(*JAMSIL)
    assert e.value.code == "geocode_unavailable" and e.value.http_status == 503


@pytest.fixture(scope="module")
def client() -> Iterator[FlaskClient]:
    base = Settings()
    cfg = Config(str(BE_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={base.test_database_url}"]})()
    command.upgrade(cfg, "head")
    app: Flask = create_app(
        Settings(DATABASE_URL=base.test_database_url, geocode_source="recorded")
    )
    yield app.test_client()


def test_geocode_endpoints(client: FlaskClient) -> None:
    q = {"q": " 교보빌딩 ", "near": "37.5675,126.9775"}  # 앞뒤 공백은 뺀다 (§7.1)
    resp = client.get("/geocode/search", query_string=q)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    found = GeocodeSearchResponse.model_validate(resp.get_json())
    assert [p.name for p in found.places[:2]] == ["광화문교보빌딩", "교보재단빌딩"]
    assert "광화문교보빌딩" in resp.get_data(as_text=True)  # 한글 그대로
    resp = client.get("/geocode/reverse", query_string={"lat": KYOBO[1], "lng": KYOBO[0]})
    assert resp.status_code == 200
    assert GeocodeReverseResponse.model_validate(resp.get_json()).label == "종로구 종로 1"


def test_geocode_errors(client: FlaskClient) -> None:
    for path, query, field in (
        ("/geocode/search", {"q": "시"}, "q"),
        ("/geocode/search", {"q": "시청", "near": "126.9775,37.5675"}, "near"),  # lng,lat 순서
        ("/geocode/reverse", {"lat": "91", "lng": "126.97"}, "lat"),
        ("/geocode/reverse", {"lat": "37.57"}, "lng"),
    ):
        resp = client.get(path, query_string=query)
        assert resp.status_code == 400, (path, query)
        err = ErrorBody.model_validate(resp.get_json()).error
        assert (err.code, err.field) == ("invalid_query", field)
    resp = client.get("/geocode/reverse", query_string={"lat": JAMSIL[1], "lng": JAMSIL[0]})
    assert resp.status_code == 503
    assert ErrorBody.model_validate(resp.get_json()).error.code == "geocode_unavailable"
