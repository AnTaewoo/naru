"""T6.4 — TOPIS 통제·버스 공지(NoticeList OA-22861) → 글 하나 = 문장 하나 → notice_v2 기록 재생.

입력은 기록 원문만 (MANIFEST recorded/topis_notice · recorded/llm notice_v2):
- topis_notice/20261108T192013.json — 2026-11-08 19:20:13 KST NoticeList 1~30
- llm/…/notice_v2/topis-<글 번호>-u<고친 시각>.json — 같은 날 19:26 live 6건(11/8 19:30 에 볼 글)
  + 19:54 22건(나머지 통제·버스 글 전부, 워커 live 경로로 기록 — 태우 2026-11-08 기록 허락)
- llm/…/notice_v2/ 의 나머지 39건(K-001~K-034·smpa 5건) — 11/8 08:03~08:05 기록
기대값은 기록을 열어 확인한 값이다 (줄마다 주석). 제목은 기록에서 읽는다(손으로 치지 않는다).
"""

import json
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from naru_ai.config import Settings
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.notice.candidates import candidate_stem
from naru_ai.notice.parser import ParsedItem, ParsedNotice
from naru_ai.notice.source import NoticeSentence
from naru_ai.notice.topis_feed import post_sentences, title_dates
from naru_ai.publish import CandidatePublisher
from naru_ai.worker import IngestWorker, live_budget
from naru_contracts import SegmentGeom, Source

KST = ZoneInfo("Asia/Seoul")
RECORD = "topis_notice/20261108T192013.json"
EVENING = datetime(2026, 11, 8, 19, 30, tzinfo=KST)  # 기록 10분 뒤
# 30행 = 통제안내·버스안내 28 + 기타안내 2(6274 7호선·6273 6호선). 28건 중 제목 날짜가 다 지난 21건
# (6301 11/7 … 6258 10/31)과 날짜 없이 3일 넘은 6268(10/29 게시)을 빼면 6건. 번호 = bdwr_seq,
# u = update_date 분까지
WATCHED = [
    "topis-6299-u202611061014",  # 11/9~11/14 서강대교 B램프 포장공사 (고침 11/6 10:14:36)
    "topis-6293-u202611052048",  # 제목에 날짜 없음, 게시 11/5 20:48:58 — 3일 안
    "topis-6289-u202611051429",  # 11/9 남이장군사당제
    "topis-6288-u202611051420",  # 11/8 자유민주 마라톤 (게시 14:06:24, 고침 14:20:29)
    "topis-6275-u202611051124",  # 11/8 쉬엄쉬엄모닝 잠실대교
    "topis-6264-u202610271009",  # 10/26~11/8 도로시설물 유지보수 — 늦은 날 11/8
]


@pytest.fixture(scope="module")
def record(recorded_dir: Path) -> dict[str, str]:
    rec: dict[str, str] = json.loads((recorded_dir / RECORD).read_text("utf-8"))
    return rec


@pytest.fixture(scope="module")
def titles(record: dict[str, str]) -> dict[str, str]:
    rows = ET.fromstring(record["raw"]).findall("row")
    return {r.findtext("bdwr_seq") or "": r.findtext("bdwr_ttl_nm") or "" for r in rows}


@pytest.fixture(scope="module")
def worker(recorded_dir: Path) -> IngestWorker:
    settings = Settings(NARU_TOPIS_RECORD=str(recorded_dir / RECORD))
    return IngestWorker(settings, CandidatePublisher("http://127.0.0.1:9", "unused"))  # 안 보낸다


@pytest.fixture(scope="module")
def parsed(worker: IngestWorker, record: dict[str, str]) -> dict[str, ParsedNotice]:
    out = {}
    for p in _posts(record, EVENING):
        out[p.notice_id] = worker.parser.parse(NoticeEnvelope.from_sentence(p.to_json()))
    return out


def _posts(record: dict[str, str], now: datetime) -> list[NoticeSentence]:
    return post_sentences(record["raw"], datetime.fromisoformat(record["called_at"]), now)


def test_title_dates(titles: dict[str, str]) -> None:
    nov8 = date(2026, 11, 8)
    # '10/26(금)~11/8(일) …' 범위의 두 날
    assert title_dates(titles["6264"], nov8) == [date(2026, 10, 26), date(2026, 11, 8)]
    assert title_dates(titles["6293"], nov8) == []  # '[서대문구] … 서대문07번 …' 슬래시 없음
    assert title_dates(titles["6268"], nov8) == []  # '(405, 740번 노선조정)'
    # 해를 넘겨 본 글: 2027-02-01 에 본 '11/7(토)'(6301)는 반년 넘게 뒤라 지난해
    assert title_dates(titles["6301"], date(2027, 2, 1)) == [date(2026, 11, 7)]


