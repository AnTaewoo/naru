"""서울 실시간 도시데이터(OA-21285 citydata) 한 장소 호출·원문 기록·읽기 (T7.19). 기록만.

live 면 열린데이터광장 키로 `/<키>/json/citydata/1/5/<AREA_NM>` 를 불러
recorded/rtd/signals/<ts>_citydata_<AREA_CD>.json 에 그대로(키는 <키>), recorded 면 그 장소의
가장 최근 기록. parse_signals 는 로그·테스트용 — BE 로 보내지 않는다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from naru_ai.ingest.topis_api import SEOUL_API, FeedRecord
from naru_ai.signal.citydata_areas import Area

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
USER_AGENT = "NaruBot/0.1 (+https://naru.antaewoo.com)"


@dataclass(frozen=True)
class LinkSpeed:
    link_id: str
    speed_kmh: float | None
    index: str  # 원활·서행·정체


@dataclass(frozen=True)
class Signals:
    """한 장소 한 번의 응답에서 읽은 것 — 로그·테스트용. BE 로 보내지 않는다."""

    area_code: str
    area_name: str
    called_at: datetime
    congestion: str | None  # AREA_CONGEST_LVL (여유·보통·약간 붐빔·붐빔)
    people_min: int | None
    people_max: int | None
    people_time: str | None
    road_index: str | None  # ROAD_TRAFFIC_IDX
    road_speed_kmh: float | None
    road_time: str | None
    links: list[LinkSpeed] = field(default_factory=list)


def _num(v: object) -> float | None:
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return None


def parse_signals(raw: str, called_at: datetime) -> Signals:
    body = json.loads(raw)
    city = body.get("CITYDATA") or {}
    ppl = (city.get("LIVE_PPLTN_STTS") or [{}])[0]
    road = city.get("ROAD_TRAFFIC_STTS") or {}
    avg = road.get("AVG_ROAD_DATA") or {}
    links = [
        LinkSpeed(str(it["LINK_ID"]), _num(it.get("SPD")), str(it.get("IDX") or ""))
        for it in road.get("ROAD_TRAFFIC_STTS") or []
    ]
    pmin, pmax = _num(ppl.get("AREA_PPLTN_MIN")), _num(ppl.get("AREA_PPLTN_MAX"))
    return Signals(
        area_code=str(city.get("AREA_CD") or ""),
        area_name=str(city.get("AREA_NM") or ""),
        called_at=called_at,
        congestion=ppl.get("AREA_CONGEST_LVL"),
        people_min=int(pmin) if pmin is not None else None,
        people_max=int(pmax) if pmax is not None else None,
        people_time=ppl.get("PPLTN_TIME"),
        road_index=avg.get("ROAD_TRAFFIC_IDX"),
        road_speed_kmh=_num(avg.get("ROAD_TRAFFIC_SPD")),
        road_time=avg.get("ROAD_TRAFFIC_TIME"),
        links=links,
    )


class CitydataApi:
    """citydata 한 장소 — live(호출 + 원문 기록) 또는 recorded(그 장소의 가장 최근 기록)."""

    def __init__(
        self,
        recorded_dir: Path,
        key: str | None = None,
        base_url: str = SEOUL_API,
        client: httpx.Client | None = None,
        until: datetime | None = None,
    ) -> None:
        self.root = recorded_dir / "rtd"
        # recorded 재생은 이 시각까지의 기록만 — 운영 워커가 같은 폴더에 새 기록을 쌓는다(버스 T6.9)
        self.until = until.astimezone(KST).strftime("%Y%m%dT%H%M%S") if until else None
        self.signals_dir = self.root / "signals"
        self.key = key or None
        self.base_url = base_url
        self._client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})

    @property
    def live(self) -> bool:
        return self.key is not None

    def calls_today(self, now: datetime) -> int:
        day = now.astimezone(KST).strftime("%Y%m%d")
        return sum(1 for _ in self.signals_dir.glob(f"{day}T*_citydata_*.json"))

    def call(self, area: Area) -> FeedRecord:
        if self.key is None:
            return self._recorded(area)
        url = "/".join([self.base_url, self.key, "json", "citydata", "1", "5", quote(area.name)])
        called = datetime.now(KST)
        r = self._client.get(url)
        r.raise_for_status()
        raw = r.text.replace(self.key, "<키>")
        path = self.signals_dir / f"{called.strftime('%Y%m%dT%H%M%S')}_citydata_{area.code}.json"
        rec = {
            "api": "rtd",
            "endpoint": "/".join([self.base_url, "<키>", "json", "citydata", "1", "5", area.name]),
            "params": {
                "service": "citydata",
                "type": "json",
                "start": 1,
                "end": 5,
                "AREA_NM": area.name,
            },
            "called_at": called.isoformat(timespec="seconds"),
            "status": r.status_code,
            "raw": raw,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8")
        log.info("recorded", extra={"api": "rtd", "area": area.code, "path": str(path)})
        return FeedRecord(path, raw, called)

    def _recorded(self, area: Area) -> FeedRecord:
        """signals/ 의 그 장소 기록, 없으면 rtd/ 바로 아래(이름에 장소가 없어 내용의 AREA_CD 로)."""
        files = [
            f
            for f in sorted(self.signals_dir.glob(f"*_citydata_{area.code}.json"))
            if self._kept(f)
        ]
        if not files:
            for f in filter(self._kept, sorted(self.root.glob("*_citydata.json"))):
                rec = json.loads(f.read_text("utf-8"))
                if f'"AREA_CD":"{area.code}"' in str(rec["raw"]).replace(" ", ""):
                    files.append(f)
        if not files:
            raise FileNotFoundError(f"citydata 기록 없음: {area.code} {area.name}")
        rec = json.loads(files[-1].read_text("utf-8"))
        return FeedRecord(files[-1], str(rec["raw"]), datetime.fromisoformat(str(rec["called_at"])))

    def _kept(self, f: Path) -> bool:
        return self.until is None or f.name[:15] <= self.until
