"""평가 집계·보고 — 케이스 결과 → 일치율·부트스트랩 CI·type 별 표·markdown (T4.3). 비교는 eval.py"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from naru_ai.notice.eval import HEADLINE, CaseResult, Robustness


@dataclass(frozen=True)
class Summary:
    n: int
    passed: int
    rates: dict[str, float]  # 필드별 일치율 (케이스 단위)
    road_rate: float | None
    reason_rate: float | None
    by_type: dict[str, tuple[int, int]]  # type → (passed, n)
    ci95: tuple[float, float]
    errors: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.n if self.n else 0.0


def _rate(values: Iterable[bool | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def bootstrap_ci(
    flags: Sequence[bool], n_resamples: int = 1000, seed: int = 0
) -> tuple[float, float]:
    if not flags:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(flags) for _ in flags) / len(flags) for _ in range(n_resamples))
    return (means[int(0.025 * n_resamples)], means[int(0.975 * n_resamples) - 1])


def summarize(results: Sequence[CaseResult]) -> Summary:
    flags = [r.passed for r in results]
    by_type: dict[str, tuple[int, int]] = {}
    for r in results:
        p, n = by_type.get(r.type, (0, 0))
        by_type[r.type] = (p + int(r.passed), n + 1)
    pairs = [p for r in results for p in r.pairs]
    rates = {f: sum(r.field_ok(f) for r in results) / len(results) for f in HEADLINE}
    rates["items_count"] = sum(r.count_ok for r in results) / len(results)
    return Summary(
        n=len(results),
        passed=sum(flags),
        rates=rates,
        road_rate=_rate(p.road for p in pairs),
        reason_rate=_rate(p.impact_reason for p in pairs),
        by_type=by_type,
        ci95=bootstrap_ci(flags),
        errors=sum(1 for r in results if r.error),
    )


# --- 보고 -------------------------------------------------------------------------
def _counter_text(c: Counter[int] | Counter[str]) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1]))


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{100 * v:.0f}%"


def _case_cell(r: CaseResult | None) -> str:
    if r is None:
        return "—"
    if r.error:
        return "오류"
    if r.passed:
        return "✓"
    bad = [f for f in HEADLINE if not r.field_ok(f)]
    if not r.count_ok:
        bad.insert(0, f"items {r.n_predicted}≠{r.n_expected}")
    return ", ".join(bad)


def markdown_report(
    title: str,
    accuracy: dict[str, tuple[Summary, Sequence[CaseResult]]],
    robust: dict[str, Robustness],
    notes: Sequence[str] = (),
) -> str:
    lines = [f"# {title}", ""]
    lines.append("## 정확도 — `data/raw/notices/cases_v1.jsonl` (실제 공지, 태우 라벨)")
    lines.append("")
    cols = ["시스템", "케이스", "전부 일치", "95% CI", *HEADLINE]
    cols += ["items 수", "road", "impact_reason", "오류"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * len(cols))
    for name, (s, _) in accuracy.items():
        cells = [name, str(s.n), _pct(s.pass_rate), f"{_pct(s.ci95[0])}~{_pct(s.ci95[1])}"]
        cells += [_pct(s.rates[f]) for f in HEADLINE]
        cells += [_pct(s.rates["items_count"]), _pct(s.road_rate), _pct(s.reason_rate)]
        cells.append(str(s.errors))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### type 별 전부 일치")
    lines.append("")
    types = sorted({t for s, _ in accuracy.values() for t in s.by_type})
    lines.append("| 시스템 | " + " | ".join(types) + " |")
    lines.append("|" + "---|" * (len(types) + 1))
    for name, (s, _) in accuracy.items():
        cells = [f"{p}/{n}" for t in types for p, n in [s.by_type.get(t, (0, 0))]]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("### 케이스별 (전부 일치 ✓ / 틀린 필드)")
    lines.append("")
    names = list(accuracy)
    lines.append("| case | type | " + " | ".join(names) + " |")
    lines.append("|" + "---|" * (len(names) + 2))
    by_id: dict[str, dict[str, CaseResult]] = {}
    for name, (_, results) in accuracy.items():
        for r in results:
            by_id.setdefault(r.case_id, {})[name] = r
    for cid, per in by_id.items():
        cells = [_case_cell(per.get(name)) for name in names]
        t = next(iter(per.values())).type
        lines.append(f"| {cid} | {t} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## 견고성 — `data/recorded/syntitan/agent_questions.csv` (합성 163건, 정답 없음)")
    lines.append("")
    lines.append("스키마 통과율과 분포만. 정확도 계산에 쓰지 않는다.")
    lines.append("")
    lines.append("| 시스템 | 입력 | 스키마 통과 | items 수 분포 | impact 분포 | kind 분포 |")
    lines.append("|---|---|---|---|---|---|")
    for name, rob in robust.items():
        ok = _pct(rob.schema_ok / rob.n if rob.n else None)
        lines.append(
            f"| {name} | {rob.n} | {rob.schema_ok}/{rob.n} ({ok}) | {_counter_text(rob.items)} "
            f"| {_counter_text(rob.impact)} | {_counter_text(rob.kind)} |"
        )
    if notes:
        lines += ["", "## 메모", ""] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"