def test_posts_to_watch_on_nov8_evening(record: dict[str, str]) -> None:
    assert [p.sentence_id for p in _posts(record, EVENING)] == WATCHED


def test_past_posts_drop_out_next_morning(record: dict[str, str]) -> None:
    # 11/9 09:00 — 11/8 로 끝난 6288·6275·6264, 게시 3일이 넘은 날짜 없는 6293 이 빠진다
    posts = _posts(record, datetime(2026, 11, 9, 9, 0, tzinfo=KST))
    assert [p.sentence_id for p in posts] == [WATCHED[0], WATCHED[2]]


def test_one_post_is_one_sentence(record: dict[str, str]) -> None:
    p = {s.notice_id: s for s in _posts(record, EVENING)}["topis-6288"]
    lines = p.text.splitlines()
    assert lines[0] == p.fields["title"] and len(lines) == 12  # 제목 + 본문 11줄(bdwr_cts)
    # 줄로 나누면(T0.5) 통제일시와 통제구간이 다른 문장이 된다 — 글 하나라 같이 읽힌다
    assert "- 통제일시 : 2026.11.8.(일) 07:00 ~ 10:30" in lines
    assert "- 통제구간 : 서울광장~종로~동대문~숭례문~광교~무교동 등" in lines
    assert p.published_at == datetime(2026, 11, 5, 14, 6, 24, tzinfo=KST)  # create_date
    assert p.fetched_at == datetime(2026, 11, 8, 19, 20, 13, tzinfo=KST)  # 기록 called_at
    assert p.source_url.endswith("openNoticeView.do?blbdDivCd=02&bdwrSeq=6288")  # url


def test_recorded_parses(parsed: dict[str, ParsedNotice]) -> None:
    got = {
        nid: [
            (it.kind, it.impact, it.impact_reason, it.window.start, it.confidence)
            for it in (i.item for i in p.items)
        ]
        for nid, p in parsed.items()
    }
    # 기록 tool_use.input 그대로. 0.8 = TOPIS 인데 차로 정보 없음(규칙서 §9-10)
    assert got == {
        "topis-6299": [("closure", "none", "motorway", "2026-11-09T21:00+09:00", 0.0)],  # 램프
        "topis-6293": [("closure", "none", "vehicle_measure", "2026-11-06T09:00+09:00", 0.0)],
        "topis-6289": [("closure", "blocks", None, "2026-11-09T08:30+09:00", 0.8)],
        "topis-6288": [("marathon", "blocks", None, "2026-11-08T07:00+09:00", 0.8)],  # 통제일시
        "topis-6275": [("closure", "blocks", None, "2026-11-08T05:00+09:00", 0.8)],
        "topis-6264": [("closure", "none", "vehicle_measure", "2026-10-26T22:00+09:00", 0.0)],
    }
    assert parsed["topis-6288"].items[0].item.window.end == "2026-11-08T10:30+09:00"


def test_unresolved_names_make_no_candidates(
    worker: IngestWorker, parsed: dict[str, ParsedNotice], caplog: pytest.LogCaptureFixture
) -> None:
    # 6288: 구간 서울광장→무교동 은 '무교동' span 이 없어 버린다(T4.2a 정렬기). 지점
    # '서울광장 일대'는 AREA(점 아님). 6289 남이장군사당·용문새마을금고·용문동 107번지 앞,
    # 6275 잠실대교·잠실수중보는 교차로 사전에도 카카오 기록에도 없다 — 추측 좌표 0
    item = parsed["topis-6288"].items[0]
    assert item.dropped_segments == 1 and [p.name for p in item.item.points] == ["서울광장 일대"]
    with caplog.at_level(logging.INFO, logger="naru_ai.notice.candidates"):  # 운영 워커는 INFO
        assert all(worker.builder.build(p) == [] for p in parsed.values())
    logged = [r.__dict__["place"] for r in caplog.records if r.getMessage() == "unresolved point"]
    # 글 순서 6289·6288·6275
    assert logged == ["용문동 107번지 앞", "서울광장 일대", "잠실수중보"]
    assert worker._live_budget(EVENING) == 0  # client 없음
    assert worker.topis_batch(EVENING) is None and worker.topis_failed == set()


