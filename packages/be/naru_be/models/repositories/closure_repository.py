"""ClosureRepository — closure_states 읽고 쓰기. DB 접근은 여기만 (ARCHITECTURE BE Model, T2.4).

공개 메서드마다 `with self._sessions.begin() as s:` — 메서드 하나 = 트랜잭션 하나 (CONVENTIONS
§4.4). 입력은 tz-aware, 저장은 UTC naive DATETIME(0), 반환은 +09:00 (KST). 좌표 DECIMAL → float.
upsert 키 = (candidate_id, crosswalk_id): 같은 후보가 다시 오면 덮어쓴다.
배치 재전송 멱등(batch_id)은 CandidateIntake 몫.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session, sessionmaker

from naru_be.config import Settings
from naru_be.models.entities.closure_state import ClosureStateEntity
from naru_contracts import ClosureState, Evidence, Impact, Status, Window

KST = timezone(timedelta(hours=9))
Bbox = tuple[float, float, float, float]  # minLng, minLat, maxLng, maxLat


def to_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("오프셋 없는 시각은 저장하지 않는다")
    return value.astimezone(UTC).replace(tzinfo=None, microsecond=0)


def to_kst(value: datetime | None) -> datetime | None:
    return None if value is None else value.replace(tzinfo=UTC).astimezone(KST)


class ClosureRepository:
    def __init__(self, sessions: sessionmaker[Session], settings: Settings | None = None) -> None:
        self._sessions = sessions
        self.settings = settings or Settings()

    def upsert_many(self, states: Iterable[ClosureState], candidate_id: str) -> int:
        rows = [self._row(state, candidate_id) for state in states]
        if not rows:
            return 0
        stmt = insert(ClosureStateEntity).values(rows)
        update_cols = {
            c: stmt.inserted[c] for c in rows[0] if c not in ("candidate_id", "crosswalk_id")
        }
        with self._sessions.begin() as s:
            s.execute(stmt.on_duplicate_key_update(**update_cols))
        return len(rows)

    def upsert(self, state: ClosureState, candidate_id: str) -> None:
        self.upsert_many([state], candidate_id)

    def active_at(self, t: datetime, bbox: Bbox) -> list[ClosureState]:
        """t 에 살아 있는 상태: window_start <= t <= window_end+grace, bbox 안. status 저장값."""
        return self.active_between(t, t, bbox)

    def active_between(self, t0: datetime, t1: datetime, bbox: Bbox) -> list[ClosureState]:
        """[t0, t1] 과 겹치는 상태: window_start <= t1, window_end+grace >= t0 (라우팅 지평)."""
        if t0.tzinfo is None or t1.tzinfo is None:
            raise ValueError("오프셋 없는 시각")
        t0_utc, t1_utc = to_utc_naive(t0), to_utc_naive(t1)
        assert t0_utc is not None and t1_utc is not None
        grace = timedelta(minutes=self.settings.released_grace_min)
        e = ClosureStateEntity
        stmt = (
            select(e)
            .where(e.lng.between(Decimal(str(bbox[0])), Decimal(str(bbox[2]))))
            .where(e.lat.between(Decimal(str(bbox[1])), Decimal(str(bbox[3]))))
            .where(or_(e.window_start.is_(None), e.window_start <= t1_utc))
            .where(or_(e.window_end.is_(None), e.window_end >= t0_utc - grace))
            .order_by(e.crosswalk_id, e.candidate_id)
        )
        with self._sessions.begin() as s:
            return [self._state(row) for row in s.scalars(stmt)]

    def count(self) -> int:
        with self._sessions.begin() as s:
            return int(s.scalar(select(func.count()).select_from(ClosureStateEntity)) or 0)

    def truncate(self) -> None:
        """테스트용. 운영 코드에서 부르지 않는다."""
        with self._sessions.begin() as s:
            s.query(ClosureStateEntity).delete()

    @staticmethod
    def _row(state: ClosureState, candidate_id: str) -> dict[str, object]:
        return {
            "candidate_id": candidate_id,
            "crosswalk_id": state.crosswalk_id,
            "status": state.status.value,
            "confidence": state.confidence,
            "window_start": to_utc_naive(state.window.start),
            "window_end": to_utc_naive(state.window.end),
            "reason": state.reason,
            "evidence": [ev.model_dump(mode="json") for ev in state.evidence],
            "lng": Decimal(f"{state.lng:.7f}"),
            "lat": Decimal(f"{state.lat:.7f}"),
            "impact": state.impact.value,
            "approx": state.approx,
            "updated_at": datetime.now(UTC).replace(tzinfo=None, microsecond=0),
        }

    @staticmethod
    def _state(row: ClosureStateEntity) -> ClosureState:
        return ClosureState(
            crosswalk_id=row.crosswalk_id,
            status=Status(row.status),
            confidence=row.confidence,
            window=Window(start=to_kst(row.window_start), end=to_kst(row.window_end)),
            reason=row.reason,
            evidence=[Evidence.model_validate(ev) for ev in row.evidence],
            lng=float(row.lng),
            lat=float(row.lat),
            impact=Impact(row.impact),
            approx=row.approx,
        )
