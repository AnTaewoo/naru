"""T7.9 — 알림 매칭 순수 함수 (ADR-014 C). 입력은 사건 v2 기록(구역 있음)과 카카오 점의 관심 지역.

2026-11-10 shapely 로 확인한 값: 11/7 15:30 기록에서 광화문교보빌딩 500 m 원과 겹치는 사건 3 —
2e930ec6deeb(r04 행진, scheduled 0.75)·be5f89a4ebf3(r01 행진, scheduled 0.85)·3c408a6e5e4a
(TOPIS 6300, confirmed 0.8); 덕수궁 대한문 300 m 는 5(세종대로 집회 돌발 셋 더). 11/9 13:30 교보
500 m 는 국회대로 행진 ccaa9980c6ac(confirmed) 하나, 11/8 20:00 엔 같은 사건이 scheduled.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from naru_be.config import Settings
from naru_be.models.domain.push_dispatcher import (
    PlannedSend,
    WatchCircle,
    due_for,
    payload_of,
    plan_sends,
)
from naru_contracts import ClosureEvent, ClosureEventsResponse

KST = timezone(timedelta(hours=9))
KYOBO = WatchCircle(126.9779039768265, 37.5709686446227, 500)
DAEHANMUN = WatchCircle(126.976542945622, 37.5650416322942, 300)


def events_of(recorded_dir: Path, name: str) -> tuple[list[ClosureEvent], datetime]:
    doc = json.loads((recorded_dir / "naru_api" / f"{name}.json").read_text("utf-8"))
    body = ClosureEventsResponse.model_validate(doc["body"])
    return body.events, body.at


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()


def keys(sends: list[PlannedSend]) -> set[tuple[int, str, str]]:
    return {(s.subscription_id, s.event_id, s.kind) for s in sends}


def test_match_kyobo_1107(recorded_dir: Path, settings: Settings) -> None:
    events, at = events_of(recorded_dir, "closure_events_live_1107_1530")
    sends = plan_sends(events, [(1, [KYOBO])], set(), at, settings)
    assert keys(sends) == {
        (1, "2e930ec6deeb", "created"),
        (1, "be5f89a4ebf3", "created"),
        (1, "3c408a6e5e4a", "confirmed"),
    }
    assert all(s.due_at == at for s in sends)  # 15:30 — 바로
    # 대한문 300 m — 세종대로 집회 돌발 셋이 더 걸린다. 두 구독, 겹치는 사건은 구독마다 하나씩
    both = plan_sends(events, [(1, [KYOBO]), (2, [DAEHANMUN])], set(), at, settings)
    assert len([s for s in both if s.subscription_id == 2]) == 5
    assert {s.event_id for s in both if s.subscription_id == 2} >= {"905defcd0853", "2d3818b07bea"}
    # 이미 줄 선 것은 다시 안 만든다
    assert plan_sends(events, [(1, [KYOBO])], keys(sends), at, settings) == []
    # 확신도 0.7 미만은 뺀다 — r01 을 0.65 로 (기록 변형)
    low = [
        e.model_copy(update={"confidence": 0.65}) if e.id == "be5f89a4ebf3" else e for e in events
    ]
    got = {s.event_id for s in plan_sends(low, [(1, [KYOBO])], set(), at, settings)}
    assert "be5f89a4ebf3" not in got and "2e930ec6deeb" in got


def test_night_created_waits_for_morning(recorded_dir: Path, settings: Settings) -> None:
    events, _ = events_of(recorded_dir, "closure_events_live_1108_2000")  # 국회대로 행진 예정(11/9)
    night = datetime(2026, 11, 8, 23, 0, tzinfo=KST)
    sends = plan_sends(events, [(7, [KYOBO])], set(), night, settings)
    assert keys(sends) == {(7, "ccaa9980c6ac", "created")}
    assert sends[0].due_at == datetime(2026, 11, 9, 7, 0, tzinfo=KST)
    assert due_for("created", datetime(2026, 11, 9, 3, 0, tzinfo=KST), settings) == datetime(
        2026, 11, 9, 7, 0, tzinfo=KST
    )
    evening = datetime(2026, 11, 8, 20, 0, tzinfo=KST)
    assert due_for("created", evening, settings) == evening  # 22시 전은 바로
    assert due_for("confirmed", night, settings) == night  # 통제 시작은 밤에도 바로
    assert (settings.push_night_start_h, settings.push_night_end_h) == (22, 7)


def test_confirmed_march_and_payload(recorded_dir: Path, settings: Settings) -> None:
    events, at = events_of(recorded_dir, "closure_events_live_1109_1330")
    sends = plan_sends(events, [(3, [KYOBO, DAEHANMUN])], set(), at, settings)
    assert keys(sends) == {(3, "ccaa9980c6ac", "confirmed")}
    event = next(e for e in events if e.id == "ccaa9980c6ac")
    payload = payload_of(event, "confirmed")
    assert payload["kind"] == "confirmed" and payload["type"] == "march"
    assert payload["url"] == "/?event=ccaa9980c6ac&t=2026-11-09T11:00:00+09:00"
    assert payload["start"] == "2026-11-09T11:00:00+09:00"
    assert payload["end"] == "2026-11-09T15:30:00+09:00"
    name = payload["event"]
    assert isinstance(name, str) and "\n" not in name and len(name) <= 80
