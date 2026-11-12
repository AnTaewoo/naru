"""closure_events — 사건 통제 구역 (T7.2, INTERFACE §3.1 v0.14, ADR-014 A)

사건 = closure_states 의 (reason, 시작, 끝) 묶음. 그 사건 후보가 횡단보도를 고른 모양(점 30 m·
선 15 m·구간 도로 경로 + 등급 버퍼)의 union 을 5 m 단순화한 EPSG:4326 GeoJSON 과 중심. 목록·상태는
여전히 closure_states 가 진실이고, 이 표는 id 로 구역만 붙인다.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09 (KST)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "closure_events",
        sa.Column("event_id", sa.String(12), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=True),  # UTC
        sa.Column("window_end", sa.DateTime(), nullable=True),  # UTC
        sa.Column("area", sa.JSON(), nullable=False),  # GeoJSON Polygon·MultiPolygon (EPSG:4326)
        sa.Column("centroid_lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("centroid_lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),  # UTC
    )


def downgrade() -> None:
    op.drop_table("closure_events")
