"""서울 실시간 도시데이터(OA-21285 citydata) 간접 신호 기록 (T7.19, 멘토링 T-E) — 기록만.

활성 통제(사건 창 1시간 전 ~ 끝 30분 뒤) 근처 장소(주요 121장소 영역, raw/citydata_areas_*)만
5분마다 불러 원문을 recorded/rtd/signals/<ts>_citydata_<AREA_CD>.json 에 남긴다. 도로 링크 속도
(ROAD_TRAFFIC_STTS: LINK_ID·SPD·IDX — LINK_ID 는 표준노드링크와 같다, 11/11 159/159)와 장소
혼잡도(LIVE_PPLTN_STTS)는 경로·확신도 어디에도 안 쓴다(ADR-002; ADR-013 의 버스와 같은 기록만).
live 면 열린데이터광장 키, recorded 면 그 장소의 가장 최근 기록(없으면 건너뛴다 — 지어내지 않는다).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from naru_ai.signal.citydata_areas import Area, AreaBook
from naru_ai.signal.citydata_feed import CitydataApi, Signals, parse_signals
from naru_contracts import ClosureEventsResponse

log = logging.getLogger(__name__)
LEAD = timedelta(hours=1)  # 버스(ADR-013 G)와 같은 창 — 시작 1시간 전부터
TAIL = timedelta(minutes=30)  # 끝 30분 뒤까지


class CitydataWatcher:
    """활성 통제 근처 장소를 골라 한 번씩 부른다(기록만). 하루 상한을 넘으면 멈춘다."""

    def __init__(
        self,
        areas: AreaBook,
        api: CitydataApi,
        events: Callable[[], ClosureEventsResponse],
        *,
        radius_m: float = 1000.0,
        per_event: int = 2,
        daily_cap: int = 200,
    ) -> None:
        self.areas = areas
        self.api = api
        self.events = events
        self.radius_m = radius_m
        self.per_event = per_event
        self.daily_cap = daily_cap
        self._active = 0

    def targets(self, now: datetime) -> list[Area]:
        """창 안(시작 1시간 전 ~ 끝 30분 뒤) 사건 중심에서 radius_m 안 장소 — 사건마다 per_event,
        겹치면 한 번."""
        out: list[Area] = []
        seen: set[str] = set()
        self._active = 0
        for ev in self.events().events:
            start, end = ev.window.start, ev.window.end
            if start is None or ev.centroid is None:
                continue
            if not (start - LEAD <= now <= (end or start) + TAIL):
                continue
            self._active += 1
            for a in self.areas.near(
                (float(ev.centroid[0]), float(ev.centroid[1])), self.radius_m, self.per_event
            ):
                if a.code not in seen:
                    seen.add(a.code)
                    out.append(a)
        return out

    def round(self, now: datetime) -> list[Signals]:
        targets = self.targets(now)
        calls = self.api.calls_today(now) if self.api.live else None
        log.info(
            "signals targets",
            extra={
                "events": self._active,
                "areas": [a.code for a in targets],
                "calls_today": calls,
            },
        )
        out: list[Signals] = []
        for area in targets:
            if self.api.live and self.api.calls_today(now) >= self.daily_cap:
                log.warning("signals daily cap", extra={"cap": self.daily_cap})
                break
            try:
                rec = self.api.call(area)
            except FileNotFoundError:
                log.info("signals record missing", extra={"area": area.code})
                continue
            s = parse_signals(rec.raw, rec.received_at)
            log.info(
                "signals",
                extra={
                    "area": s.area_code,
                    "congestion": s.congestion,
                    "road": s.road_index,
                    "speed": s.road_speed_kmh,
                    "links": len(s.links),
                },
            )
            out.append(s)
        return out