def test_topis_batch_on_nov7_morning(worker: IngestWorker, record: dict[str, str]) -> None:
    # 11/7 09:00 에 볼 글 14건(제목 날짜가 11/7 이후 13건 + 날짜 없는 6293) 중 후보가 나오는 건
    # 6300 '도심 대규모 집회 …' 하나. 본문 '숭례문R~대한문R 왕복 전차로 집회', '숭례문R~세종R
    # 역방향 … 행진', '숭례문R~서울고용노동청 … 행진' → 구간 셋. 대한문오거리·서울고용노동청은
    # 못 풀어 그 둘은 숭례문 점만
    nov7 = datetime(2026, 11, 7, 9, 0, tzinfo=KST)
    assert len(_posts(record, nov7)) == 14
    batch = worker.topis_batch(nov7)
    assert batch is not None and batch.producer == "notice"
    cands = {c.candidate_id: c for c in batch.candidates}
    assert list(cands) == [f"topis-6300-i1-{k}" for k in ("seg1-from", "seg2", "seg3-from")]
    c = cands["topis-6300-i1-seg2"]
    assert isinstance(c.geometry, SegmentGeom)
    ends = (c.geometry.from_.gazetteer_id, c.geometry.to.gazetteer_id)
    assert ends == ("625", "535")  # OA-23081 숭례문오거리·세종대로사거리 (test_resolver)
    assert c.source is Source.topis and c.confidence == 0.8 and not c.review_required
    assert (c.window.start, c.window.end) == (
        datetime(2026, 11, 7, 5, 0, tzinfo=KST),  # '05:00부터 통제 예정'
        datetime(2026, 11, 7, 17, 0, tzinfo=KST),  # 행진 '16:00~17:00'
    )
    assert c.notice_ref is not None and c.notice_ref.sentence_id == "topis-6300-u202611061734"
    assert c.evidence[0].ref.endswith(f"{RECORD}#topis-6300-u202611061734")  # 버전은 근거에만
    assert worker.topis_batch(nov7).batch_id == batch.batch_id  # 같은 내용 = 같은 배치(BE 멱등)


def test_area_endpoint_uses_the_intersection_of_the_same_name(
    worker: IngestWorker, record: dict[str, str]
) -> None:
    # 태우 C①(2026-11-08): 구간 끝점은 AREA 라도 교차로 사전에 같은 이름이 있으면 그 교차로.
    # 태그는 기록 그대로 — 6288 '서울광장 일대'(AREA, 정규 이름 서울광장), 6262 '광화문광장'(AREA,
    # 구간 셋의 출발), 6287 '여의도'(AREA). OA-23081 교차로명: 서울광장 7088 · 광화문 677 만 있고
    # 광화문광장·여의도는 없다
    posts = {p.notice_id: p for p in _posts(record, datetime(2026, 10, 26, tzinfo=KST))}

    def item(nid: str) -> ParsedItem:
        env = NoticeEnvelope.from_sentence(posts[nid].to_json())
        return worker.parser.parse(env).items[0]

    res = worker.builder.resolver
    seoul, plaza, yeouido = item("topis-6288"), item("topis-6262"), item("topis-6287")
    assert seoul.tag_of("서울광장") == "AREA"
    assert res.resolve("서울광장", "AREA") is None  # 지점은 그대로 — AREA 는 점이 아니다
    p = res.resolve_endpoint("서울광장", seoul.tag_of("서울광장"))
    assert p is not None and (p.gazetteer_source, p.gazetteer_id) == ("seoul_intersection", "7088")
    assert plaza.segments[0].from_ == "광화문광장" and plaza.tag_of("광화문광장") == "AREA"
    assert res.resolve_endpoint("광화문광장", "AREA") is None  # 사전에 없으면 그대로 None
    assert res.resolve_endpoint("여의도", yeouido.tag_of("여의도")) is None


def test_candidate_ids_drop_the_post_version() -> None:
    # 고친 글(새 u<시각>)이 같은 후보 ID 로 덮는다. 경찰청 행 ID 는 그대로
    assert candidate_stem(WATCHED[3]) == "topis-6288"
    assert candidate_stem("smpa-20261107-r04") == "smpa-20261107-r04"  # 기록 smpa-20261107-r04


def test_live_budget() -> None:
    # 11/8 notice_v2 기록 45건(아래 테스트) 기준 — 한 번 10, 하루 200
    assert live_budget(10, 200, 45) == 10
    assert live_budget(10, 50, 45) == 5
    assert live_budget(10, 45, 45) == 0
    assert live_budget(10, 40, 45) == 0  # 상한을 낮춰도 음수가 아니다


def test_saved_today_counts_by_kst_day(worker: IngestWorker) -> None:
    rec = worker.recorder

    def called_on(day: date) -> int:
        stamps = (json.loads(p.read_text("utf-8"))["called_at"] for p in rec.dir.glob("*.json"))
        return sum(1 for s in stamps if datetime.fromisoformat(s).astimezone(KST).date() == day)

    nov8 = called_on(date(2026, 11, 8))
    assert nov8 >= 67  # 08:03~08:05 39건 + topis 19:26 6건·19:54 22건 (+ 그날 운영 워커 몫)
    assert rec.saved_today(datetime(2026, 11, 8, 23, 59, tzinfo=KST)) == nov8
    # K-001 called_at 2026-11-07T23:03:49+00:00 — UTC 로는 11/7 이지만 KST 로는 11/8
    assert rec.saved_today(datetime(2026, 11, 7, 12, 0, tzinfo=KST)) == 0
