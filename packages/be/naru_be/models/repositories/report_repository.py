"""ReportRepository — reports 쓰기·세기 (T7.15, INTERFACE §8). DB 접근은 Repository 만.

시각은 UTC 로 저장하고 KST 로 돌려준다. 좌표·기기 토큰 원문은 받지도 않는다.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from naru_be.models.entities.report import ReportEntity
from naru_be.models.repositories.closure_repository import to_kst, to_utc_naive
from naru_contracts.reports_api import ReportSource, ReportState


@dataclass(frozen=True)
class ReportRow:
    id: int
    crosswalk_id: str
    state: ReportState
    reported_at: datetime  # KST
    accuracy_m: int
    source: ReportSource
    device_hash: str


def _utc(t: datetime) -> datetime:
    out = to_utc_naive(t)
    assert out is not None
    return out


class ReportRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(
        self,
        crosswalk_id: str,
        state: ReportState,
        accuracy_m: int,
        source: ReportSource,
        device_hash: str,
        at: datetime,
    ) -> ReportRow:
        row = ReportEntity(
            crosswalk_id=crosswalk_id,
            state=state,
            reported_at=_utc(at),
            accuracy_m=accuracy_m,
            source=source,
            device_hash=device_hash,
        )
        with self._sessions.begin() as s:
            s.add(row)
            s.flush()
            return self._row(row)

    def last_at(self, device_hash: str, crosswalk_id: str) -> datetime | None:
        """이 기기가 이 횡단보도를 마지막으로 제보한 시각 (KST)."""
        e = ReportEntity
        stmt = select(func.max(e.reported_at)).where(
            e.device_hash == device_hash, e.crosswalk_id == crosswalk_id
        )
        with self._sessions.begin() as s:
            return to_kst(s.scalar(stmt))

    def recent_counts(
        self, ids: Collection[str], since: datetime, until: datetime
    ) -> dict[str, tuple[int, int]]:
        """[since, until] 제보 수 — 횡단보도마다 (blocked, open). 제보가 없는 id 는 빠진다."""
        e = ReportEntity
        stmt = (
            select(e.crosswalk_id, e.state, func.count())
            .where(e.crosswalk_id.in_(list(ids)))
            .where(e.reported_at.between(_utc(since), _utc(until)))
            .group_by(e.crosswalk_id, e.state)
        )
        out: dict[str, tuple[int, int]] = {}
        with self._sessions.begin() as s:
            for cid, state, n in s.execute(stmt):
                blocked, opened = out.get(cid, (0, 0))
                out[cid] = (blocked + n, opened) if state == "blocked" else (blocked, opened + n)
        return out

    def between(
        self, start: datetime, end: datetime, source: ReportSource | None = None
    ) -> list[ReportRow]:
        """[start, end] 제보, 시각 순 (현장 비교 — scripts/field_compare.py)."""
        e = ReportEntity
        stmt = select(e).where(e.reported_at.between(_utc(start), _utc(end)))
        if source is not None:
            stmt = stmt.where(e.source == source)
        with self._sessions.begin() as s:
            return [self._row(r) for r in s.scalars(stmt.order_by(e.reported_at, e.id))]

    def truncate(self) -> None:
        """테스트용. 운영 코드에서 부르지 않는다."""
        with self._sessions.begin() as s:
            s.query(ReportEntity).delete()

    @staticmethod
    def _row(e: ReportEntity) -> ReportRow:
        at = to_kst(e.reported_at)
        assert at is not None
        return ReportRow(
            id=e.id,
            crosswalk_id=e.crosswalk_id,
            state="blocked" if e.state == "blocked" else "open",
            reported_at=at,
            accuracy_m=e.accuracy_m,
            source="field" if e.source == "field" else "user",
            device_hash=e.device_hash,
        )
