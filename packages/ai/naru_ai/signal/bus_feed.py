"""버스 위치·노선 경로 받기 — getBusPosByRtid·getRoutePath 호출, 원문 기록, 파싱 (T6.2, ADR-013).

- 위치: live 면 원문을 `data/recorded/bus/<kind>/<ts>_getBusPosByRtid_<노선>.json` 에 남긴다.
  kind = notice(공지 통제) · incident(TOPIS 집회·행사 돌발 기준 데이터) — 태우 2026-11-08. 키는
  가린다. 하루(KST) 호출 수는 그날 기록 파일 수로 센다 — 워커가 다시 떠도 이어진다. recorded 면
  그 노선의 가장 최근 기록을 재생한다(kind 폴더, 그다음 나누기 전 `bus/` 바로 아래 기록).
  itemList 는 그대로 BusPosition 으로(INTERFACE §1.2). headerCd 8(운행 종료)은 차 없음.
- 경로: 노선정보조회 getRoutePath(data.go.kr 15000193)를 노선당 하루 한 번
  `data/raw/bus_routes/<날짜>/path_<노선>.json` 에 받은 그대로 둔다 — 도로 그래프로 정류소를
  잇지 않는다(우회 지점에서 실제 노선과 달라 가짜 이탈이 생긴다, 태우 2026-11-08). 실패하면
  (2026-11-08 키 미등록 HTTP 401) 그날 그 노선은 다시 부르지 않는다.
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
ROUTE_PATH_API = "http://ws.bus.go.kr/api/rest/busRouteInfo/getRoutePath"
NO_VEHICLES = "8"  # headerCd 8 운행 종료 (메모 bus-position-api)
KINDS = ("notice", "incident", "marathon")  # incident 는 11/9 까지(2순위 돌발, ADR-013 보류로 뺌)


class BusFeedError(Exception):
    """getBusPosByRtid 가 정상(headerCd 0)이 아니다."""


class RoutePathError(Exception):
    """getRoutePath 가 정상이 아니다 (키 미등록 401 등)."""


def _int(v: object) -> int | None:
    return int(str(v)) if v not in (None, "") else None


def _float(v: object) -> float | None:
    return float(str(v)) if v not in (None, "") else None


def _flag(v: object) -> bool | None:
    return str(v) == "1" if v not in (None, "") else None


def _day(now: datetime) -> str:
    return now.astimezone(KST).strftime("%Y%m%d")


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


def _record(
    path: Path,
    api: str,
    endpoint: str,
    params: dict[str, str],
    r: httpx.Response,
    raw: str,
    called: datetime,
) -> None:
    rec = {
        "api": api,
        "endpoint": f"{endpoint}?serviceKey=<키>",
        "params": params,
        "called_at": called.isoformat(timespec="seconds"),
        "status": r.status_code,
        "raw": raw,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8")


class BusApi:
    """getBusPosByRtid — live(호출 + 원문 기록) 또는 recorded(그 노선의 가장 최근 기록,
    until 이 있으면 그 시각까지 — 파일 이름의 KST 시각으로 본다)."""

    def __init__(
        self,
        recorded_dir: Path,
        key: str | None = None,
        base_url: str = BUS_API,
        client: httpx.Client | None = None,
        until: datetime | None = None,
    ) -> None:
        self.root = recorded_dir / "bus"
        self.until = until.astimezone(KST).strftime("%Y%m%dT%H%M%S") if until else None
        self.key = unquote(key) if key else None  # 인코딩 키면 풀어서 httpx 가 다시 인코딩
        self.base_url = base_url
        self._client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})

    @property
    def live(self) -> bool:
        return self.key is not None

    def calls_today(self, now: datetime, kind: str | None = None) -> int:
        """오늘(KST) 남긴 원문 기록 수 = 오늘 부른 수. 나누기 전 기록(bus/ 바로 아래)은 notice."""
        pattern = f"{_day(now)}T*_getBusPosByRtid*.json"
        kinds = (kind,) if kind else KINDS
        n = sum(1 for k in kinds for _ in (self.root / k).glob(pattern))
        if kind in (None, "notice"):
            n += sum(1 for _ in self.root.glob(pattern))
        return n

    def call(self, route_id: str, kind: str = "notice") -> FeedRecord:
        if kind not in KINDS:
            raise ValueError(f"kind 는 {KINDS} 중 하나: {kind}")
        name = f"*_getBusPosByRtid_{route_id}.json"
        if self.key is None:
            files = self._recorded(kind, name)
            if not files:
                raise FileNotFoundError(f"버스 기록 없음: 노선 {route_id}")
            rec = json.loads(files[-1].read_text("utf-8"))
            return FeedRecord(
                files[-1], str(rec["raw"]), datetime.fromisoformat(str(rec["called_at"]))
            )
        params = {"busRouteId": route_id, "resultType": "json"}
        called = datetime.now(KST)
        r = self._client.get(self.base_url, params={"serviceKey": self.key, **params})
        r.raise_for_status()
        raw = r.text.replace(self.key, "<키>")
        path = (
            self.root / kind / f"{called.strftime('%Y%m%dT%H%M%S')}_getBusPosByRtid_{route_id}.json"
        )
        _record(path, "bus", self.base_url, params, r, raw, called)
        return FeedRecord(path, raw, called)

    def _recorded(self, kind: str, name: str) -> list[Path]:
        """kind 폴더의 기록, 없으면 나누기 전(bus/ 바로 아래) — until 뒤 기록은 없는 셈"""
        for files in (sorted((self.root / kind).glob(name)), sorted(self.root.glob(name))):
            kept = [f for f in files if self.until is None or f.name[:15] <= self.until]
            if kept:
                return kept
        return []


class RoutePaths:
    """노선 경로 — getRoutePath 를 노선당 하루 한 번 raw 에 받아 둔다. 키가 없으면 안 부른다."""

    def __init__(
        self,
        raw_dir: Path,
        key: str | None = None,
        base_url: str = ROUTE_PATH_API,
        client: httpx.Client | None = None,
    ) -> None:
        self.root = raw_dir / "bus_routes"
        self.key = unquote(key) if key else None
        self.base_url = base_url
        self._client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})
        self._failed: set[tuple[str, str]] = set()

    def path(self, route_id: str, now: datetime) -> Path:
        return self.root / _day(now) / f"path_{route_id}.json"

    def ensure(self, route_id: str, now: datetime) -> Path | None:
        """오늘 경로가 있으면 그 파일, 없으면 받아 둔다. 오늘 이미 실패한 노선은 다시 안 부른다."""
        path = self.path(route_id, now)
        if path.exists():
            return path
        if self.key is None or (_day(now), route_id) in self._failed:
            return None
        params = {"busRouteId": route_id, "resultType": "json"}
        called = datetime.now(KST)
        r = self._client.get(self.base_url, params={"serviceKey": self.key, **params})
        raw = r.text.replace(self.key, "<키>")
        code = None
        if r.status_code == 200:
            try:
                code = str((json.loads(raw).get("msgHeader") or {}).get("headerCd"))
            except json.JSONDecodeError:
                code = None
        if code != "0":
            self._failed.add((_day(now), route_id))
            raise RoutePathError(f"getRoutePath {route_id}: HTTP {r.status_code} {raw[:200]}")
        _record(path, "bus_routes", self.base_url, params, r, raw, called)
        return path
