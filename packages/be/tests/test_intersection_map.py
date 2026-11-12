"""T1.3 — IntersectionMap: 교차로명 → 교차로관리번호 → 횡단보도 (실데이터 OA-23081, 종로·중구).

기대값은 2026-11-07 xlsx를 열어 확인한 값. 서비스 범위는 T6.9 부터 서울 전체지만 IntersectionMap 은
운영 코드가 쓰지 않아(T1.3 부품) 종로·중구로 고정해 그 값을 지킨다.
"""

from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.intersection_map import IntersectionMap

# 교차로관리번호 535 세종대로사거리의 횡단보도관리번호 8개 (xlsx 종로구 행)
SEJONG_CROSSWALKS = (
    "06-0000023200",
    "06-0000023205",
    "06-0000023206",
    "06-0000029520",
    "06-0000035426",
    "06-0000036391",
    "06-0000046713",
    "06-0000046716",
)


@pytest.fixture(scope="module")
def imap(seoul_spatial_dir: Path) -> IntersectionMap:
    xlsx = seoul_spatial_dir / "OA-23081.xlsx"
    return IntersectionMap.from_xlsx(xlsx, Settings(districts=("종로구", "중구")))


def test_counts_and_uniqueness(imap: IntersectionMap) -> None:
    assert len(imap) == 409  # 종로·중구 교차로관리번호 수 = 교차로명 수 (1:1)
    assert len(imap.names()) == 409
    all_ids = [cid for n in imap.names() for cid in imap.crosswalks_of(n)]
    assert len(all_ids) == 1211 and len(set(all_ids)) == 1211  # 횡단보도는 한 교차로에만
    sizes = [len(imap.crosswalks_of(n)) for n in imap.names()]
    assert min(sizes) == 1 and max(sizes) == 9
    assert sum(1 for s in sizes if s >= 2) == 329  # 2개 이상 329, 1개뿐 80


def test_sejongdaero_sageori(imap: IntersectionMap) -> None:
    it = imap.by_name("세종대로사거리")  # ROADMAP T1.3: 교차로명 하나 → 횡단보도 ≥ 2
    assert it is not None and it.intersection_id == "535" and it.district == "종로구"
    assert it.crosswalk_ids == SEJONG_CROSSWALKS
    assert imap.crosswalks_of("세종대로사거리") == set(SEJONG_CROSSWALKS)
    assert imap.by_id("535") is it
    # 횡단보도 8점의 평균은 노드링크 '세종대로사거리' 노드(126.97698, 37.57023)에서 15 m 안
    assert abs(it.lng - 126.97698) < 0.0003 and abs(it.lat - 37.57023) < 0.00015


def test_exact_match_only(imap: IntersectionMap) -> None:
    assert imap.by_name("세종대로") is None
    assert imap.by_name("세종대로사거리 ") is None
    assert imap.crosswalks_of("없는교차로") == set()
    # '(연등)' 변형은 다른 교차로 — 223행이 그런 이름을 갖는다
    plain, variant = imap.by_name("경복궁"), imap.by_name("경복궁(연등)1")
    assert plain is not None and variant is not None
    assert plain.intersection_id != variant.intersection_id
