"""ClosureEngine — 후보 + 횡단보도 → ClosureState, 상태기계 (ARCHITECTURE 상태기계 표, T2.3).

  scheduled  후보 그대로 (시각표·공지·돌발 예고). confidence < review_confidence 면 적재는 하되
             라우팅은 안 쓴다 (라우터 몫)
  confirmed  실측 증거가 있는 후보가 window.start 를 지났을 때 — 코스 시각표(timetable),
             돌발 발생(topis_incident), 버스 이탈(bus_skip). 공지(notice)만 있는 후보는 시간이
             지나도 scheduled (실측이 와야 confirmed)
  released   window.end + released_grace_min 경과, 또는 bus_return 증거
전이마다 evidence 를 하나 더 붙인다 (detail.transition, detail.rule). window.end 가 없으면
start + unknown_end_hours 를 임시 end 로 두고 evidence 에 남긴다 (INTERFACE §1).
좌표는 CrosswalkIndex 의 관리번호 점. Flask·DB 모른다.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_contracts import ClosureCandidate, ClosureState, Evidence, EvidenceKind, Status, Window

CONFIRMING_EVIDENCE = frozenset(
    {EvidenceKind.timetable, EvidenceKind.topis_incident, EvidenceKind.bus_skip}
)


class ClosureEngine:
    def __init__(self, index: CrosswalkIndex, settings: Settings | None = None) -> None:
        self.index = index
        self.settings = settings or Settings()

    def effective_window(self, candidate: ClosureCandidate) -> tuple[Window, Evidence | None]:
        """end 가 없으면 start + unknown_end_hours. 그 사실을 evidence 로 돌려준다."""
        w = candidate.window
        if w.end is not None or w.start is None:
            return w, None
        end = w.start + timedelta(hours=self.settings.unknown_end_hours)
        note = Evidence(
            kind=candidate.evidence[0].kind,
            ref=candidate.evidence[0].ref,
            at=w.start,
            detail={"rule": "unknown_end", "end": end.isoformat()},
        )
        return Window(start=w.start, end=end), note

    def status_at(
        self, candidate: ClosureCandidate, at: datetime
    ) -> tuple[Status, Evidence | None]:
        """시각 `at` 의 상태와, 전이가 있었으면 그 evidence."""
        if candidate.status_hint is Status.zone_scheduled:
            return Status.zone_scheduled, None
        window, _ = self.effective_window(candidate)
        start, end = window.start, window.end
        base = candidate.evidence[0]
        confirmable = candidate.confidence >= self.settings.confirmed_confidence and any(
            e.kind in CONFIRMING_EVIDENCE for e in candidate.evidence
        )
        if end is not None and at >= end + timedelta(minutes=self.settings.released_grace_min):
            if candidate.status_hint is Status.scheduled and not confirmable:
                return Status.released, _transition(
                    base, end, "scheduled→released", "window_end+grace"
                )
            return Status.released, _transition(base, end, "confirmed→released", "window_end+grace")
        if candidate.status_hint is Status.confirmed:
            return Status.confirmed, None
        if confirmable and start is not None and at >= start:
            return Status.confirmed, _transition(base, start, "scheduled→confirmed", "window_start")
        return Status.scheduled, None

    def apply(
        self, candidate: ClosureCandidate, crosswalk_ids: Iterable[str], at: datetime | None = None
    ) -> list[ClosureState]:
        at = at or datetime.now(UTC)
        if at.tzinfo is None:
            raise ValueError("at 은 tz-aware 여야 한다")
        status, transition = self.status_at(candidate, at)
        window, unknown_end = self.effective_window(candidate)
        evidence = list(candidate.evidence)
        if unknown_end is not None:
            evidence.append(unknown_end)
        if transition is not None:
            evidence.append(transition)
        reason = _reason(candidate)
        states: list[ClosureState] = []
        for crosswalk_id in sorted(set(crosswalk_ids)):
            c = self.index.get(crosswalk_id)
            states.append(
                ClosureState(
                    crosswalk_id=crosswalk_id,
                    status=status,
                    confidence=candidate.confidence,
                    window=window,
                    reason=reason,
                    evidence=evidence,
                    lng=c.lng,
                    lat=c.lat,
                )
            )
        return states

    def bump_confidence(self, state: ClosureState, spike: Evidence) -> ClosureState:
        """혼잡 급등(rtd_spike)은 scheduled 의 confidence 만 올린다 (ADR-002). 상태는 그대로."""
        if spike.kind is not EvidenceKind.rtd_spike or state.status is not Status.scheduled:
            return state
        confidence = min(1.0, max(state.confidence, self.settings.review_confidence))
        return state.model_copy(
            update={"confidence": confidence, "evidence": [*state.evidence, spike]}
        )

    def release_by_evidence(
        self, state: ClosureState, evidence: Evidence, at: datetime
    ) -> ClosureState:
        """버스 복귀(bus_return) 등 실측 해제 신호 → released."""
        if evidence.kind is not EvidenceKind.bus_return or state.status is Status.released:
            return state
        transition = _transition(evidence, at, f"{state.status.value}→released", "bus_return")
        return state.model_copy(
            update={"status": Status.released, "evidence": [*state.evidence, transition]}
        )


def _transition(base: Evidence, at: datetime, transition: str, rule: str) -> Evidence:
    return Evidence(
        kind=base.kind, ref=base.ref, at=at, detail={"transition": transition, "rule": rule}
    )


def _reason(candidate: ClosureCandidate) -> str:
    detail = candidate.evidence[0].detail or {}
    section = detail.get("section")
    label = detail.get("label")
    if section:
        return (
            f"{candidate.type.value} {label} {section}"
            if label
            else f"{candidate.type.value} {section}"
        )
    if candidate.notice_ref is not None:
        return candidate.notice_ref.excerpt
    return f"{candidate.type.value} ({candidate.source.value})"
