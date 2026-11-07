"""candidate_batches 테이블 — 배치 하나의 처리 결과. batch_id 가 PK 라 재전송은 조회로 끝난다."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from naru_be.models.entities.base import Base


class CandidateBatchEntity(Base):
    __tablename__ = "candidate_batches"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    producer: Mapped[str] = mapped_column(String(32))
    produced_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))  # UTC
    accepted: Mapped[int] = mapped_column(Integer)
    review_required: Mapped[int] = mapped_column(Integer)
    crosswalks_updated: Mapped[int] = mapped_column(Integer)
