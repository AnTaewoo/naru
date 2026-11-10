"""T7.16 — 행진 확률 모델 (ADR-015): 프로필(경로·행렬·s)·P(t, s)·키프레임·라우터 비용.

입력은 기록된 공지 후보(conftest notice_batch)와 표준노드링크 도로 그래프. 2026-11-10 에 도로
최단경로를 돌려 확인한 값($CLAUDE_JOB_DIR/tmp/scripts/march_probe.py):
- 11/7 r01 동화면세점 앞 → 종로1가사거리 → 동화면세점 앞 (12:00~16:00, 50,000명): L 1,453.4 m,
  횡단보도 13 — 세종대로사거리 06-0000036391 s 185.5 · 06-0000023206 s 205.2 · 06-0000029520
  s 225.0, 종로구청입구 06-0000002104 s 1,036.0. 지난 도로 세종대로21길·새문안로·종로·새문안로·
  세종대로21길 → 폭 '로' 10 m → 행렬 2,500 m 는 L 로 자른다
- 11/9 r01 하나증권 앞 → 금감원 → 여의도역 (10:30~13:00, 200명): L 577.8 m, 여의도공원앞
  06-0000004701 s 238.5 · 여의도역 06-0000023703 s 554.5. 도로 여의대로2길·여의대로·의사당대로·
  여의나루로 → '대로' 16 m → 200/(16x2) = 6.25 m → 하한 100 m
- 11/7 r04 는 seg1 이 지점(seg1-to)으로만 풀리고 seg2·seg3 이 숭례문오거리에서 갈라진다 → 대상 아님
P 는 손으로 푼 값(테스트 안 주석) — 표본 u = -1, -0.9 ... 1 (21개), v_i = v(1 + 0.5u).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from naru_be.config import Settings
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.march import MarchProfile, keyframes, march_part, march_profile, p_at
from naru_contracts import CandidateBatch, ClosureCandidate

KST = timezone(timedelta(hours=9))
R01 = "smpa-20261107-r01-i1-seg1"
HANA = "smpa-20261109-r01-i1-seg1"
YEOUIDO_PARK, YEOUIDO_STN = "06-0000004701", "06-0000023703"
SEJONG_A, SEJONG_B, SEJONG_C = "06-0000036391", "06-0000023206", "06-0000029520"
JONGNO_GU = "06-0000002104"


def by_prefix(batch: CandidateBatch, prefix: str) -> list[ClosureCandidate]:
    return [c for c in batch.candidates if c.candidate_id.startswith(prefix)]


def profile_of(
    index: CrosswalkIndex, cands: list[ClosureCandidate], settings: Settings
) -> MarchProfile | None:
    parts = {c.candidate_id: p for c in cands if (p := march_part(index, c)) is not None}
    return march_profile(cands, parts, index, settings)


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="module")
def r01(
    road_index: CrosswalkIndex, notice_batch: CandidateBatch, settings: Settings
) -> MarchProfile:
    found = profile_of(road_index, by_prefix(notice_batch, "smpa-20261107-r01-"), settings)
    assert found is not None
    return found


@pytest.fixture(scope="module")
def hana(
    road_index: CrosswalkIndex, notice_batch: CandidateBatch, settings: Settings
) -> MarchProfile:
    found = profile_of(road_index, by_prefix(notice_batch, "smpa-20261109-r01-"), settings)
    assert found is not None
    return found


def test_profile_r01_loop(r01: MarchProfile) -> None:
    assert r01.length_m == pytest.approx(1453.4, abs=1)
    assert r01.width_m == 10.0 and r01.queue_m == r01.length_m  # 50,000/(10x2) = 2,500 > L
    assert len(r01.s) == 13 and r01.path[0] == r01.path[-1]  # 고리 — 끝이 시작
    assert r01.s[SEJONG_A] == pytest.approx(185.5, abs=1)
    assert r01.s[SEJONG_B] == pytest.approx(205.2, abs=1)
    assert r01.s[JONGNO_GU] == pytest.approx(1036.0, abs=1)
    assert all(-180 < lng < 180 and 37 < lat < 38 for lng, lat in r01.path)
    assert MarchProfile.from_json(r01.to_json()) == r01


def test_profile_hana_small_queue(hana: MarchProfile) -> None:
    assert hana.length_m == pytest.approx(577.8, abs=1)
    assert hana.width_m == 16.0 and hana.queue_m == 100.0  # 200명 → 6.25 m → 하한
    assert set(hana.s) == {YEOUIDO_PARK, YEOUIDO_STN}
    assert hana.s[YEOUIDO_PARK] == pytest.approx(238.5, abs=1)
    assert hana.s[YEOUIDO_STN] == pytest.approx(554.5, abs=1)


def test_branching_and_broken_segments_are_not_modeled(
    road_index: CrosswalkIndex, notice_batch: CandidateBatch, settings: Settings
) -> None:
    r04 = by_prefix(notice_batch, "smpa-20261107-r04-")
    assert {c.candidate_id for c in r04} == {
        "smpa-20261107-r04-i1-seg1-to",
        "smpa-20261107-r04-i1-seg2",
        "smpa-20261107-r04-i1-seg3",
    }
    assert profile_of(road_index, r04, settings) is None
    # seg2·seg3 만 — 둘 다 숭례문오거리에서 시작(갈라짐)
    assert profile_of(road_index, [c for c in r04 if c.candidate_id.endswith("seg3")], settings)
    assert (
        profile_of(road_index, [c for c in r04 if "seg1" not in c.candidate_id], settings) is None
    )
    # 끝이 없는 창은 대상이 아니다
    r01 = by_prefix(notice_batch, "smpa-20261107-r01-")
    open_end = [
        c.model_copy(update={"window": c.window.model_copy(update={"end": None})}) for c in r01
    ]
    assert profile_of(road_index, open_end, settings) is None
    # 행진이 아니면(집회) 대상이 아니다
    rally = [c.model_copy(update={"type": "rally"}) for c in r01]
    assert profile_of(road_index, rally, settings) is None


def test_p_at_hana(hana: MarchProfile, settings: Settings) -> None:
    start, end = datetime(2026, 11, 9, 10, 30, tzinfo=KST), datetime(2026, 11, 9, 13, 0, tzinfo=KST)

    def p(cid: str, t: datetime) -> float | None:
        return p_at(hana, start, end, cid, t, settings)

    # 시작: 머리 0. 여의도공원앞 s 238.5 - 선행 300 < 0 → 21/21,
    # 여의도역 554.5 - 300 > 0 → 0 → 하한 0.2
    assert p(YEOUIDO_PARK, start) == 1.0 and p(YEOUIDO_STN, start) == 0.2
    # 끝: 머리 x_i = 577.8(1 + 0.5u). 여의도역: 254.5 ≤ x < 654.5 ↔ u ∈ [-1.12, 0.265)
    # → u = -1 ... 0.2 → 13/21
    assert p(YEOUIDO_STN, end) == pytest.approx(13 / 21)
    # 여의도공원앞: x < 338.5 ↔ 1 + 0.5u < 0.586 ↔ u < -0.828 → u = -1, -0.9 → 2/21 < 하한 0.2 → 0.2
    assert p(YEOUIDO_PARK, end) == 0.2
    # 창 밖은 0, 경로 밖 횡단보도는 None
    assert p(YEOUIDO_STN, start - timedelta(seconds=1)) == 0.0
    assert p(YEOUIDO_STN, end + timedelta(seconds=1)) == 0.0
    assert p_at(hana, start, end, SEJONG_A, start, settings) is None
    assert (settings.march_samples, settings.march_speed_spread) == (21, 0.5)
    assert (settings.march_lead_m, settings.march_p_floor, settings.march_p_block) == (
        300,
        0.2,
        0.8,
    )


def test_keyframes_hana(hana: MarchProfile, settings: Settings) -> None:
    start, end = datetime(2026, 11, 9, 10, 30, tzinfo=KST), datetime(2026, 11, 9, 13, 0, tzinfo=KST)
    frames = keyframes(hana, start, end, start, start + timedelta(minutes=2), settings)
    assert [f.t for f in frames] == [start + timedelta(seconds=60 * k) for k in range(3)]
    first = frames[0]
    assert len(first.samples) == 21 and all(
        len(pts) == 1 for pts in first.samples
    )  # 머리 0, 꼬리 < 0
    assert first.radius_m == 0.0 and first.crosswalks == {YEOUIDO_PARK: 1.0, YEOUIDO_STN: 0.2}
    assert first.center == pytest.approx(hana.path[0], abs=1e-6)
    # 2분 뒤: 가장 빠른 표본 머리 = 1.5 x 0.0642 x 120 = 11.6 m → 25 m 간격이라 꼬리(0)와 머리 둘
    last = frames[-1]
    assert all(len(pts) == 2 for pts in last.samples) and 0 < last.radius_m < 12
    # 통제 시간 전체 — 1분 간격 151 키프레임, 점은 키프레임당 600 상한
    whole = keyframes(hana, start, end, None, None, settings)
    assert len(whole) == 151 and all(sum(len(s) for s in f.samples) <= 600 for f in whole)
    # 끝: 가장 느린 표본 머리 288.9 m·꼬리 188.9 → 25 m 간격 5점,
    # 가장 빠른 머리 866.7(경로 밖)·꼬리 766.7 → 0점
    assert len(whole[-1].samples[0]) == 5 and whole[-1].samples[-1] == ()
    assert keyframes(hana, start, end, end + timedelta(minutes=1), None, settings) == []
