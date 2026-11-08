"""버스 위치 받기 — getBusPosByRtid 호출·원문 기록·파싱 (T6.2, ADR-013 D·G). 판단 없음.

live 면 원문을 `data/recorded/bus/<ts>_getBusPosByRtid_<노선>.json` 에 남기고(키는 가림), 하루(KST)
상한은 그날 기록 파일 수로 센다 — 워커가 다시 떠도 이어진다. recorded 면 그 노선의 가장 최근 기록을
재생한다. itemList 는 그대로 BusPosition 으로(INTERFACE §1.2). headerCd 8(운행 종료)은 차 없음.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import httpx

from naru_ai.ingest.topis_api import KST, USER_AGENT, FeedRecord
from naru_contracts import BusPosition

BUS_API = "http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid"
NO_VEHICLES = "8"  # headerCd 8 운행 종료 (메모 bus-position-api)


class BusFeedError(Exception):
    """getBusPosByRtid 가 정상(headerCd 0)이 아니다."""


def _int(v: object) -> int | None:
    return int(str(v)) if v not in (None, "") else None


def _float(v: object) -> float | None:
    return float(str(v)) if v not in (None, "") else None


def _flag(v: object) -> bool | None:
    return str(v) == "1" if v not in (None, "") else None


def parse_bus_positions(raw: str) -> list[BusPosition]:
    body = json.loads(raw)
    header = body.get("msgHeader") or {}
    code = str(header.get("headerCd"))
    if code == NO_VEHICLES:
        return []
    if code != "0":
        raise BusFeedError(f"headerCd {code} {header.get('headerMsg')}")
    items = (body.get("msgBody") or {}).get("itemList") or []
    out: list[BusPosition] = []
    for it in items:
        if not it.get("gpsX") or not it.get("gpsY"):
            continue
        out.append(
            BusPosition(
                veh_id=str(it["vehId"]),
                plain_no=it.get("plainNo") or None,
                data_tm=datetime.strptime(str(it["dataTm"]), "%Y%m%d%H%M%S").replace(tzinfo=KST),
                lng=float(it["gpsX"]),
                lat=float(it["gpsY"]),
                sect_ord=_int(it.get("sectOrd")),
                section_id=it.get("sectionId") or None,
                sect_dist=_float(it.get("sectDist")),
                stop_flag=_flag(it.get("stopFlag")),
                last_stn_id=it.get("lastStnId") or None,
                next_st_id=it.get("nextStId") or None,
                is_run=_flag(it.get("isrunyn")),
            )
        )
    return out


class BusApi:
    """getBusPosByRtid — live(호출 + 원문 기록) 또는 recorded(그 노선의 가장 최근 기록)."""

    def __init__(
        self,
        recorded_dir: Path,
        key: str | None = None,
        base_url: str = BUS_API,
        client: httpx.Client | None = None,
    ) -> None:
        self.folder = recorded_dir / "bus"
        self.key = unquote(key) if key else None  # 인코딩 키면 풀어서 httpx 가 다시 인코딩
        self.base_url = base_url
        self._client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})

    @property
    def live(self) -> bool:
        return self.key is not None

    def calls_today(self, now: datetime) -> int:
        """오늘(KST) 남긴 원문 기록 수 = 오늘 부른 수 (ADR-013 G 상한)."""
        day = now.astimezone(KST).strftime("%Y%m%d")
        return sum(1 for _ in self.folder.glob(f"{day}T*_getBusPosByRtid*.json"))

    def call(self, route_id: str) -> FeedRecord:
        if self.key is None:
            files = sorted(self.folder.glob(f"*_getBusPosByRtid_{route_id}.json"))
            if not files:
                raise FileNotFoundError(f"버스 기록 없음: 노선 {route_id}")
            rec = json.loads(files[-1].read_text("utf-8"))
            called = datetime.fromisoformat(str(rec["called_at"]))
            return FeedRecord(files[-1], str(rec["raw"]), called)
        params = {"busRouteId": route_id, "resultType": "json"}
        called = datetime.now(KST)
        r = self._client.get(self.base_url, params={"serviceKey": self.key, **params})
        r.raise_for_status()
        raw = r.text.replace(self.key, "<키>")
        path = self.folder / f"{called.strftime('%Y%m%dT%H%M%S')}_getBusPosByRtid_{route_id}.json"
        rec = {
            "api": "bus",
            "endpoint": f"{self.base_url}?serviceKey=<키>",
            "params": params,
            "called_at": called.isoformat(timespec="seconds"),
            "status": r.status_code,
            "raw": raw,
        }
        self.folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8")
        return FeedRecord(path, raw, called)
