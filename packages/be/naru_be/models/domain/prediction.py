"""막힘 예측 — 그 시각 나루가 이 횡단보도를 막힘으로 보나 (T7.15, INTERFACE §5).

라우터(routers.py)와 같은 규칙 하나:
  confirmed(그 시각 다시 판정) → 막힘 (라우터는 간선 제외)
  scheduled · 확신도 ≥ review_confidence(0.7) · 그 시각이 공지 창 안 → 막힘 (라우터는 +300초)
  그 밖(창 밖·0.7 미만·zone_scheduled·released) → 열림
현장 체크리스트(scripts/field_checklist.py)와 field 제보 비교(scripts/field_compare.py)가 쓴다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.closure_events import event_id, worst
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.repositories.report_repository import ReportRow
from naru_contracts import ClosureState, Status

Verdict = Literal["match", "over", "under"]  # 맞음 · 더 막음(나루 막힘, 실제 열림) · 덜 막음


def penalized(state: ClosureState, status: Status, at: datetime, settings: Settings) -> bool:
    """예정이고 확신도 ≥ 0.7 이고 at 이 공지 창 안 (ADR-011 A). 끝이 없으면 시작 뒤 전부."""
    if status is not Status.scheduled or state.confidence < settings.review_confidence:
        return False
    start, end = state.window.start, state.window.end
    return (start is None or at >= start) and (end is None or at <= end)


def blocked_at(
    state: ClosureState, at: datetime, engine: ClosureEngine, settings: Settings
) -> Status | None:
    """막힘으로 보면 그 상태(confirmed | scheduled), 아니면 None."""
    status = engine.status_of_state(state, at)
    if status is Status.confirmed or penalized(state, status, at, settings):
        return status
    return None


@dataclass(frozen=True)
class ChecklistRow:
    crosswalk_id: str
    name: str | None  # 교차로명 (색인에 없으면 None)
    district: str | None
    lng: float
    lat: float
    event_id: str
    reason: str
    status: Status  # 그 시간대에서 가장 센 판정
    confidence: float
    window_start: datetime | None
    window_end: datetime | None
    blocked_from: datetime  # 처음 막힌 분
    blocked_to: datetime  # 마지막으로 막힌 분


def checklist(
    states: Iterable[ClosureState],
    index: CrosswalkIndex,
    engine: ClosureEngine,
    settings: Settings,
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(minutes=1),
) -> list[ChecklistRow]:
    """[start, end] 에 한 번이라도 막히는 (횡단보도, 사건) — 현장에 들고 나갈 목록."""
    found: dict[tuple[str, str], ChecklistRow] = {}
    for st in states:
        hits: list[tuple[datetime, Status]] = []
        t = start
        while t <= end:
            status = blocked_at(st, t, engine, settings)
            if status is not None:
                hits.append((t, status))
            t += step
        if not hits:
            continue
        cw = index.find(st.crosswalk_id)
        row = ChecklistRow(
            crosswalk_id=st.crosswalk_id,
            name=cw.intersection_name if cw else None,
            district=cw.district if cw else None,
            lng=st.lng,
            lat=st.lat,
            event_id=event_id(st.reason, st.window.start, st.window.end),
            reason=st.reason,
            status=worst(s for _, s in hits),
            confidence=st.confidence,
            window_start=st.window.start,
            window_end=st.window.end,
            blocked_from=hits[0][0],
            blocked_to=hits[-1][0],
        )
        key = (row.crosswalk_id, row.event_id)
        prev = found.get(key)
        if prev is not None:  # 같은 사건의 후보 여럿이 같은 횡단보도를 골랐다
            row = replace(
                prev,
                status=worst((prev.status, row.status)),
                confidence=max(prev.confidence, row.confidence),
                blocked_from=min(prev.blocked_from, row.blocked_from),
                blocked_to=max(prev.blocked_to, row.blocked_to),
            )
        found[key] = row
    return sorted(found.values(), key=lambda r: (r.blocked_from, r.reason, r.crosswalk_id))


@dataclass(frozen=True)
class CompareRow:
    report: ReportRow
    predicted: Status | None  # 그 시각 나루 판정 — 막힘이면 confirmed | scheduled
    reason: str | None  # 막힘으로 본 사유 (여럿이면 가장 센 판정의 첫 사유)
    verdict: Verdict


@dataclass(frozen=True)
class CompareResult:
    rows: list[CompareRow]
    tp: int  # 나루 막힘 · 실제 막힘
    fp: int  # 더 막음
    fn: int  # 덜 막음
    tn: int  # 나루 열림 · 실제 열림

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None


def compare(
    reports: Sequence[ReportRow],
    states: Iterable[ClosureState],
    engine: ClosureEngine,
    settings: Settings,
) -> CompareResult:
    """제보마다 그 시각 나루 예측과 맞춰 본다 (양성 = 막힘)."""
    by_cw: dict[str, list[ClosureState]] = {}
    for st in states:
        by_cw.setdefault(st.crosswalk_id, []).append(st)
    rows: list[CompareRow] = []
    for r in reports:
        hits = [
            (status, st.reason)
            for st in by_cw.get(r.crosswalk_id, ())
            if (status := blocked_at(st, r.reported_at, engine, settings)) is not None
        ]
        predicted = worst(s for s, _ in hits) if hits else None
        reason = next((why for s, why in hits if s is predicted), None)
        actual = r.state == "blocked"
        verdict: Verdict = (
            "match" if (predicted is not None) == actual else "over" if not actual else "under"
        )
        rows.append(CompareRow(r, predicted, reason, verdict))
    tp = sum(1 for x in rows if x.predicted is not None and x.report.state == "blocked")
    fp = sum(1 for x in rows if x.verdict == "over")
    fn = sum(1 for x in rows if x.verdict == "under")
    return CompareResult(rows, tp, fp, fn, len(rows) - tp - fp - fn)
