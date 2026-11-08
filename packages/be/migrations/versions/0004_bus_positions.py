"""bus_positions — 워커가 보낸 버스 위치 (T6.2, INTERFACE §1.2 v0.13, ADR-013 D)

보정 계열(bus_corrections)은 T6.3 에서 계산 방식과 함께 만든다.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bus_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_id", sa.String(16), nullable=False),
        sa.Column("veh_id", sa.String(16), nullable=False),
        sa.Column("plain_no", sa.String(16), nullable=True),
        sa.Column("data_tm", sa.DateTime(), nullable=False),  # UTC
        sa.Column("lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("sect_ord", sa.Integer(), nullable=True),
        sa.Column("section_id", sa.String(16), nullable=True),
        sa.Column("sect_dist", sa.Float(), nullable=True),
        sa.Column("stop_flag", sa.Boolean(), nullable=True),
        sa.Column("last_stn_id", sa.String(16), nullable=True),
        sa.Column("next_st_id", sa.String(16), nullable=True),
        sa.Column("is_run", sa.Boolean(), nullable=True),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("ref", sa.String(255), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),  # UTC
        sa.UniqueConstraint("route_id", "veh_id", "data_tm", name="uq_bus_route_veh_tm"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_bus_route_tm", "bus_positions", ["route_id", "data_tm"])


def downgrade() -> None:
    op.drop_index("ix_bus_route_tm", table_name="bus_positions")
    op.drop_table("bus_positions")
