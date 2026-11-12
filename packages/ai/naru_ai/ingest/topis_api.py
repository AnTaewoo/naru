"""서울 열린데이터광장 OpenAPI(TOPIS 돌발 OA-13315·링크 OA-13310/13311) 호출과 원문 기록 (T6.1).

키는 URL 에 들어가므로 기록·로그에서 가린다. 기록 형식은 scripts/record_api.py 와 같다
(api, endpoint, params, called_at, status, raw). 웹 페이지가 아니라 키로 쓰는 공개 API 라
주기는 그 한도를 따른다(ADR-013 H). User-Agent 는 ADR-011 E.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pyproj import Transformer

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
SEOUL_API = "http://openapi.seoul.go.kr:8088"
USER_AGENT = "NaruBot/0.1 (+https://naru.antaewoo.com)"  # ADR-011 E
_TM = Transformer.from_crs("EPSG:5181", "EPSG:4326", always_xy=True)  # grs80tm_x/y 는 5181


class SeoulApiError(Exception):
    """응답이 정상(INFO-000)이 아니다."""


@dataclass(frozen=True)
class FeedRecord:
    path: Path
    raw: str
    received_at: datetime


def seoul_rows(raw: str, service: str) -> list[dict[str, str]]:
    root = ET.fromstring(raw)
    if root.tag != service:
        code = root.findtext("RESULT/CODE") or root.findtext("CODE") or "?"
        if code == "INFO-200":  # 해당 데이터 없음
            return []
        msg = root.findtext("RESULT/MESSAGE") or root.findtext("MESSAGE") or ""
        raise SeoulApiError(f"{service}: {code} {msg}")
    return [{c.tag: (c.text or "").strip() for c in row} for row in root.findall("row")]


class SeoulOpenApi:
    """서울 열린데이터광장 OpenAPI(xml) 호출 + 원문 기록 (형식은 scripts/record_api.py 와 같다)."""

    def __init__(
        self,
        key: str,
        recorded_dir: Path,
        base_url: str = SEOUL_API,
        client: httpx.Client | None = None,
    ) -> None:
        if not key:
            raise ValueError("SEOUL_OPENDATA_KEY 없음 — 돌발 live 를 쓸 수 없다")
        self.key = key
        self.recorded_dir = recorded_dir
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})

    def call(
        self, api: str, service: str, start: int, end: int, *extra: str, dedupe: bool = False
    ) -> FeedRecord:
        tail = [service, str(start), str(end)]
        url = "/".join([self.base_url, self.key, "xml", *tail, *(quote(e) for e in extra)]) + "/"
        masked = "/".join([self.base_url, "<키>", "xml", *tail, *extra]) + "/"
        called_at = datetime.now(KST)
        r = self._client.get(url)
        r.raise_for_status()
        raw = r.text.replace(self.key, "<키>")
        name = "_".join([service, *extra])
        folder = self.recorded_dir / api
        if dedupe:
            last = sorted(folder.glob(f"*_{name}.json"))
            if last and json.loads(last[-1].read_text("utf-8")).get("raw") == raw:
                return FeedRecord(last[-1], raw, called_at)
        path = folder / f"{called_at.strftime('%Y%m%dT%H%M%S')}_{name}.json"
        params: dict[str, object] = {"service": service, "type": "xml", "start": start, "end": end}
        if extra:
            params["LINK_ID"] = extra[0]
        rec = {
            "api": api,
            "endpoint": masked,
            "params": params,
            "called_at": called_at.isoformat(timespec="seconds"),
            "status": r.status_code,
            "raw": raw,
        }
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8")
        log.info("recorded", extra={"api": api, "service": service, "path": str(path)})
        return FeedRecord(path, raw, called_at)

    def fetch_link(self, link_id: str) -> None:
        """LinkInfo(도로명·노드명)·LinkVerInfo(꼭짓점)를 받아 links/ 에 기록 — LinkBook 용."""
        for service in ("LinkInfo", "LinkVerInfo"):
            self.call("links", service, 1, 100, link_id)


class IncidentFeed:
    """돌발 원문 — live(OA-13315 호출 + 기록) 또는 기록(지정 파일, 없으면 가장 최근)."""

    def __init__(
        self, recorded_dir: Path, api: SeoulOpenApi | None = None, pinned: Path | None = None
    ) -> None:
        self.recorded_dir = recorded_dir
        self.api = api
        self.pinned = pinned

    def fetch(self) -> FeedRecord:
        if self.api is not None:
            return self.api.call("incident", "AccInfo", 1, 1000, dedupe=True)
        path = self.pinned
        if path is None:
            files = sorted((self.recorded_dir / "incident").glob("*_AccInfo.json"))
            if not files:
                raise FileNotFoundError("돌발 기록 없음 — make record API=incident")
            path = files[-1]
        rec = json.loads(path.read_text("utf-8"))
        return FeedRecord(path, str(rec["raw"]), datetime.fromisoformat(str(rec["called_at"])))


@dataclass(frozen=True)
class Link:
    link_id: str
    road_name: str | None
    start_name: str | None
    end_name: str | None
    coords: tuple[tuple[float, float], ...]  # [lng, lat]


def lnglat_5181(x: float, y: float) -> tuple[float, float]:
    lng, lat = _TM.transform(x, y)
    return (round(lng, 7), round(lat, 7))


class LinkBook:
    """TOPIS 링크 선·이름 — 기록(links/<ts>_{LinkInfo,LinkVerInfo}_<id>.json)에서, 없으면 fetch."""

    def __init__(self, links_dir: Path, fetch: Callable[[str], None] | None = None) -> None:
        self.links_dir = links_dir
        self.fetch = fetch
        self._cache: dict[str, Link | None] = {}

    def _latest(self, service: str, link_id: str) -> str | None:
        files = sorted(self.links_dir.glob(f"*_{service}_{link_id}.json"))
        return str(json.loads(files[-1].read_text("utf-8"))["raw"]) if files else None

    def get(self, link_id: str) -> Link | None:
        if link_id in self._cache:
            return self._cache[link_id]
        ver = self._latest("LinkVerInfo", link_id)
        if ver is None and self.fetch is not None and link_id:
            self.fetch(link_id)
            ver = self._latest("LinkVerInfo", link_id)
        link = None if ver is None else self._link(link_id, ver)
        self._cache[link_id] = link
        return link

    def _link(self, link_id: str, ver: str) -> Link | None:
        rows = sorted(seoul_rows(ver, "LinkVerInfo"), key=lambda r: int(r.get("ver_seq") or 0))
        coords = tuple(lnglat_5181(float(r["grs80tm_x"]), float(r["grs80tm_y"])) for r in rows)
        if len(coords) < 2:
            return None
        info_raw = self._latest("LinkInfo", link_id)
        info = seoul_rows(info_raw, "LinkInfo")[0] if info_raw else {}
        return Link(
            link_id,
            info.get("road_name") or None,
            info.get("st_node_nm") or None,
            info.get("ed_node_nm") or None,
            coords,
        )
