"""reports 테이블 — 통제 제보(INTERFACE §8, T7.15). 기록만, 판단 없음.

좌표·기기 토큰 원문은 없다. 시각은 UTC.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from naru_be.models.entities.base import Base


class ReportEntity(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_cw_at", "crosswalk_id", "reported_at"),
        Index("ix_reports_device_cw", "device_hash", "crosswalk_id"),
        Index("ix_reports_source_at", "source", "reported_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    crosswalk_id: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16))  # blocked | open
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    accuracy_m: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))  # user | field
    device_hash: Mapped[str] = mapped_column(CHAR(64))  # sha256(기기 토큰)
