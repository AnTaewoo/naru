"""Alembic env — URL 은 Settings(DATABASE_URL) 또는 `-x url=...`. metadata 는 naru_be 엔티티."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from naru_be.config import Settings
from naru_be.models.entities.base import Base
from naru_be.models.entities.bus_position import BusPositionEntity
from naru_be.models.entities.candidate_batch import CandidateBatchEntity
from naru_be.models.entities.closure_event import ClosureEventEntity
from naru_be.models.entities.closure_state import ClosureStateEntity

config = context.config
if config.config_file_name is not None:
    # 테스트처럼 한 프로세스에서 마이그레이션을 돌려도 이미 있는 로거(워커 등)를 끄지 않는다 (T6.1)
    fileConfig(config.config_file_name, disable_existing_loggers=False)

url = context.get_x_argument(as_dictionary=True).get("url") or Settings().database_url
config.set_main_option("sqlalchemy.url", url)
target_metadata = Base.metadata
TABLES = (  # metadata 등록
    ClosureStateEntity.__tablename__,
    CandidateBatchEntity.__tablename__,
    BusPositionEntity.__tablename__,
    ClosureEventEntity.__tablename__,
)


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
