"""카카오 로컬 API (ADR-011 B) — live 호출과 recorded 재생이 같은 모양(KakaoLocal). Flask 를 모른다.

live 는 서버 .env 의 KAKAO_REST_KEY 로 부른다 — 키는 브라우저·응답·로그·기록에 남기지 않는다.
recorded 는 `data/recorded/kakao/local/<record_name(endpoint, params)>` 를 읽는다. 같은 이름으로
`scripts/record_api.py --api geocode` 가 기록하므로, 요청 모양(아래 *_params)이 바뀌면
재생이 실패한다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

import httpx

log = logging.getLogger(__name__)

KEYWORD = "https://dapi.kakao.com/v2/local/search/keyword.json"
COORD2ADDRESS = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
KEYWORD_SIZE = 10  # 한 번에 받을 장소 수 (카카오 1~15)
# near 가 있으면 그 반경 안에서 정확도 순. 거리순(sort=distance)은 건물 안 가게가 앞선다 —
# 2026-11-08 기록: '교보빌딩' 1위 "투데이세차 광화문점", '시청' 1위 전자담배 가게,
# 본건물·서울시청은 10위 밖
NEAR_RADIUS_M = 5000
# 서울 전체 검색(카카오 rect "좌측X,좌측Y,우측X,우측Y" = w,s,e,n) — OA-23081 횡단보도
# 21,775곳(EPSG:5186)의 범위 lng 126.7981~127.1831 · lat 37.4345~37.6921 을 소수 2자리
# 바깥으로 넓힌 것 = 나루가 길을 내는 범위. near 반경 안 결과 뒤를 여기서 채운다 (태우 11/11)
SEOUL_RECT = "126.79,37.43,127.19,37.70"
USER_AGENT = "NaruBot/0.1 (+https://naru.antaewoo.com)"  # ADR-011 E


class KakaoUnavailableError(Exception):
    """키 없음·카카오 오류·시간 초과·기록 없음. Geocoder 가 geocode_unavailable 로 바꾼다."""


def keyword_params(
    q: str, near: tuple[float, float] | None, *, seoul: bool = False
) -> dict[str, str]:
    """키워드 검색. near([lng, lat])가 있으면 반경 NEAR_RADIUS_M 안에서 정확도 순, seoul 이면
    서울 전체(SEOUL_RECT)에서 정확도 순, 둘 다 아니면 전국. 둘을 같이 주지 않는다.

    near 는 소수 2자리(약 1 km)로 — 지도가 조금 움직여도 같은 요청(기록·재생 이름)이고, 카카오에
    보내는 위치도 그만큼만 정확하다.
    """
    if near is not None and seoul:
        raise ValueError("near 와 seoul 은 같이 쓰지 않는다")
    params = {"query": q, "size": str(KEYWORD_SIZE)}
    if near is not None:
        params |= {"x": f"{near[0]:.2f}", "y": f"{near[1]:.2f}", "radius": str(NEAR_RADIUS_M)}
    elif seoul:
        params["rect"] = SEOUL_RECT
    return params


def coord2address_params(lng: float, lat: float) -> dict[str, str]:
    """좌표 → 주소. 입력은 WGS84(카카오 기본), 소수 7자리(약 1 cm)."""
    return {"x": f"{lng:.7f}", "y": f"{lat:.7f}"}


def record_name(endpoint: str, params: Mapping[str, str]) -> str:
    """기록 파일 이름 — endpoint 와 정렬한 params 의 sha1."""
    canonical = endpoint + "?" + urlencode(sorted(params.items()))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest() + ".json"


class KakaoLocal(Protocol):
    def get(self, endpoint: str, params: Mapping[str, str]) -> object: ...


class LiveKakaoLocal:
    """서버에서 카카오를 부른다. 200 이 아니거나 시간 초과면 KakaoUnavailableError."""

    def __init__(self, key: str, timeout_s: float) -> None:
        self._key = key
        self._timeout_s = timeout_s

    def get(self, endpoint: str, params: Mapping[str, str]) -> object:
        if not self._key:
            raise KakaoUnavailableError("KAKAO_REST_KEY 없음")
        started = time.monotonic()
        try:
            r = httpx.get(
                endpoint,
                params=dict(params),
                headers={"Authorization": f"KakaoAK {self._key}", "User-Agent": USER_AGENT},
                timeout=self._timeout_s,
            )
        except httpx.HTTPError as e:
            raise KakaoUnavailableError(f"카카오 호출 실패: {type(e).__name__}") from e
        elapsed_ms = round((time.monotonic() - started) * 1000)
        extra = {"api": "kakao", "params": dict(params), "status": r.status_code}
        log.info("kakao local", extra=extra | {"elapsed_ms": elapsed_ms})
        if r.status_code != 200:
            raise KakaoUnavailableError(f"카카오 HTTP {r.status_code}")
        body: object = r.json()
        return body


class RecordedKakaoLocal:
    """기록을 재생한다. 기록이 없으면 지어내지 않고 KakaoUnavailableError."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, endpoint: str, params: Mapping[str, str]) -> object:
        path = self._root / record_name(endpoint, params)
        if not path.exists():
            raise KakaoUnavailableError(f"기록 없음 {path.name}: {dict(params)}")
        doc = json.loads(path.read_text("utf-8"))
        if doc.get("status") != 200:
            raise KakaoUnavailableError(f"기록된 응답이 HTTP {doc.get('status')}")
        body: object = json.loads(doc["raw"])
        return body
