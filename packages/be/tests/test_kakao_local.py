"""T5.8 — 카카오 로컬 기록(record_api.py --api geocode, live)을 BE 가 같은 요청으로 재생한다.

기록 = `data/recorded/kakao/local/<record_name(endpoint, params)>` (ADR-011 B). 파일 이름이 내용의
endpoint·params 로 정해지므로, BE 가 만드는 요청 모양이 바뀌면 재생이 실패한다.
"""

import json
from pathlib import Path

import pytest

from naru_be.models.repositories.kakao_local import (
    COORD2ADDRESS,
    KEYWORD,
    KakaoUnavailableError,
    RecordedKakaoLocal,
    coord2address_params,
    keyword_params,
    record_name,
)


@pytest.fixture(scope="module")
def local_dir(recorded_dir: Path) -> Path:
    d = recorded_dir / "kakao" / "local"
    assert d.is_dir(), "기록 없음: make record API=geocode 먼저 (카카오 live 7회)"
    return d


def test_every_record_is_named_by_its_request(local_dir: Path) -> None:
    # 역지오코딩 4 + 키워드 near 3 (scripts/record_api.py GEOCODE_*) + 처음 기록한 거리순 3(안 씀)
    # + 2026-11-11 서울 전체 rect 4·멀리 near 1 (MANIFEST "recorded/kakao/local")
    files = sorted(local_dir.glob("*.json"))
    assert len(files) == 15
    for f in files:
        text = f.read_text("utf-8")
        doc = json.loads(text)
        assert f.name == record_name(doc["endpoint"], doc["params"])
        assert doc["endpoint"] in (KEYWORD, COORD2ADDRESS) and doc["status"] == 200
        assert "KakaoAK" not in text


def test_request_shape() -> None:
    # near 는 소수 2자리(약 1 km), 좌표는 7자리 — 기록·재생 이름이 float 표기에 흔들리지 않게
    assert keyword_params("교보빌딩", None) == {"query": "교보빌딩", "size": "10"}
    near = {"query": "시청", "size": "10", "x": "126.98", "y": "37.57", "radius": "5000"}
    assert keyword_params("시청", (126.9775, 37.5675)) == near  # FE 지도 기본 중심
    assert keyword_params("시청", (126.9791, 37.5718)) == near  # 조금 움직여도 같은 요청
    assert coord2address_params(126.9779039768265, 37.5709686446227) == {
        "x": "126.9779040",
        "y": "37.5709686",
    }


def test_recorded_replays_and_missing_is_unavailable(local_dir: Path) -> None:
    src = RecordedKakaoLocal(local_dir)
    body = src.get(COORD2ADDRESS, coord2address_params(126.9779039768265, 37.5709686446227))
    assert isinstance(body, dict) and isinstance(body.get("documents"), list)
    # 기록 1e979f8e… 을 열어 확인 (MANIFEST recorded/kakao/local): 교보빌딩 점의 도로명 주소
    assert body["documents"][0]["road_address"]["address_name"] == "서울특별시 종로구 종로 1"
    # 기록 안 한 점(잠실, 태우 실서버 요청)은 재생할 게 없다 — 지어내지 않고 실패
    with pytest.raises(KakaoUnavailableError):
        src.get(COORD2ADDRESS, coord2address_params(127.0980, 37.5133))


def test_seoul_wide_shape() -> None:
    # 서울 전체는 rect 하나(near 와 같이 못 쓴다) — 기록 9da3f3aa…(교보빌딩 rect) 의 params 와 같다
    assert keyword_params("교보빌딩", None, seoul=True) == {
        "query": "교보빌딩",
        "size": "10",
        "rect": "126.79,37.43,127.19,37.70",
    }
    with pytest.raises(ValueError):
        keyword_params("교보빌딩", (126.98, 37.57), seoul=True)
