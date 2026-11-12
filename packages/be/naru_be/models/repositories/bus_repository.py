"""BusRepository — bus_positions 쓰기·세기 (T6.2). DB 접근은 Repository 만 (ARCHITECTURE BE Model).

(노선, 차량, data_tm)이 같은 위치는 INSERT IGNORE 로 건너뛴다 — 재전송·같은 응답 재수신에 안전.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from naru_be.models.entities.bus_position import BusPositionEntity
from naru_be.models.repositories.closure_repository import to_utc_naive
from naru_contracts import BusPositionBatch


class BusRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def save(self, batch: BusPositionBatch) -> int:
        """새로 저장한 위치 수."""
        if not batch.positions:
            return 0
        received = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        rows = [
            {
                "route_id": batch.route_id,
                "veh_id": p.veh_id,
                "plain_no": p.plain_no,
                "data_tm": to_utc_naive(p.data_tm),
                "lng": Decimal(f"{p.lng:.7f}"),
                "lat": Decimal(f"{p.lat:.7f}"),
                "sect_ord": p.sect_ord,
                "section_id": p.section_id,
                "sect_dist": p.sect_dist,
                "stop_flag": p.stop_flag,
                "last_stn_id": p.last_stn_id,
                "next_st_id": p.next_st_id,
                "is_run": p.is_run,
                "batch_id": batch.batch_id,
                "ref": batch.ref,
                "received_at": received,
            }
            for p in batch.positions
        ]
        stmt = insert(BusPositionEntity).prefix_with("IGNORE").values(rows)
        with self._sessions.begin() as s:
            result = s.execute(stmt)
            assert isinstance(result, CursorResult)  # INSERT 는 rowcount 가 있다
            return int(result.rowcount or 0)

    def count(self, route_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(BusPositionEntity)
        if route_id is not None:
            stmt = stmt.where(BusPositionEntity.route_id == route_id)
        with self._sessions.begin() as s:
            return int(s.scalar(stmt) or 0)

    def truncate(self) -> None:
        """테스트용. 운영 코드에서 부르지 않는다."""
        with self._sessions.begin() as s:
            s.query(BusPositionEntity).delete()
