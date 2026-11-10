"""알림 표 셋 (T7.8, ADR-014 C) — push_subscriptions · watch_areas · push_sends. 시각은 UTC."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from naru_be.models.entities.base import Base


class PushSubscriptionEntity(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(512), unique=True)
    p256dh: Mapped[str] = mapped_column(String(128))
    auth: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class WatchAreaEntity(Base):
    __tablename__ = "watch_areas"
    __table_args__ = (Index("ix_watch_sub", "subscription_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("push_subscriptions.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16))  # saved | last_seen
    lng: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    lat: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    radius_m: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PushSendEntity(Base):
    __tablename__ = "push_sends"
    __table_args__ = (UniqueConstraint("subscription_id", "event_id", "kind", name="uq_push_send"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("push_subscriptions.id", ondelete="CASCADE")
    )
    event_id: Mapped[str] = mapped_column(String(12))
    kind: Mapped[str] = mapped_column(String(16))  # created | confirmed
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
