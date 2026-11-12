"""bus_positions 테이블 — 워커가 보낸 버스 위치(INTERFACE §1.2, T6.2). 판단 없이 그대로.

(노선, 차량, data_tm)이 같으면 한 번만 — 같은 응답을 다시 받아도 쌓이지 않는다. 시각은 UTC.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from naru_be.models.entities.base import Base


class BusPositionEntity(Base):
    __tablename__ = "bus_positions"
    __table_args__ = (
        UniqueConstraint("route_id", "veh_id", "data_tm", name="uq_bus_route_veh_tm"),
        Index("ix_bus_route_tm", "route_id", "data_tm"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(String(16))
    veh_id: Mapped[str] = mapped_column(String(16))
    plain_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    data_tm: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    lng: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    lat: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    sect_ord: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sect_dist: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_stn_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    next_st_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_run: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    batch_id: Mapped[str] = mapped_column(String(64))
    ref: Mapped[str] = mapped_column(String(255))  # 원문 기록 파일
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
