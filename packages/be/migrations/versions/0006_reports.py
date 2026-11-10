"""reports — 통제 제보 (T7.15, INTERFACE §8 v0.14 보충, 태우 지시 11/10)

기록만 — 경로·확신도·상태에 쓰지 않는다. 좌표·기기 토큰 원문은 없다(기기는 sha256).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-10 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crosswalk_id", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),  # blocked | open
        sa.Column("reported_at", sa.DateTime(), nullable=False),  # UTC, 서버가 받은 시각
        sa.Column("accuracy_m", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),  # user | field
        sa.Column("device_hash", sa.CHAR(64), nullable=False),  # sha256(기기 토큰)
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_reports_cw_at", "reports", ["crosswalk_id", "reported_at"])
    op.create_index("ix_reports_device_cw", "reports", ["device_hash", "crosswalk_id"])
    op.create_index("ix_reports_source_at", "reports", ["source", "reported_at"])


def downgrade() -> None:
    op.drop_index("ix_reports_source_at", table_name="reports")
    op.drop_index("ix_reports_device_cw", table_name="reports")
    op.drop_index("ix_reports_cw_at", table_name="reports")
    op.drop_table("reports")
