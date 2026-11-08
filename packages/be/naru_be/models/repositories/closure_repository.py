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
from naru_be.models.domain.types import CandidateMeta, IntakeResult
from naru_be.models.entities.candidate_batch import CandidateBatchEntity
from naru_be.models.entities.closure_state import ClosureStateEntity
from naru_contracts import (
    CandidateSummary,
    ClosureEvent,
    ClosureState,
    ClosureType,
    DataAsOf,
    Evidence,
    Impact,
    NoticeRef,
    Source,
    Status,
    Window,
)

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

    def upsert_many(
        self, states: Iterable[ClosureState], candidate_id: str, meta: CandidateMeta | None = None
    ) -> int:
        """meta(ADR-012): 후보의 종류·출처·summary·notice. 없으면 null(테스트의 직접 저장)."""
        rows = [self._row(state, candidate_id, meta) for state in states]
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

    def attach(
        self,
        crosswalk_ids: set[str],
        window: Window,
        sources: frozenset[str],
        evidence: list[Evidence],
    ) -> list[str]:
        """같은 횡단보도·겹치는 시각인 그 출처 후보들의 모든 행에 근거를 더한다 (T6.1 — 돌발이
        공지를 확인). 이미 있는 근거(같은 acc_id)는 건너뛴다. 붙인 후보 ID."""
        e = ClosureStateEntity
        start, end = to_utc_naive(window.start), to_utc_naive(window.end)
        add = [ev.model_dump(mode="json") for ev in evidence]
        with self._sessions.begin() as s:
            hits = s.execute(
                select(e.candidate_id, e.window_start, e.window_end).where(
                    e.crosswalk_id.in_(crosswalk_ids), e.source.in_(sources)
                )
            ).all()
            linked = sorted({c for c, ws, we in hits if _overlaps(ws, we, start, end)})
            for row in s.scalars(select(e).where(e.candidate_id.in_(linked))) if linked else ():
                have = {_ev_key(ev) for ev in row.evidence}
                new = [ev for ev in add if _ev_key(ev) not in have]
                if new:
                    row.evidence = [*row.evidence, *new]
        return linked

    def linked_evidence(
        self, crosswalk_ids: set[str], window: Window, source: str
    ) -> list[Evidence]:
        """같은 횡단보도·겹치는 시각인 그 출처 행들의 근거 (공지가 돌발보다 늦게 올 때, T6.1).
        엔진이 붙인 상태 전이·규칙 근거는 빼고, 같은 acc_id 는 한 번."""
        e = ClosureStateEntity
        start, end = to_utc_naive(window.start), to_utc_naive(window.end)
        with self._sessions.begin() as s:
            rows = s.execute(
                select(e.window_start, e.window_end, e.evidence).where(
                    e.crosswalk_id.in_(crosswalk_ids), e.source == source
                )
            ).all()
        out: list[Evidence] = []
        seen: set[str] = set()
        for ws, we, evidence in rows:
            if not _overlaps(ws, we, start, end):
                continue
            for ev in evidence:
                detail = ev.get("detail")
                engine_made = isinstance(detail, dict) and (
                    "transition" in detail or "rule" in detail
                )
                if engine_made or _ev_key(ev) in seen:
                    continue
                seen.add(_ev_key(ev))
                out.append(Evidence.model_validate(ev))
        return out

    def active_at(self, t: datetime, bbox: Bbox) -> list[ClosureState]:
        """t 에 살아 있는 상태: window_start <= t <= window_end+grace, bbox 안. status 저장값."""
        return self.active_between(t, t, bbox)

    def active_horizon(self, t: datetime, bbox: Bbox) -> list[ClosureState]:
        """t 에 살아 있거나 t 뒤 route_horizon_min 안에 시작하는 상태 (route·closures 공통 지평)."""
        return self.active_between(t, t + timedelta(minutes=self.settings.route_horizon_min), bbox)

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

    def events(self, bbox: Bbox | None = None) -> list[ClosureEvent]:
        """(reason, window) 사건 묶음 — 서로 다른 횡단보도 수·범위·approx (INTERFACE §3.1, ADR-010).

        bbox 면 그 안의 상태만 묶는다. 순서는 시작 늦은 것 먼저, 시작 없는 것은 끝.
        """
        e = ClosureStateEntity
        stmt = select(
            e.reason,
            e.window_start,
            e.window_end,
            func.count(func.distinct(e.crosswalk_id)),
            func.min(e.lng),
            func.min(e.lat),
            func.max(e.lng),
            func.max(e.lat),
            func.max(e.approx),
        ).group_by(e.reason, e.window_start, e.window_end)
        if bbox is not None:
            stmt = stmt.where(e.lng.between(Decimal(str(bbox[0])), Decimal(str(bbox[2])))).where(
                e.lat.between(Decimal(str(bbox[1])), Decimal(str(bbox[3])))
            )
        stmt = stmt.order_by(e.window_start.is_(None), e.window_start.desc(), e.reason)
        # 사건마다 후보 메타(ADR-012) — 같은 사건의 행은 같은 item 에서 와서 메타가 같다
        meta_stmt = select(
            e.reason, e.window_start, e.window_end, e.source, e.type, e.summary, e.notice
        ).where(e.source.is_not(None))
        with self._sessions.begin() as s:
            rows = s.execute(stmt).all()
            metas: dict[tuple[object, ...], tuple[object, ...]] = {}
            for reason, start, end, *meta in s.execute(meta_stmt).all():
                metas.setdefault((reason, start, end), tuple(meta))
        return [
            ClosureEvent(
                reason=reason,
                window=Window(start=to_kst(start), end=to_kst(end)),
                crosswalks=int(n),
                bbox=(float(min_lng), float(min_lat), float(max_lng), float(max_lat)),
                approx=bool(approx),
                **_event_meta(metas.get((reason, start, end))),
            )
            for reason, start, end, n, min_lng, min_lat, max_lng, max_lat, approx in rows
        ]

    def data_as_of(self) -> DataAsOf:
        """출처마다 저장된 통제의 가장 늦은 근거 시각 (INTERFACE §3.1 v0.12, ADR-011 C·ADR-012).

        공지(smpa·topis_notice)는 게시 시각, course 는 시각표 게시 시각(상태 전이 근거는 뺀다),
        topis_incident 는 돌발 수신 시각. 그 출처가 없으면 null.
        """
        e = ClosureStateEntity
        stmt = select(e.source, e.evidence, e.notice).where(e.source.is_not(None))
        latest: dict[str, datetime] = {}
        with self._sessions.begin() as s:
            for source, evidence, notice in s.execute(stmt).all():
                key = str(source)
                for at in _source_times(key, evidence, notice):
                    if key not in latest or at > latest[key]:
                        latest[key] = at
        heard = self._last_received(Source.incident.value)  # 돌발은 받은 시각(빈 배치·재전송 포함)
        if heard is not None and heard > latest.get(Source.incident.value, heard):
            latest[Source.incident.value] = heard
        elif heard is not None:
            latest.setdefault(Source.incident.value, heard)
        kst = {k: v.astimezone(KST) for k, v in latest.items()}
        # 키(ADR-011 C) ↔ 출처: topis_incident = incident(TOPIS 돌발),
        # topis_notice = topis(TOPIS 공지)
        return DataAsOf(
            topis_incident=kst.get(Source.incident.value),
            topis_notice=kst.get(Source.topis.value),
            smpa=kst.get(Source.smpa.value),
            course=kst.get(Source.course.value),
        )

    def count(self) -> int:
        with self._sessions.begin() as s:
            return int(s.scalar(select(func.count()).select_from(ClosureStateEntity)) or 0)

    def batch_result(self, batch_id: str) -> IntakeResult | None:
        """이미 처리한 배치면 그때의 결과 (INTERFACE §1.1 멱등). 아니면 None."""
        with self._sessions.begin() as s:
            row = s.get(CandidateBatchEntity, batch_id)
            if row is None:
                return None
            return IntakeResult(
                row.batch_id, row.accepted, row.review_required, row.crosswalks_updated, True
            )

    def touch_batch(self, batch_id: str) -> None:
        """같은 배치를 다시 받았다 — 받은 시각만 새로 (돌발 수신 시각 = data_as_of, T6.1)."""
        with self._sessions.begin() as s:
            row = s.get(CandidateBatchEntity, batch_id)
            if row is not None:
                row.received_at = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    def _last_received(self, producer: str) -> datetime | None:
        b = CandidateBatchEntity
        with self._sessions.begin() as s:
            at = s.scalar(select(func.max(b.received_at)).where(b.producer == producer))
        return None if at is None else at.replace(tzinfo=UTC)

    def save_batch(self, result: IntakeResult, producer: str, produced_at: datetime) -> None:
        produced = to_utc_naive(produced_at)
        assert produced is not None
        with self._sessions.begin() as s:
            s.add(
                CandidateBatchEntity(
                    batch_id=result.batch_id,
                    producer=producer,
                    produced_at=produced,
                    received_at=datetime.now(UTC).replace(tzinfo=None, microsecond=0),
                    accepted=result.accepted,
                    review_required=result.review_required,
                    crosswalks_updated=result.crosswalks_updated,
                )
            )

    def truncate(self) -> None:
        """테스트용. 운영 코드에서 부르지 않는다."""
        with self._sessions.begin() as s:
            s.query(ClosureStateEntity).delete()
            s.query(CandidateBatchEntity).delete()

    @staticmethod
    def _row(
        state: ClosureState, candidate_id: str, meta: CandidateMeta | None
    ) -> dict[str, object]:
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
            "source": meta.source if meta else None,
            "type": meta.type if meta else None,
            "summary": meta.summary if meta else None,
            "notice": meta.notice if meta else None,
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


