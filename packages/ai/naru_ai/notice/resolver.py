"""Resolver — 정규형 → PlacePoint (CONVENTIONS §3.4). 교차로 → 카카오 기록 순. 못 찾으면 None.

카카오는 기록 재생만 (`data/recorded/kakao/keyword/<sha1(검색어)>.json`, `make record API=kakao
--queries ...`). 검색어는 정규형 그대로, 없으면 방향어(앞·건너편·동측…)를 뗀 기본 이름.
1순위 선택: 서울 bbox 안 + 지역 힌트(AREA span, 예: 여의도)가 있으면 주소에 그 힌트가 있는 첫 문서.
식당·카페 등(EXCLUDED_CATEGORY_GROUPS)은 제외. 힌트가 있는데 맞는 문서가 없으면 None —
'사랑채' 처럼 전국에 흔한 이름이 엉뚱한 곳으로 가지 않게.
추측 좌표·기본 좌표 없음.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from naru_ai.notice.gazetteer import Gazetteer
from naru_contracts import PlacePoint, RoadClass

log = logging.getLogger(__name__)

SEOUL_BBOX = (126.76, 37.42, 127.19, 37.70)  # minLng, minLat, maxLng, maxLat
# 집회·행진 지점이 될 수 없는 카카오 category_group_code — 같은 이름의 식당·카페를 1순위에서 뺀다
# ('사랑채' 검색 1페이지에 여의도동 한식집이 있었다, 2026-11-07)
EXCLUDED_CATEGORY_GROUPS = frozenset(
    {"FD6", "CE7", "CS2", "AC5", "PK6", "OL7", "AG2", "AD5", "PM9"}
)  # 음식점·카페·편의점·학원·주차장·주유소·중개업소·숙박·약국
DIRECTION_SUFFIX = re.compile(
    r"\s*(정문\s*앞|후문\s*앞|앞|(동|서|남|북)측\s*건너편|건너편|(동|서|남|북)측|(남|북)단|입구)$"
)


class KakaoRecords:
    """기록된 카카오 키워드 검색 응답 (scripts/record_api.py 형식: endpoint·params·status·raw)."""

    def __init__(self, root: Path) -> None:
        self.dir = root / "kakao" / "keyword"

    def path(self, query: str) -> Path:
        return self.dir / f"{hashlib.sha1(query.encode('utf-8')).hexdigest()}.json"

    def documents(self, query: str) -> list[dict[str, str]] | None:
        path = self.path(query)
        if not path.exists():
            return None
        rec = json.loads(path.read_text("utf-8"))
        if rec.get("status") != 200:
            return None
        body = json.loads(rec["raw"]) if isinstance(rec["raw"], str) else rec["raw"]
        docs = body.get("documents", [])
        return [{str(k): str(v) for k, v in d.items()} for d in docs]


class Resolver:
    def __init__(self, gazetteer: Gazetteer, kakao: KakaoRecords) -> None:
        self.gazetteer = gazetteer
        self.kakao = kakao

    def resolve(
        self, canonical: str, tag: str | None = None, area_hint: str | None = None
    ) -> PlacePoint | None:
        """교차로 사전 → 카카오 기록. ROAD·AREA 태그는 점이 아니다 → None."""
        if tag in ("ROAD", "AREA"):
            return None
        if tag in (None, "INTERSECTION", "POI"):
            hit = self.gazetteer.intersection(canonical)
            if hit is not None:
                return hit
        if tag == "INTERSECTION":
            return None
        return self._kakao(canonical, area_hint)

    def resolve_road(self, name: str) -> tuple[str, RoadClass | None] | None:
        return self.gazetteer.road(name)

    def _kakao(self, canonical: str, area_hint: str | None) -> PlacePoint | None:
        name = self.gazetteer.alias(canonical)
        base = DIRECTION_SUFFIX.sub("", name).strip()
        for query in dict.fromkeys((name, base)):
            docs = self.kakao.documents(query)
            if docs is None:
                log.info("kakao record missing", extra={"query": query})
                continue
            doc = self._pick(docs, area_hint)
            if doc is not None:
                return PlacePoint(
                    canonical=canonical,
                    lng=float(doc["x"]),
                    lat=float(doc["y"]),
                    gazetteer_source="kakao",
                    gazetteer_id=doc["id"],
                )
        return None

    @staticmethod
    def _pick(docs: list[dict[str, str]], area_hint: str | None) -> dict[str, str] | None:
        for doc in docs:
            lng, lat = float(doc["x"]), float(doc["y"])
            if not (SEOUL_BBOX[0] < lng < SEOUL_BBOX[2] and SEOUL_BBOX[1] < lat < SEOUL_BBOX[3]):
                continue
            if doc.get("category_group_code", "") in EXCLUDED_CATEGORY_GROUPS:
                continue
            if area_hint and area_hint not in doc.get("address_name", "") + doc.get(
                "road_address_name", ""
            ):
                continue
            return doc
        return None
