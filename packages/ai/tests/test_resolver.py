"""T4.2b — Gazetteer(교차로·도로명) + Resolver(카카오 기록 재생). 좌표는 전부 실데이터에서.

교차로 기대값: OA-23081 에서 교차로명 → 교차로관리번호 (2026-11-07 적재 확인: 세종대로사거리 535,
종로1가 567, 숭례문 625, 여의도역 182). 카카오 기대값: recorded/kakao/keyword 의 documents.
"""

from pathlib import Path

import pytest

from naru_ai.notice.gazetteer import Gazetteer, road_class
from naru_ai.notice.resolver import KakaoRecords, Resolver
from naru_contracts import PlacePoint, RoadClass


def gid(p: PlacePoint | None) -> str:
    assert p is not None
    return p.gazetteer_id


@pytest.fixture(scope="module")
def gazetteer(seoul_spatial_dir: Path, nodelink_seoul_dir: Path) -> Gazetteer:
    return Gazetteer.load(seoul_spatial_dir / "OA-23081.xlsx", nodelink_seoul_dir / "link.gpkg")


@pytest.fixture(scope="module")
def resolver(gazetteer: Gazetteer, recorded_dir: Path) -> Resolver:
    return Resolver(gazetteer, KakaoRecords(recorded_dir))


def test_intersections_from_crosswalk_registry(gazetteer: Gazetteer) -> None:
    assert len(gazetteer) == 7592 and gazetteer.road_count == 2972  # 서울 교차로명 / 링크 도로명
    p = gazetteer.intersection("세종대로사거리")
    assert p is not None and p.gazetteer_id == "535" and p.gazetteer_source == "seoul_intersection"
    assert abs(p.lng - 126.977128) < 1e-5 and abs(p.lat - 37.570170) < 1e-5  # 횡단보도 8점 평균
    # 접미사 '사거리'·'오거리' 를 떼면 등록 이름과 맞는다
    assert gid(gazetteer.intersection("종로1가사거리")) == "567"
    assert gid(gazetteer.intersection("숭례문오거리")) == "625"
    assert gid(gazetteer.intersection("여의도역")) == "182"
    assert gazetteer.intersection("내자동사거리") is None  # 등록 이름 없음 → 추측하지 않는다
    assert gazetteer.road("은행로") == ("은행로", RoadClass.ro)
    assert gazetteer.road("세종대로") == ("세종대로", RoadClass.daero)
    assert gazetteer.road("없는길") is None and road_class("사직로8길") is RoadClass.gil


def test_kakao_replay_and_selection_rule(resolver: Resolver) -> None:
    # '의사당역 5번출구' 기록 documents[0]: 국회의사당역 9호선 5번출구 id 8200572
    p = resolver.resolve("의사당역 5번출구", "POI")
    assert p is not None and p.gazetteer_source == "kakao" and p.gazetteer_id == "8200572"
    assert (p.lng, p.lat) == (126.91724371956369, 37.52828844742831)
    # 방향어를 떼고 기본 이름으로 — '하나증권' 기록 documents[0]: 하나증권 본사 452895564 (여의도동)
    p = resolver.resolve("하나증권 앞", "POI", area_hint="여의도")
    assert p is not None and p.gazetteer_id == "452895564" and p.canonical == "하나증권 앞"
    # 힌트 없으면 서울 안 첫 문서: '민주당사' → 더불어민주당 서울특별시당 17071011
    assert gid(resolver.resolve("민주당사", "POI")) == "17071011"
    # 힌트에 맞는 문서가 없으면 None: 여의도동 '사랑채' 는 음식점(FD6)이라 제외
    assert resolver.resolve("사랑채 동측 건너편", "POI", area_hint="여의도") is None
    assert gid(resolver.resolve("사랑채 동측 건너편", "POI")) == "27271133"
    # 교차로 사전이 카카오보다 먼저: '여의도역' 은 seoul_intersection 182 (카카오 기록도 있지만)
    p = resolver.resolve("여의도역", "POI")
    assert p is not None and p.gazetteer_source == "seoul_intersection"
    # 기록에 없는 이름·도로·지역은 None
    assert resolver.resolve("기록에없는장소", "POI") is None
    assert resolver.resolve("은행로", "ROAD") is None and resolver.resolve("여의도", "AREA") is None
    assert resolver.resolve_road("은행로") == ("은행로", RoadClass.ro)