def _event_meta(meta: tuple[object, ...] | None) -> dict[str, object]:
    """저장된 메타 → ClosureEvent 칸. v0.12 전 행이면 전부 null."""
    if meta is None:
        return {"type": None, "source": None, "summary": None, "notice": None}
    source, type_, summary, notice = meta
    return {
        "type": ClosureType(str(type_)) if type_ else None,
        "source": Source(str(source)) if source else None,
        "summary": CandidateSummary.model_validate(summary) if summary else None,
        "notice": NoticeRef.model_validate(notice) if notice else None,
    }


def _source_times(source: str, evidence: object, notice: object) -> list[datetime]:
    """그 출처의 데이터 시각들 — 공지는 게시 시각, 나머지는 근거 시각(상태 전이 근거는 뺀다)."""
    if source in (Source.smpa.value, Source.topis.value):
        published = notice.get("published_at") if isinstance(notice, dict) else None
        return [datetime.fromisoformat(published)] if isinstance(published, str) else []
    kind = {Source.course.value: "timetable", Source.incident.value: "topis_incident"}.get(source)
    out: list[datetime] = []
    for ev in evidence if isinstance(evidence, list) else []:
        if not isinstance(ev, dict) or ev.get("kind") != kind:
            continue
        detail = ev.get("detail")
        if isinstance(detail, dict) and "transition" in detail:
            continue  # 엔진이 붙인 상태 전이(해제 예정 등)는 데이터 시각이 아니다
        at = ev.get("at")
        if isinstance(at, str):
            out.append(datetime.fromisoformat(at))
    return out


def _overlaps(
    a_start: datetime | None,
    a_end: datetime | None,
    b_start: datetime | None,
    b_end: datetime | None,
) -> bool:
    """두 창이 겹치나 (UTC naive, 끝 없음 = 열림)."""
    return (a_end is None or b_start is None or b_start < a_end) and (
        b_end is None or a_start is None or a_start < b_end
    )


def _ev_key(ev: dict[str, object]) -> str:
    """근거 중복 키 — 돌발은 acc_id(원문 기록 파일이 바뀌어도 같은 돌발), 나머지는 종류·ref."""
    detail = ev.get("detail")
    acc = detail.get("acc_id") if isinstance(detail, dict) else None
    return f"{ev.get('kind')}:{acc}" if acc else f"{ev.get('kind')}:{ev.get('ref')}"
