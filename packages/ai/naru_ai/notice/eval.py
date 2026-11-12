"""평가 — 라벨 대비 케이스 비교와 합성 입력 견고성 (T4.3). 입력 eval_cases.py, 집계 eval_report.py.

정확도(34건, 태우 라벨): item 짝은 window 시작 시각 순으로(규칙서 §9.3). 케이스가 통과하려면
items 수가 같고 짝마다 impact·kind·segments(from/to/via 순서, 정규형 또는 원문)·window(분 단위,
approx 면 ±10분)·toward·points 가 맞아야 한다. road·impact_reason 은 참고 열.
거절(expected items 0)은 예측에 blocks/unknown item 이 없으면 통과. 케이스 단위 부트스트랩 95% CI.
견고성(163건, 합성·정답 없음): 스키마 통과율 + impact·kind 분포만. 정확도 계산에 안 쓴다.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from naru_ai.llm.notice_schema import NoticeItem, NoticeOutput
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import RecordingMismatchError
from naru_ai.notice.eval_cases import Case, ExpectedItem
from naru_ai.notice.parser import RecordingMissingError

HEADLINE = ("impact", "kind", "segments", "window", "toward", "points")
APPROX_TOLERANCE = timedelta(minutes=10)
# 평가는 한 케이스의 실패로 멈추지 않고 실패를 센다 — 파서·기록·스키마·규칙 기준선이 내는 예외만
PREDICT_ERRORS = (RecordingMissingError, RecordingMismatchError, OSError, ValueError, IndexError)


# --- 비교 -------------------------------------------------------------------------
@dataclass(frozen=True)
class PairResult:
    impact: bool
    kind: bool
    segments: bool
    window: bool
    toward: bool
    points: bool
    road: bool | None  # segment 가 없으면 None
    impact_reason: bool | None  # expected impact 가 none 일 때만


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    type: str
    n_expected: int
    n_predicted: int
    count_ok: bool
    pairs: tuple[PairResult, ...]
    error: str | None = None

    def field_ok(self, name: str) -> bool:
        if self.error or not self.count_ok:
            return False
        return all(getattr(p, name) is not False for p in self.pairs)

    @property
    def passed(self) -> bool:
        return all(self.field_ok(f) for f in HEADLINE)


def _minute(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).replace(second=0, microsecond=0)


def _window_ok(exp: ExpectedItem, pred: NoticeItem) -> bool:
    tol = APPROX_TOLERANCE if exp.approx else timedelta(0)
    for key in ("start", "end"):
        e, p = _minute(exp.window.get(key)), _minute(getattr(pred.window, key))
        if (e is None) != (p is None):
            return False
        if e is not None and p is not None and abs(e - p) > tol:
            return False
    return True


def _name_ok(expected: str, predicted: str, text: str) -> bool:
    """정규형 또는 원문 — 둘 중 하나면 인정 (규칙서 §7-3)."""
    if predicted == expected:
        return True
    return bool(predicted) and predicted in text and expected not in text


def _segments_ok(exp: ExpectedItem, pred: NoticeItem, text: str) -> bool:
    if len(exp.segments) != len(pred.segments):
        return False
    for e, p in zip(exp.segments, pred.segments, strict=True):
        if not (_name_ok(e.from_, p.from_, text) and _name_ok(e.to, p.to, text)):
            return False
        if len(e.via) != len(p.via) or not all(
            _name_ok(a, b, text) for a, b in zip(e.via, p.via, strict=True)
        ):
            return False
        if e.direction != p.direction:
            return False
    return True


def _road_ok(exp: ExpectedItem, pred: NoticeItem) -> bool | None:
    if not exp.segments or len(exp.segments) != len(pred.segments):
        return None
    return all(e.road == p.road for e, p in zip(exp.segments, pred.segments, strict=True))


def compare_item(exp: ExpectedItem, pred: NoticeItem, text: str) -> PairResult:
    exp_points = {p.name for p in exp.points}
    pred_points = [p.name for p in pred.points]
    points_ok = len(exp_points) == len(pred_points) and all(
        any(_name_ok(e, p, text) for e in exp_points) for p in pred_points
    )
    if exp.toward is None:
        toward_ok = pred.toward is None
    else:
        toward_ok = pred.toward is not None and _name_ok(exp.toward, pred.toward, text)
    reason_ok = (exp.impact_reason == pred.impact_reason) if exp.impact == "none" else None
    return PairResult(
        impact=exp.impact == pred.impact,
        kind=exp.kind == pred.kind,
        segments=_segments_ok(exp, pred, text),
        window=_window_ok(exp, pred),
        toward=toward_ok,
        points=points_ok,
        road=_road_ok(exp, pred),
        impact_reason=reason_ok,
    )


def _start_key(value: str | None) -> str:
    return value or "9999"


def compare_case(case: Case, predicted: Sequence[NoticeItem]) -> CaseResult:
    exp = sorted(case.expected, key=lambda i: _start_key(i.window.get("start")))
    pred = sorted(predicted, key=lambda i: _start_key(i.window.start))
    if not exp:  # 거절: blocks/unknown item 이 없어야 한다
        blocking = [p for p in pred if p.impact != "none"]
        return CaseResult(case.case_id, case.type, 0, len(pred), not blocking, ())
    pairs = tuple(compare_item(e, p, case.text) for e, p in zip(exp, pred, strict=False))
    return CaseResult(case.case_id, case.type, len(exp), len(pred), len(exp) == len(pred), pairs)


def evaluate(
    cases: Iterable[Case], predict: Callable[[NoticeEnvelope], NoticeOutput]
) -> list[CaseResult]:
    out: list[CaseResult] = []
    for case in cases:
        try:
            output = predict(case.envelope())
        except PREDICT_ERRORS as exc:
            n_exp = len(case.expected)
            out.append(CaseResult(case.case_id, case.type, n_exp, 0, False, (), repr(exc)))
            continue
        out.append(compare_case(case, output.items))
    return out


# --- 견고성 (합성 입력, 정답 없음) --------------------------------------------------
@dataclass
class Robustness:
    n: int = 0
    schema_ok: int = 0
    items: Counter[int] = field(default_factory=Counter)
    impact: Counter[str] = field(default_factory=Counter)
    kind: Counter[str] = field(default_factory=Counter)
    errors: list[tuple[str, str]] = field(default_factory=list)


def robustness(
    envelopes: Iterable[NoticeEnvelope], predict: Callable[[NoticeEnvelope], NoticeOutput]
) -> Robustness:
    rob = Robustness()
    for env in envelopes:
        rob.n += 1
        try:
            output = predict(env)
        except PREDICT_ERRORS as exc:
            rob.errors.append((env.sentence_id, repr(exc)))
            continue
        rob.schema_ok += 1
        rob.items[len(output.items)] += 1
        for item in output.items:
            rob.impact[item.impact] += 1
            rob.kind[item.kind] += 1
    return rob
