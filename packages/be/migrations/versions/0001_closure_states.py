"""closure_states — 횡단보도 x 후보 상태 (T2.4, INTERFACE v0.6 ClosureState + candidate_id)

Revision ID: 0001
Revises:
Create Date: 2026-11-07 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "closure_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.String(64), nullable=False),
        sa.Column("crosswalk_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=True),  # UTC
        sa.Column("window_end", sa.DateTime(), nullable=True),  # UTC
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("impact", sa.String(32), nullable=False, server_default="blocks"),
        sa.Column("approx", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),  # UTC
        sa.UniqueConstraint("candidate_id", "crosswalk_id", name="uq_closure_candidate_crosswalk"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_closure_lng_lat", "closure_states", ["lng", "lat"])
    op.create_index("ix_closure_window", "closure_states", ["window_start", "window_end"])


def downgrade() -> None:
    op.drop_index("ix_closure_window", table_name="closure_states")
    op.drop_index("ix_closure_lng_lat", table_name="closure_states")
    op.drop_table("closure_states")
