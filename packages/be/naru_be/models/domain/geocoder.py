"""Geocoder — 장소 검색·좌표 → 주소 (INTERFACE §7, ADR-011 B). Flask 를 모른다.

카카오 로컬(KakaoLocal: live 또는 recorded 재생)의 응답을 계약 모양으로 바꾼다. 카카오를 못 부르거나
응답 모양이 다르면 GeocodeUnavailableError(503).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, ValidationError

from naru_be.errors import GeocodeUnavailableError
from naru_be.models.repositories.kakao_local import (
    COORD2ADDRESS,
    KEYWORD,
    KakaoLocal,
    KakaoUnavailableError,
    coord2address_params,
    keyword_params,
)
from naru_contracts import GeocodeReverseResponse, Place
from naru_contracts.geocode_api import SEARCH_LIMIT

# near 가 있을 때 반경 안(정확도 순) 결과를 앞에 두는 수 — 나머지는 서울 전체에서 채운다.
# 지도 가운데가 멀어도(2026-11-11 태우 실서버 '용산', 가운데 과천 쪽) 빈 목록이 되지 않게
NEAR_TAKE = 5


class _Kakao(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _KakaoPlace(_Kakao):
    id: str
    place_name: str
    address_name: str
    road_address_name: str = ""
    x: float  # 경도 (WGS84 문자열)
    y: float


class _KeywordBody(_Kakao):
    documents: list[_KakaoPlace]


class _Named(_Kakao):
    address_name: str


class _AddressDoc(_Kakao):
    road_address: _Named | None = None
    address: _Named | None = None


class _Coord2AddressBody(_Kakao):
    documents: list[_AddressDoc]


def short_address(address: str) -> str:
    """화면용 — 시·도를 뺀다: "서울특별시 종로구 종로 1" → "종로구 종로 1"."""
    head, _, rest = address.partition(" ")
    return rest or head


class Geocoder:
    def __init__(self, source: KakaoLocal) -> None:
        self._source = source

    def search(self, q: str, near: tuple[float, float] | None) -> list[Place]:
        """키워드 검색, 최대 SEARCH_LIMIT 개. near([lng, lat])가 있으면 반경 안 정확도 순 앞
        NEAR_TAKE 개 + 서울 전체(SEOUL_RECT) 정확도 순에서 겹치지 않는 것(태우 11/11 — 가까운 것
        먼저, 먼 것도 알려 준다). 없으면 전국 정확도 순."""
        if near is None:
            docs = self._documents(keyword_params(q, None))
        else:
            docs = self._documents(keyword_params(q, near))[:NEAR_TAKE]
            seen = {d.id for d in docs}
            wide = self._documents(keyword_params(q, None, seoul=True))
            docs += [d for d in wide if d.id not in seen]
        return [
            Place(
                id=d.id,
                name=d.place_name,
                address=d.road_address_name or d.address_name,
                coord=(d.x, d.y),
            )
            for d in docs[:SEARCH_LIMIT]
        ]

    def _documents(self, params: Mapping[str, str]) -> list[_KakaoPlace]:
        return self._parse(_KeywordBody, KEYWORD, params).documents

    def reverse(self, lng: float, lat: float) -> GeocodeReverseResponse:
        """좌표 → 도로명·지번 주소. label 은 도로명(없으면 지번)에서 시·도를 뺀 것."""
        body = self._parse(_Coord2AddressBody, COORD2ADDRESS, coord2address_params(lng, lat))
        doc = body.documents[0] if body.documents else _AddressDoc()
        road = doc.road_address.address_name if doc.road_address else None
        jibun = doc.address.address_name if doc.address else None
        shown = road or jibun
        return GeocodeReverseResponse(
            label=short_address(shown) if shown else None, road_address=road, address=jibun
        )

    def _parse[T: _Kakao](self, model: type[T], endpoint: str, params: Mapping[str, str]) -> T:
        try:
            return model.model_validate(self._source.get(endpoint, params))
        except KakaoUnavailableError as e:
            raise GeocodeUnavailableError(str(e)) from e
        except ValidationError as e:
            raise GeocodeUnavailableError(f"카카오 응답 모양이 다르다: {e.error_count()}곳") from e
