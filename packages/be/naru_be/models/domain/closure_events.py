"""사건 v2 (ADR-014 A, INTERFACE §3.1 v0.14) — 사건 id·상태 묶기·시간 창·상한. Flask·DB 모른다.

사건 = 같은 (reason, window.start, window.end) 의 횡단보도 상태 묶음.
- id = sha1("<reason>|<시작 UTC YYYY-MM-DDTHH:MM:SSZ>|<끝 UTC>") 앞 12자 — 다시 받아도 같다.
- status = 시각 at 기준 그 사건 횡단보도 상태 중 가장 심한 것, confidence = 가장 큰 값.
- 지금 지도(at 이 있을 때): [from, to] 와 겹치는 사건만 — 시작 ≤ to,
  (끝 또는 시작+6시간) + 30분 ≥ from. from 기본 at, to 기본 at 의 다음 날 24:00(KST).
  한 번에 300건까지(심한 상태·시작 가까운 순으로 고른 뒤 시작 늦은 순).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Protocol

from naru_be.config import Settings
from naru_be.models.domain.types import KST
from naru_contracts import ClosureEvent, ClosureEventsQuery, ClosureState, Status

EVENTS_CAP = 300
SEVERITY = {Status.confirmed: 3, Status.scheduled: 2, Status.zone_scheduled: 1, Status.released: 0}


def event_id(reason: str, start: datetime | None, end: datetime | None) -> str:
    """사건 id — reason·시작·끝(UTC 초 단위)의 sha1 앞 12자."""

    def utc(t: datetime | None) -> str:
        return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if t is not None else ""

    return hashlib.sha1(f"{reason}|{utc(start)}|{utc(end)}".encode()).hexdigest()[:12]


def worst(statuses: Iterable[Status]) -> Status:
    """가장 심한 상태 — 통제 중 > 예정 > 예정 구역 > 해제."""
    return max(statuses, key=lambda s: SEVERITY[s])


@dataclass(frozen=True)
class EventWindow:
    """지금 지도의 시간 창 — at 기준 상태, [start, end] 와 겹치는 사건."""

    at: datetime
    start: datetime
    end: datetime


def window_of(query: ClosureEventsQuery, now: datetime) -> tuple[datetime, EventWindow | None]:
    """질의 → (상태 기준 시각, 시간 창). at 이 없으면 (서버 지금, 창 없음 = 전부)."""
    if query.at is None:
        return now, None
    at = query.at
    tomorrow_end = datetime.combine(at.astimezone(KST).date() + timedelta(days=2), time(), KST)
    return at, EventWindow(at, query.from_ or at, query.to or tomorrow_end)


def overlaps(
    start: datetime | None, end: datetime | None, window: EventWindow, settings: Settings
) -> bool:
    """사건 창이 [window.start, window.end] 와 겹치나 — 끝 없으면 시작+6시간, 끝+30분까지."""
    if start is None:
        return False
    stop = end or start + timedelta(hours=settings.unknown_end_hours)
    grace = timedelta(minutes=settings.released_grace_min)
    return start <= window.end and stop + grace >= window.start


def limit_events(
    events: Sequence[ClosureEvent], at: datetime, cap: int = EVENTS_CAP
) -> tuple[list[ClosureEvent], bool]:
    """상한 — 넘으면 심한 상태·시작 가까운 순으로 cap 개를 고른 뒤 시작 늦은 순(§3.1 순서)."""
    if len(events) <= cap:
        return list(events), False

    def rank(e: ClosureEvent) -> tuple[int, float, str]:
        start = e.window.start
        gap = abs((start - at).total_seconds()) if start is not None else float("inf")
        return (-SEVERITY[e.status], gap, e.id)

    kept = sorted(events, key=rank)[:cap]

    def order(e: ClosureEvent) -> tuple[bool, float, str]:
        start = e.window.start
        return (start is None, -start.timestamp() if start is not None else 0.0, e.reason)

    return sorted(kept, key=order), True


class EventRows(Protocol):
    """사건을 묶어 주는 저장소 (ClosureRepository.events)."""

    def events(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        district_of: Callable[[str], str | None] | None = None,
        *,
        status_of: Callable[[ClosureState], Status],
        window: EventWindow | None = None,
    ) -> list[ClosureEvent]: ...


class StatusJudge(Protocol):
    def status_of_state(self, state: ClosureState, at: datetime) -> Status: ...


@dataclass(frozen=True)
class EventsResult:
    events: list[ClosureEvent]
    at: datetime  # 사건 status 의 기준 시각
    truncated: bool


def listed(
    query: ClosureEventsQuery,
    now: datetime,
    rows: EventRows,
    judge: StatusJudge,
    bbox: tuple[float, float, float, float] | None,
    district_of: Callable[[str], str | None] | None = None,
) -> EventsResult:
    """GET /closures/events 의 Model — 시각·창을 정하고 사건을 묶은 뒤, 창이 있으면 상한."""
    at, window = window_of(query, now)
    events = rows.events(
        bbox, district_of, status_of=lambda st: judge.status_of_state(st, at), window=window
    )
    if window is None:
        return EventsResult(events, at, False)
    kept, truncated = limit_events(events, at)
    return EventsResult(kept, at, truncated)
