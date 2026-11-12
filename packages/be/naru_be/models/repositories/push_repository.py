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

from naru_be.models.entities.push import PushSendEntity, PushSubscriptionEntity, WatchAreaEntity
from naru_be.models.repositories.closure_repository import to_kst, to_utc_naive


@dataclass(frozen=True)
class SubscriptionRow:
    id: int
    endpoint: str
    active: bool
    created_at: datetime  # KST


@dataclass(frozen=True)
class SubscriptionKeys:
    """발송에 쓰는 구독 — endpoint 와 키 (T7.9)."""

    id: int
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class PushSendRow:
    id: int
    subscription_id: int
    event_id: str
    kind: str  # created | confirmed
    due_at: datetime  # KST
    sent_at: datetime | None
    http_status: int | None


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

    # ---- 발송 (T7.9) ----
    def subscriptions_with_areas(
        self, now: datetime
    ) -> list[tuple[SubscriptionKeys, list[WatchAreaRow]]]:
        """켜진 구독과 그 관심 지역(만료된 last_seen 은 지우고). 관심 지역이 없는 구독은 뺀다."""
        s_e, a_e = PushSubscriptionEntity, WatchAreaEntity
        with self._sessions.begin() as s:
            s.execute(delete(a_e).where(a_e.expires_at.is_not(None), a_e.expires_at <= _utc(now)))
            subs = list(s.scalars(select(s_e).where(s_e.active.is_(True)).order_by(s_e.id)))
            areas = list(s.scalars(select(a_e).order_by(a_e.id)))
            by_sub: dict[int, list[WatchAreaRow]] = {}
            for a in areas:
                by_sub.setdefault(a.subscription_id, []).append(self._area(a))
            return [
                (SubscriptionKeys(x.id, x.endpoint, x.p256dh, x.auth), by_sub[x.id])
                for x in subs
                if x.id in by_sub
            ]

    def existing_sends(self) -> set[tuple[int, str, str]]:
        e = PushSendEntity
        with self._sessions.begin() as s:
            rows = s.execute(select(e.subscription_id, e.event_id, e.kind)).all()
            return {(int(a), str(b), str(c)) for a, b, c in rows}

    def queue_sends(self, planned: list[tuple[int, str, str, datetime]]) -> int:
        """(구독, 사건, 종류)마다 한 번 — 유일키가 막는다(INSERT IGNORE). 새로 줄 선 수."""
        if not planned:
            return 0
        rows = [
            {"subscription_id": sid, "event_id": eid, "kind": kind, "due_at": _utc(due)}
            for sid, eid, kind, due in planned
        ]
        stmt = insert(PushSendEntity).prefix_with("IGNORE").values(rows)
        with self._sessions.begin() as s:
            result = s.execute(stmt)
            assert isinstance(result, CursorResult)
            return int(result.rowcount or 0)

    def due_sends(self, now: datetime) -> list[tuple[PushSendRow, SubscriptionKeys]]:
        """아직 안 보냈고 때가 된 것 — 켜진 구독만, 줄 선 순서."""
        e, s_e = PushSendEntity, PushSubscriptionEntity
        stmt = (
            select(e, s_e)
            .join(s_e, s_e.id == e.subscription_id)
            .where(e.sent_at.is_(None), e.due_at <= _utc(now), s_e.active.is_(True))
            .order_by(e.id)
        )
        with self._sessions.begin() as s:
            return [
                (
                    PushSendRow(
                        x.id, x.subscription_id, x.event_id, x.kind, _kst(x.due_at), None, None
                    ),
                    SubscriptionKeys(sub.id, sub.endpoint, sub.p256dh, sub.auth),
                )
                for x, sub in s.execute(stmt).all()
            ]

    def mark_sent(self, send_id: int, http_status: int, now: datetime) -> None:
        e = PushSendEntity
        with self._sessions.begin() as s:
            s.execute(
                update(e).where(e.id == send_id).values(sent_at=_utc(now), http_status=http_status)
            )
            if 200 <= http_status < 300:
                sub_id = s.scalar(select(e.subscription_id).where(e.id == send_id))
                s.execute(
                    update(PushSubscriptionEntity)
                    .where(PushSubscriptionEntity.id == sub_id)
                    .values(last_ok_at=_utc(now))
                )

    def deactivate_id(self, subscription_id: int) -> None:
        e = PushSubscriptionEntity
        with self._sessions.begin() as s:
            s.execute(update(e).where(e.id == subscription_id).values(active=False))

    def sends(self) -> list[PushSendRow]:
        """테스트·점검용 — 줄 선 것 전부."""
        e = PushSendEntity
        with self._sessions.begin() as s:
            return [
                PushSendRow(
                    x.id,
                    x.subscription_id,
                    x.event_id,
                    x.kind,
                    _kst(x.due_at),
                    to_kst(x.sent_at),
                    x.http_status,
                )
                for x in s.scalars(select(e).order_by(e.id))
            ]

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
