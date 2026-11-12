"""closure_events.march — 행진 확률 모델 프로필 (T7.16, ADR-015 B)

대상 행진 사건만 JSON {path(EPSG:4326), length_m, queue_m, width_m, s{횡단보도 id: 경로 위 m}}.
대상이 아니면 NULL. 표를 새로 만들지 않는다 (사건 id 가 열쇠, 문서형이라 JSON — CONVENTIONS §4.4).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-10 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("closure_events", sa.Column("march", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("closure_events", "march")
