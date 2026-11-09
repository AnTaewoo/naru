"""closure_events 테이블 — 사건 통제 구역 (T7.2, ADR-014 A). 사건 id 로 구역·중심만 붙인다.

컬럼 규칙 (CONVENTIONS §4.4): 시간 DATETIME(0) UTC naive, 좌표 DECIMAL(10,7),
문서형(GeoJSON)만 JSON.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from naru_be.models.entities.base import Base


class ClosureEventEntity(Base):
    __tablename__ = "closure_events"

    event_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))  # UTC
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))  # UTC
    area: Mapped[dict[str, object]] = mapped_column(JSON)  # GeoJSON Polygon·MultiPolygon
    centroid_lng: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    centroid_lat: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
