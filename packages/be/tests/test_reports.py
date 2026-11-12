"""T7.15 — 통제 제보 ReportDesk·ReportRepository (INTERFACE §8): 최근접, 간격 429, 최근 집계.

실제 MySQL(naru_test) + OA-23081 횡단보도 색인(conftest course_world). 2026-11-10 색인을 열어 확인:
광화문교보빌딩 카카오 좌표(§7.1) → 06-0000051345 '교보생명' 종로구 71.07 m (xlsx 행 20198),
덕수궁 대한문 → 06-0000021877 '덕수궁앞' 중구 38.4 m. 06-0000000000 은 xlsx 3열에 없다(최소 …002).
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from conftest import CourseWorld
from naru_be.models.domain.reports import ReportDesk
from naru_be.models.repositories.report_repository import ReportRepository

from naru_be.errors import InvalidQueryError, TooManyReportsError
from naru_contracts import ReportRequest

KST = timezone(timedelta(hours=9))
KYOBO = (126.9779039768265, 37.5709686446227)  # 카카오 '광화문교보빌딩' 24020019
DAEHANMUN = (126.976542945622, 37.5650416322942)  # 카카오 '덕수궁 대한문' 17582477
SEONGNAM = (127.1112, 37.3947)  # 서울 밖 (test_routers out_of_coverage 와 같은 점)
KYOBO_CW, DAEHANMUN_CW = "06-0000051345", "06-0000021877"


@pytest.fixture()
def desk(course_world: CourseWorld, report_repo: ReportRepository) -> ReportDesk:
    report_repo.truncate()
    return ReportDesk(course_world.index, report_repo, course_world.settings)


def _ask(cw: str, state: str, device: str, source: str = "user") -> ReportRequest:
    return ReportRequest.model_validate(
        {"crosswalk_id": cw, "state": state, "accuracy_m": 12, "source": source, "device": device}
    )


def test_nearest_crosswalk(desk: ReportDesk) -> None:
    hit = desk.nearest(*KYOBO)
    assert hit is not None
    assert (hit.crosswalk.crosswalk_id, hit.crosswalk.intersection_name) == (KYOBO_CW, "교보생명")
    assert hit.crosswalk.district == "종로구" and round(hit.distance_m, 1) == 71.1
    near = desk.nearest(*DAEHANMUN)
    assert near is not None and near.crosswalk.crosswalk_id == DAEHANMUN_CW
    assert near.crosswalk.intersection_name == "덕수궁앞" and round(near.distance_m, 1) == 38.4
    assert desk.nearest(*SEONGNAM) is None  # 100 m(report_snap_m) 안에 없다
    assert desk.settings.report_snap_m == 100


def test_submit_interval_and_recent(desk: ReportDesk) -> None:
    repo = desk.repo
    device, other = str(uuid.uuid4()), str(uuid.uuid4())  # FE 와 같은 방식의 기기 토큰
    t0 = datetime(2026, 11, 10, 15, 0, tzinfo=KST)
    saved = desk.submit(_ask(KYOBO_CW, "blocked", device), now=t0)
    assert (saved.crosswalk_id, saved.state, saved.reported_at) == (KYOBO_CW, "blocked", t0)
    (row,) = repo.between(t0, t0, source="user")
    assert row.device_hash == hashlib.sha256(device.encode()).hexdigest() and row.accuracy_m == 12
    with pytest.raises(TooManyReportsError) as e:  # 같은 기기·같은 횡단보도 600초 안
        desk.submit(_ask(KYOBO_CW, "open", device), now=t0 + timedelta(seconds=599))
    assert (e.value.code, e.value.http_status, e.value.field) == (
        "too_many_reports",
        429,
        "crosswalk_id",
    )
    desk.submit(_ask(DAEHANMUN_CW, "open", device), now=t0 + timedelta(minutes=1))  # 다른 횡단보도
    desk.submit(_ask(KYOBO_CW, "open", other), now=t0 + timedelta(minutes=2))  # 다른 기기
    desk.submit(_ask(KYOBO_CW, "blocked", device), now=t0 + timedelta(seconds=600))  # 간격 지남
    with pytest.raises(InvalidQueryError) as bad:
        desk.submit(_ask("06-0000000000", "blocked", device), now=t0)
    assert bad.value.field == "crosswalk_id"
    at = t0 + timedelta(minutes=30)
    assert desk.recent((KYOBO_CW, DAEHANMUN_CW, "06-0000030621"), 60, now=at) == {
        KYOBO_CW: (2, 1),
        DAEHANMUN_CW: (0, 1),
    }
    # 28분 창 = 15:02 부터(경계 포함) — 교보 15:02 open·15:10 blocked, 대한문 15:01 은 밖
    assert desk.recent((KYOBO_CW, DAEHANMUN_CW), 28, now=at) == {KYOBO_CW: (1, 1)}
    assert [r.source for r in repo.between(t0, at, source="field")] == []
    assert len(repo.between(t0, at)) == 4
