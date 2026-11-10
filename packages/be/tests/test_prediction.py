"""T7.15 — 막힘 예측 blocked_at(라우터 §5 규칙)·현장 체크리스트·field 제보 비교.

코스 기록(conftest course_world: 2026 서울마라톤 후보 16 → 상태 470). 2026-11-10 에 열어 확인:
06-0000023206 '세종대로사거리' 종로구 — 'marathon 1구간 세종대로 사거리~숭례문 오거리'
07:20~08:08, 0.9 (07:00 scheduled · 07:45 confirmed · 13:30 released).
06-0000036391 '세종대로사거리' — 출발지 05:00~08:30. 사건 id 는 기록
naru_api/closure_events_live_0315_0745.json 의 1구간 adaea2f4cc02 · 출발지 3d608690c438.
비교 테스트의 제보는 ReportDesk 로 낸 입력(횡단보도·상태·시각) — 실제 정답은 11/14 field 제보.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from conftest import CourseWorld

from naru_be.models.domain.prediction import blocked_at, checklist, compare
from naru_be.models.domain.reports import ReportDesk
from naru_be.models.repositories.report_repository import ReportRepository
from naru_contracts import ClosureState, ReportRequest, Status

KST = timezone(timedelta(hours=9))
SEJONG, START_CW = "06-0000023206", "06-0000036391"
LEG1 = "marathon 1구간 세종대로 사거리~숭례문 오거리"


def at(h: int, m: int) -> datetime:
    return datetime(2026, 3, 15, h, m, tzinfo=KST)


@pytest.fixture(scope="module")
def leg1(course_world: CourseWorld) -> ClosureState:
    (st,) = [s for s in course_world.states if s.crosswalk_id == SEJONG]
    assert st.reason == LEG1 and st.confidence == 0.9
    return st


def test_blocked_at_same_rule_as_router(course_world: CourseWorld, leg1: ClosureState) -> None:
    w = course_world

    def judge(st: ClosureState, t: datetime) -> Status | None:
        return blocked_at(st, t, w.engine, w.settings)

    assert judge(leg1, at(7, 0)) is None  # 창 시작 전 예정 — 라우터도 보통 간선
    assert judge(leg1, at(7, 45)) is Status.confirmed
    assert judge(leg1, at(8, 37)) is Status.confirmed  # 끝 08:08 + 정리 30분 안
    assert judge(leg1, at(8, 38)) is None  # released
    soft = leg1.model_copy(update={"confidence": 0.75})  # 0.7 이상 0.8 미만 — 창 안 예정
    assert judge(soft, at(7, 45)) is Status.scheduled and judge(soft, at(8, 8)) is Status.scheduled
    assert judge(soft, at(8, 9)) is None  # 창 끝 뒤 예정은 보통
    assert judge(leg1.model_copy(update={"confidence": 0.5}), at(7, 45)) is None


def test_checklist_marathon_morning(course_world: CourseWorld) -> None:
    w = course_world
    rows = checklist(w.states, w.index, w.engine, w.settings, at(7, 0), at(9, 0))
    by = {(r.crosswalk_id, r.reason): r for r in rows}
    r = by[(SEJONG, LEG1)]
    assert (r.blocked_from, r.blocked_to, r.status) == (at(7, 20), at(8, 37), Status.confirmed)
    assert (r.event_id, r.name, r.district, r.confidence) == (
        "adaea2f4cc02",
        "세종대로사거리",
        "종로구",
        0.9,
    )
    assert (r.window_start, r.window_end) == (at(7, 20), at(8, 8))
    start = by[(START_CW, "marathon 출발지 광화문 광장 (미국대사관 앞 세종대로)")]
    # 끝 08:30 + 정리 30분 = 09:00 에 released → 마지막으로 막힌 분은 08:59
    assert (start.blocked_from, start.blocked_to, start.event_id) == (
        at(7, 0),
        at(8, 59),
        "3d608690c438",
    )
    # 07:00~09:00 에 한 번이라도 막히는 (횡단보도, 사유)
    # — 5분 간격 probe(2026-11-10)와 같은 462쌍·401곳
    assert len(rows) == 462 and len({x.crosswalk_id for x in rows}) == 401
    assert rows == sorted(rows, key=lambda x: (x.blocked_from, x.reason, x.crosswalk_id))
    # 13:30~14:00 엔 결승 15구간(종합운동장 동문 앞~사거리 05:00~14:30)의 '삼성교동측' 한 곳만,
    # 가장 늦은 끝 14:30 + 정리 30분 = 15:00 부터는 없다 (2026-11-10 상태를 열어 확인)
    late = checklist(w.states, w.index, w.engine, w.settings, at(13, 30), at(14, 0))
    assert [(x.crosswalk_id, x.name, x.district) for x in late] == [
        ("06-0000033662", "삼성교동측", "송파구")
    ]
    assert checklist(w.states, w.index, w.engine, w.settings, at(15, 0), at(15, 30)) == []


@pytest.fixture()
def field_desk(course_world: CourseWorld, report_repo: ReportRepository) -> Iterator[ReportDesk]:
    report_repo.truncate()
    yield ReportDesk(course_world.index, report_repo, course_world.settings)
    report_repo.truncate()


def test_compare_field_reports(course_world: CourseWorld, field_desk: ReportDesk) -> None:
    w = course_world
    device = str(uuid.uuid4())

    def send(cw: str, state: str, minute: int, source: str = "field") -> None:
        body = {"crosswalk_id": cw, "state": state, "accuracy_m": 9, "source": source}
        field_desk.submit(
            ReportRequest.model_validate({**body, "device": device}), now=at(7, minute)
        )

    send(SEJONG, "blocked", 45)  # 나루 막힘(1구간 confirmed) · 실제 막힘 → 맞음
    send(START_CW, "open", 46)  # 나루 막힘(출발지) · 실제 열림 → 더 막음
    send("06-0000051345", "blocked", 47)  # 교보생명 — 코스 밖, 나루 열림 · 실제 막힘 → 덜 막음
    send("06-0000021877", "open", 48)  # 덕수궁앞 — 나루 열림 · 실제 열림 → 맞음
    send("06-0000030621", "blocked", 49, source="user")  # user 제보는 비교에 안 들어간다
    reports = field_desk.repo.between(at(0, 0), at(23, 59), source="field")
    result = compare(reports, w.states, w.engine, w.settings)
    assert [(r.report.crosswalk_id, r.predicted, r.verdict) for r in result.rows] == [
        (SEJONG, Status.confirmed, "match"),
        (START_CW, Status.confirmed, "over"),
        ("06-0000051345", None, "under"),
        ("06-0000021877", None, "match"),
    ]
    assert result.rows[0].reason == LEG1 and result.rows[2].reason is None
    assert (result.tp, result.fp, result.fn, result.tn) == (1, 1, 1, 1)
    assert result.recall == 0.5 and result.precision == 0.5
