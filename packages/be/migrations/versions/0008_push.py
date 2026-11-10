"""push_subscriptions · watch_areas · push_sends — 알림 (T7.8, ADR-014 C)

계정 없이 구독 endpoint 가 손잡이. 관심 지역 last_seen 은 150 m 격자·3시간(expires_at).
push_sends 는 (구독, 사건, 종류)마다 한 번(T7.9 발송). 시각은 UTC.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
MYSQL = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("endpoint", sa.String(512), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(128), nullable=False),
        sa.Column("auth", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),  # UTC
        sa.Column("last_ok_at", sa.DateTime(), nullable=True),  # UTC, 마지막 발송 성공
        **MYSQL,
    )
    op.create_table(
        "watch_areas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),  # saved | last_seen
        sa.Column("lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("radius_m", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),  # UTC
        sa.Column("expires_at", sa.DateTime(), nullable=True),  # UTC, last_seen 만
        **MYSQL,
    )
    op.create_index("ix_watch_sub", "watch_areas", ["subscription_id"])
    op.create_table(
        "push_sends",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(12), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),  # created | confirmed
        sa.Column("due_at", sa.DateTime(), nullable=False),  # UTC
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.UniqueConstraint("subscription_id", "event_id", "kind", name="uq_push_send"),
        **MYSQL,
    )


def downgrade() -> None:
    op.drop_table("push_sends")
    op.drop_index("ix_watch_sub", table_name="watch_areas")
    op.drop_table("watch_areas")
    op.drop_table("push_subscriptions")
