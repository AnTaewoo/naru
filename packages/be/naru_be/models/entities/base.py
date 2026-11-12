"""SQLAlchemy Declarative Base — 엔티티 전부 여기서 상속. Alembic 이 metadata 를 본다."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
