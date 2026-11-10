"""PushRepository — 구독·관심 지역 쓰기·읽기 (T7.8). DB 접근은 Repository 만.

시각은 UTC 로 저장하고 KST 로 돌려준다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from naru_be.models.entities.push import PushSubscriptionEntity, WatchAreaEntity
from naru_be.models.repositories.closure_repository import to_kst, to_utc_naive


@dataclass(frozen=True)
class SubscriptionRow:
    id: int
    endpoint: str
    active: bool
    created_at: datetime  # KST


@dataclass(frozen=True)
class WatchAreaRow:
    id: int
    subscription_id: int
    kind: str
    lng: float
    lat: float
    radius_m: int
    created_at: datetime  # KST
    expires_at: datetime | None


def _utc(t: datetime) -> datetime:
    out = to_utc_naive(t)
    assert out is not None
    return out


def _kst(t: datetime) -> datetime:
    out = to_kst(t)
    assert out is not None
    return out


class PushRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def upsert_subscription(
        self, endpoint: str, p256dh: str, auth: str, now: datetime
    ) -> SubscriptionRow:
        """같은 endpoint 면 키를 새로 하고 다시 켠다 (id 그대로)."""
        row = {
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "active": True,
            "created_at": _utc(now),
        }
        stmt = insert(PushSubscriptionEntity).values(row)
        stmt = stmt.on_duplicate_key_update(
            p256dh=stmt.inserted.p256dh, auth=stmt.inserted.auth, active=True
        )
        with self._sessions.begin() as s:
            s.execute(stmt)
        found = self.subscription(endpoint)
        assert found is not None
        return found

    def subscription(self, endpoint: str) -> SubscriptionRow | None:
        e = PushSubscriptionEntity
        with self._sessions.begin() as s:
            row = s.scalar(select(e).where(e.endpoint == endpoint))
            if row is None:
                return None
            return SubscriptionRow(row.id, row.endpoint, bool(row.active), _kst(row.created_at))

    def deactivate(self, endpoint: str) -> bool:
        e = PushSubscriptionEntity
        with self._sessions.begin() as s:
            result = s.execute(update(e).where(e.endpoint == endpoint).values(active=False))
            assert isinstance(result, CursorResult)
            return bool(result.rowcount)

    def areas(self, subscription_id: int) -> list[WatchAreaRow]:
        e = WatchAreaEntity
        stmt = select(e).where(e.subscription_id == subscription_id).order_by(e.id)
        with self._sessions.begin() as s:
            return [self._area(r) for r in s.scalars(stmt)]

    def add_area(
        self,
        subscription_id: int,
        kind: str,
        lng: float,
        lat: float,
        radius_m: int,
        now: datetime,
        expires_at: datetime | None,
    ) -> WatchAreaRow:
        row = WatchAreaEntity(
            subscription_id=subscription_id,
            kind=kind,
            lng=Decimal(f"{lng:.7f}"),
            lat=Decimal(f"{lat:.7f}"),
            radius_m=radius_m,
            created_at=_utc(now),
            expires_at=_utc(expires_at) if expires_at else None,
        )
        with self._sessions.begin() as s:
            s.add(row)
            s.flush()
            return self._area(row)

    def delete_areas(self, subscription_id: int, kind: str) -> int:
        e = WatchAreaEntity
        with self._sessions.begin() as s:
            result = s.execute(
                delete(e).where(e.subscription_id == subscription_id, e.kind == kind)
            )
            assert isinstance(result, CursorResult)
            return int(result.rowcount or 0)

    def delete_area(self, subscription_id: int, area_id: int) -> int:
        e = WatchAreaEntity
        with self._sessions.begin() as s:
            result = s.execute(
                delete(e).where(e.subscription_id == subscription_id, e.id == area_id)
            )
            assert isinstance(result, CursorResult)
            return int(result.rowcount or 0)

    def purge_expired(self, subscription_id: int, now: datetime) -> int:
        e = WatchAreaEntity
        with self._sessions.begin() as s:
            result = s.execute(
                delete(e).where(
                    e.subscription_id == subscription_id,
                    e.expires_at.is_not(None),
                    e.expires_at <= _utc(now),
                )
            )
            assert isinstance(result, CursorResult)
            return int(result.rowcount or 0)

    def truncate(self) -> None:
        """테스트용. 운영 코드에서 부르지 않는다 (watch_areas·push_sends 는 FK CASCADE)."""
        with self._sessions.begin() as s:
            s.query(PushSubscriptionEntity).delete()

    @staticmethod
    def _area(e: WatchAreaEntity) -> WatchAreaRow:
        return WatchAreaRow(
            id=e.id,
            subscription_id=e.subscription_id,
            kind=e.kind,
            lng=float(e.lng),
            lat=float(e.lat),
            radius_m=e.radius_m,
            created_at=_kst(e.created_at),
            expires_at=to_kst(e.expires_at),
        )
