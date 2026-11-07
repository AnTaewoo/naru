"""T4.3 — eval: 정답을 예측으로 넣으면 1.0, 규칙 기준선이 34건 전부에서 돌아간다, 합성 163건 적재.

라벨 파일은 data/raw/notices/cases_v1.jsonl (태우, 2026-11-07). 없으면 실패한다.
"""

from pathlib import Path

import pytest

from naru_ai.llm.notice_schema import Lanes, NoticeItem, NoticeOutput, Segment, Window
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.notice.eval import compare_case, evaluate, robustness
from naru_ai.notice.eval_cases import Case, load_cases, load_synthetic
from naru_ai.notice.eval_report import bootstrap_ci, markdown_report, summarize
from naru_ai.notice.rule_baseline import RuleBaseline


@pytest.fixture(scope="module")
def cases(notices_dir: Path) -> list[Case]:
    path = notices_dir / "cases_v1.jsonl"
    assert path.exists(), "라벨 없음: data/raw/notices/cases_v1.jsonl (T0.6)"
    out = load_cases(path)
    assert len(out) == 34
    return out


def as_prediction(case: Case) -> NoticeOutput:
    """라벨 item 을 그대로 NoticeItem 으로 (spans 등 라벨에 없는 칸은 비움)."""
    items = []
    for e in case.expected:
        items.append(
            NoticeItem(
                window=Window(start=e.window.get("start"), end=e.window.get("end")),
                approx=e.approx,
                kind=e.kind,  # type: ignore[arg-type]  # 라벨의 kind 는 스키마 enum 값이다
                impact=e.impact,  # type: ignore[arg-type]  # 라벨의 impact 도 enum 값
                impact_reason=None,
                segments=[
                    Segment(
                        order=None,
                        **{"from": s.from_},
                        to=s.to,
                        via=list(s.via),
                        road=s.road,
                        direction=s.direction,  # type: ignore[arg-type]  # one_way|both
                        lanes=Lanes(count=None, scope=None),
                        length_km=None,
                    )
                    for s in e.segments
                ],
                points=[{"name": p.name, "road_hint": None} for p in e.points],  # type: ignore[list-item]  # pydantic 이 변환
                toward=e.toward,
                road_hints=[],
                reported_people=None,
                police_stations=[],
                spans=[],
                confidence=0.5,
                notes=None,
            )
        )
    return NoticeOutput(items=items)


def test_expected_as_prediction_scores_one(cases: list[Case]) -> None:
    by_id = {c.case_id: c for c in cases}
    results = evaluate(cases, lambda env: as_prediction(by_id[env.sentence_id]))
    assert all(r.passed for r in results), [r.case_id for r in results if not r.passed]
    s = summarize(results)
    assert s.pass_rate == 1.0 and s.ci95 == (1.0, 1.0) and s.errors == 0
    assert all(v == 1.0 for v in s.rates.values()) and s.road_rate == 1.0
    assert sum(n for _, n in s.by_type.values()) == 34
    assert set(s.by_type) == {"정상", "놓치기쉬움", "none", "unknown", "거절"}  # 2026-11-08 라벨
    # 거절(K-034, items 0): blocks item 을 내면 실패, none 만 내면 통과
    k034 = by_id["K-034"]
    none_item = as_prediction(by_id["K-029"]).items[0].model_copy(update={"impact": "none"})
    blocks_item = none_item.model_copy(update={"impact": "blocks"})
    assert compare_case(k034, [none_item]).passed and not compare_case(k034, [blocks_item]).passed
    # 원문 이름도 인정 (§7-3): K-001 의 via '종로1R' 은 원문이라 통과, 엉뚱한 이름은 실패
    k001 = by_id["K-001"]
    raw = as_prediction(k001)
    raw_seg = raw.items[0].segments[0].model_copy(update={"via": ["종로1R"]})
    assert compare_case(k001, [raw.items[0].model_copy(update={"segments": [raw_seg]})]).passed
    bad_seg = raw.items[0].segments[0].model_copy(update={"via": ["광화문"]})
    assert not compare_case(k001, [raw.items[0].model_copy(update={"segments": [bad_seg]})]).passed


def test_rule_baseline_runs_on_every_case(cases: list[Case]) -> None:
    results = evaluate(cases, RuleBaseline().parse)
    assert len(results) == 34 and all(r.error is None for r in results)
    s = summarize(results)
    assert 0.0 < s.pass_rate < 1.0  # 기준선은 일부만 맞는다 — 숫자는 docs/eval 표
    # K-001 (순환 행진): 시간·kind·from/to/via 를 규칙으로 맞춘다
    r = next(r for r in results if r.case_id == "K-001")
    assert r.field_ok("window") and r.field_ok("kind") and r.field_ok("segments")
    report = markdown_report("t", {"규칙": (s, results)}, {})
    assert "| 규칙 |" in report and "K-034" in report


def test_bootstrap_and_synthetic(recorded_dir: Path) -> None:
    assert bootstrap_ci([True] * 10) == (1.0, 1.0) and bootstrap_ci([]) == (0.0, 0.0)
    lo, hi = bootstrap_ci([True, False] * 17)
    assert 0.3 < lo < 0.5 < hi < 0.7
    path = recorded_dir / "syntitan" / "agent_questions.csv"
    assert path.exists(), "합성 입력 없음: data/recorded/syntitan/agent_questions.csv"
    envs = load_synthetic(path, "2026-11-07T00:00:00+09:00")
    assert len(envs) == 163 and envs[0].sentence_id == "C-001" and envs[0].source == "news"
    assert all("\n" in e.text for e in envs)
    rob = robustness(envs[:5], RuleBaseline().parse)
    assert rob.n == 5 and rob.schema_ok == 5 and sum(rob.impact.values()) == 5
    env = NoticeEnvelope(
        sentence_id="x",
        source="smpa",
        text="12:00~13:00 | 광화문 앞 <세종대로>",
        event_date="2026-11-07",
        published_at="2026-11-06T18:00:00+09:00",
        fetched_at="2026-11-07T09:00:00+09:00",
    )
    item = RuleBaseline().parse(env).items[0]
    assert (
        item.kind == "rally_point"
        and item.impact == "unknown"
        and item.points[0].name == "광화문 앞"
    )
    assert item.window.start == "2026-11-07T12:00:00+09:00" and item.road_hints == ["세종대로"]
