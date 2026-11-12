"""DB 엔진·세션 — SQLAlchemy 2 + PyMySQL (CONVENTIONS §4.4).

Repository 는 sessionmaker 를 생성자로 받는다. 시간은 UTC DATETIME(0) 로 저장한다
(docker compose MySQL 의 서버 타임존도 UTC). 변환은 Repository 가 한다.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600, future=True)


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
