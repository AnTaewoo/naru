"""알림 매칭 — 순수 함수 (ADR-014 C, T7.9). Flask·DB 를 모른다.

plan_sends(events, subscriptions, existing, now): 관심 지역 원(EPSG:5179, 반경 m)과 사건 통제 구역이
겹치면 (구독, 사건, 종류) 하나 — 종류는 사건이 그 시각 통제 중이면 confirmed, 예정이면 created.
사건은 impact blocks(zone_scheduled 아님)·확신도 ≥ review_confidence(0.7)·구역이 있는 것만.
이미 줄 섰거나 보낸 (구독, 사건, 종류)는 다시 안 만든다. created 가 밤(push_night_start_h ~
push_night_end_h KST)이면 다음 07:00 에, 그 밖과 confirmed 는 바로.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import shapely
from numpy.typing import NDArray
from pyproj import Transformer
from shapely.strtree import STRtree

from naru_be.config import Settings
from naru_be.models.domain.types import KST
from naru_contracts import ClosureEvent, Status

_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
SendKind = str  # "created" | "confirmed"


@dataclass(frozen=True)
class WatchCircle:
    lng: float
    lat: float
    radius_m: int


@dataclass(frozen=True)
class PlannedSend:
    subscription_id: int
    event_id: str
    kind: SendKind
    due_at: datetime


def _to_5179(xy: NDArray[np.float64]) -> NDArray[np.float64]:
    x, y = _4326_TO_5179.transform(xy[:, 0], xy[:, 1])
    return np.column_stack([x, y])


def area_5179(event: ClosureEvent) -> shapely.Geometry | None:
    if event.area is None:
        return None
    geo = shapely.geometry.shape(event.area.model_dump(mode="json"))
    return shapely.transform(geo, _to_5179)


def circle_5179(c: WatchCircle) -> shapely.Polygon:
    x, y = _4326_TO_5179.transform(c.lng, c.lat)
    return shapely.Point(x, y).buffer(c.radius_m)


def eligible(event: ClosureEvent, settings: Settings) -> bool:
    """알릴 만한 사건 — 통제 중·예정(구역 예정은 impact unknown 이라 뺀다), 확신도 ≥ 0.7, 구역."""
    return (
        event.status in (Status.confirmed, Status.scheduled)
        and event.confidence >= settings.review_confidence
        and event.area is not None
    )


def due_for(kind: SendKind, now: datetime, settings: Settings) -> datetime:
    """confirmed 는 바로. created 는 밤(22~07시 KST)이면 다음 07:00."""
    if kind == "confirmed":
        return now
    local = now.astimezone(KST)
    start, end = settings.push_night_start_h, settings.push_night_end_h
    if local.hour >= start:
        morning = (local + timedelta(days=1)).replace(hour=end, minute=0, second=0, microsecond=0)
    elif local.hour < end:
        morning = local.replace(hour=end, minute=0, second=0, microsecond=0)
    else:
        return now
    return morning


def plan_sends(
    events: Sequence[ClosureEvent],
    subscriptions: Sequence[tuple[int, Sequence[WatchCircle]]],
    existing: Collection[tuple[int, str, str]],
    now: datetime,
    settings: Settings,
) -> list[PlannedSend]:
    wanted = [e for e in events if eligible(e, settings)]
    shapes = [area_5179(e) for e in wanted]
    geoms = [g for g in shapes if g is not None]
    if not geoms:
        return []
    tree = STRtree(geoms)
    out: list[PlannedSend] = []
    seen: set[tuple[int, str, str]] = set(existing)
    for sub_id, circles in subscriptions:
        for c in circles:
            circle = circle_5179(c)
            for i in tree.query(circle, predicate="intersects"):
                event = wanted[int(i)]
                kind = "confirmed" if event.status is Status.confirmed else "created"
                key = (sub_id, event.id, kind)
                if key in seen:
                    continue
                seen.add(key)
                out.append(PlannedSend(sub_id, event.id, kind, due_for(kind, now, settings)))
    return out


def payload_of(event: ClosureEvent, kind: SendKind) -> dict[str, object]:
    """서비스워커가 알림을 만드는 재료 — 한국어 문구는 sw.js 가 붙인다."""
    start = event.window.start.isoformat() if event.window.start else None
    url = f"/?event={event.id}" + (f"&t={start}" if start else "")
    return {
        "kind": kind,
        "event_id": event.id,
        "type": event.type.value if event.type else None,
        "event": event.reason.splitlines()[0][:80],
        "start": start,
        "end": event.window.end.isoformat() if event.window.end else None,
        "url": url,
    }
