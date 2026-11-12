"""candidate_batches — 받은 배치와 처리 결과 (T3.4, INTERFACE §1.1 batch_id 멱등)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_batches",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("producer", sa.String(32), nullable=False),
        sa.Column("produced_at", sa.DateTime(), nullable=False),  # UTC
        sa.Column("received_at", sa.DateTime(), nullable=False),  # UTC
        sa.Column("accepted", sa.Integer(), nullable=False),
        sa.Column("review_required", sa.Integer(), nullable=False),
        sa.Column("crosswalks_updated", sa.Integer(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )


def downgrade() -> None:
    op.drop_table("candidate_batches")
