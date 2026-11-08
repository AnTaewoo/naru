"""T5.8 — Geocoder (INTERFACE §7, ADR-011 B). 카카오 로컬 기록을 재생한다(live 없음).

기대값은 recorded kakao/local 을 열어 확인한 값 (MANIFEST "recorded/kakao/local", 2026-11-08 기록):
교보빌딩 점 → 도로명 "서울특별시 종로구 종로 1"·지번 "서울 종로구 종로1가 1", 세종대로 건너기 도착점
(태우 실서버 요청) → 도로명 없음·지번 "서울 중구 남대문로2가 9-9", 키워드 반경 5 km 정확도 순 1위
교보빌딩 → 광화문교보빌딩 24020019, 덕수궁 → 덕수궁 10305191, 시청 → 서울특별시청 8430129.
"""

from pathlib import Path

import pytest

from naru_be.errors import GeocodeUnavailableError
from naru_be.models.domain.geocoder import Geocoder
from naru_be.models.repositories.kakao_local import RecordedKakaoLocal
from naru_contracts import GeocodeReverseResponse

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
