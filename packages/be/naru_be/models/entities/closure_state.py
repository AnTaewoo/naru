"""closure_states 테이블 — 횡단보도 하나 x 후보 하나의 현재 상태 (ARCHITECTURE, T2.4).

컬럼 규칙 (CONVENTIONS §4.4): 시간 DATETIME(0) UTC naive, 좌표 DECIMAL(10,7) + 복합 인덱스
(lng, lat), 문서형(evidence)만 JSON, enum 은 VARCHAR(32) + 앱 검증.
유일키 (candidate_id, crosswalk_id) 로 upsert.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Float, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from naru_be.models.entities.base import Base


class ClosureStateEntity(Base):
    __tablename__ = "closure_states"
    __table_args__ = (
        UniqueConstraint("candidate_id", "crosswalk_id", name="uq_closure_candidate_crosswalk"),
        Index("ix_closure_lng_lat", "lng", "lat"),
        Index("ix_closure_window", "window_start", "window_end"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(64))
    crosswalk_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))  # UTC
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))  # UTC
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    lng: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    lat: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    impact: Mapped[str] = mapped_column(String(32), default="blocks")
    approx: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    # v0.12 (ADR-012) — 후보의 종류·출처·summary·notice_ref 그대로. 그 전에 저장된 행은 null
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    notice: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
