"""closure_states — 후보의 종류·출처·summary·notice_ref (T5.9, INTERFACE v0.12, ADR-012)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08 (KST)

v0.12 전에 저장된 행은 null 이다 — 같은 배치를 다시 받으면(재수집) 채워진다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("closure_states", sa.Column("source", sa.String(32), nullable=True))
    op.add_column("closure_states", sa.Column("type", sa.String(32), nullable=True))
    op.add_column("closure_states", sa.Column("summary", sa.JSON(), nullable=True))
    op.add_column("closure_states", sa.Column("notice", sa.JSON(), nullable=True))


def downgrade() -> None:
    for col in ("notice", "summary", "type", "source"):
        op.drop_column("closure_states", col)
