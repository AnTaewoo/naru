"""T0.5 — 공지 원문 → 문장 레코드 (실데이터: 서울경찰청 PDF 3일치, TOPIS 공지 기록).

기대값은 2026-11-07에 PDF를 눈으로 읽어 센 값과 기록 파일을 열어 확인한 값. 옆 주석이 확인 방법.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from naru_ai.notice.source import SmpaPdfSource, TopisNoticeSource, html_lines

KST = timedelta(hours=9)

# PDF를 눈으로 읽어 센 표의 행 수 (머리글 제외), 2026-11-07
SMPA_ROWS = {
    "261107(토) 오늘의 주요집회.pdf": 6,
    "261108(일) 오늘의 주요집회.pdf": 3,
    "261109(월) 오늘의 주요집회.pdf": 4,
}


def test_smpa_rows_become_sentences(smpa_dir: Path) -> None:
    source = SmpaPdfSource(smpa_dir)
    for name, rows in SMPA_ROWS.items():
        assert len(source.parse_file(smpa_dir / name)) == rows, name
    sentences = source.sentences()
    assert len(sentences) == sum(SMPA_ROWS.values())
    assert len({s.sentence_id for s in sentences}) == len(sentences)
    for s in sentences:
        assert s.source_type == "smpa" and s.source_url.startswith("https://www.smpa.go.kr/")
        assert s.published_at.utcoffset() == KST and s.fetched_at.utcoffset() == KST
        assert s.text and not s.text.startswith("집회 일시")  # 머리글은 문장이 아니다
    # 11/7 1행: 셀을 왼쪽부터 공백으로 이은 원문. 장소 셀 안의 줄바꿈은 공백이 된다
    first = sentences[0]
    assert first.sentence_id == "smpa-20261107-r01"
    assert (
        first.text
        == "12:00~16:00 동화면세점 앞 → 종로1R → 동화면세점 앞 <세종대로 등> 50,000명 종로, 남대문"
    )
    assert first.fields["place"] == "동화면세점 앞 → 종로1R → 동화면세점 앞 <세종대로 등>"
    assert first.fields["headcount"] == "50,000명" and first.fields["station"] == "종로, 남대문"
    assert first.event_date == date(2026, 11, 7)
    assert first.published_at == datetime(
        2026, 11, 6, 18, 0, tzinfo=first.published_at.tzinfo
    )  # "(2026. 11. 6. 18:00 기준 작성)"
    assert first.context_prev is None
    assert first.context_next == "12:45~16:00 서초역 8出 ↔ 강남역 <서초대로 등> 3,000명 서초"
    # 11/8 3행: 교보빌딩 정문 앞 <세종대로> 100명 종로 (데모 지점)
    kyobo = next(s for s in sentences if s.sentence_id == "smpa-20261108-r03")
    assert kyobo.text == "15:00~18:00 교보빌딩 정문 앞 <세종대로> 100명 종로"
    assert kyobo.context_next is None and kyobo.event_date == date(2026, 11, 8)


def test_html_lines_keeps_inline_text_together() -> None:
    # TOPIS 본문은 인라인 span으로 쪼개져 온다. 블록 경계에서만 줄을 나눈다 (sample 6301)
    body = (
        "&lt;p&gt;&lt;b&gt;1. 집회일시 :&lt;/b&gt;&lt;b&gt;'26.11&lt;/b&gt;"
        "&lt;b&gt;.7.(토) 16:00 ~ 19:30&lt;/b&gt;&lt;/p&gt;"
        "&lt;p&gt;&amp;nbsp;&lt;/p&gt;&lt;p&gt;- 의사당대로 통제&lt;/p&gt;"
    )
    assert html_lines(body) == ["1. 집회일시 :'26.11.7.(토) 16:00 ~ 19:30", "- 의사당대로 통제"]


def test_topis_recorded_to_sentences(topis_recorded: list[tuple[str, datetime]]) -> None:
    sentences = TopisNoticeSource(topis_recorded, categories=("통제안내", "버스안내")).sentences()
    assert sentences, "기록된 공지에 통제안내·버스안내가 없다"
    notices = {s.notice_id for s in sentences}
    assert len({s.sentence_id for s in sentences}) == len(sentences)
    for s in sentences:
        assert s.source_type == "topis"
        assert s.source_url.startswith("https://topis.seoul.go.kr/notice/openNoticeView.do")
        assert s.published_at.utcoffset() == KST and s.fetched_at.utcoffset() == KST
        assert s.fields["category"] in ("통제안내", "버스안내")
    # 공지마다 첫 문장(l000)은 제목이다
    titles = [s for s in sentences if s.fields["line"] == "0"]
    assert len(titles) == len(notices) and all(s.text == s.fields["title"] for s in titles)


def test_sentences_jsonl_has_sources(notices_dir: Path) -> None:
    rows = [
        json.loads(line)
        for line in (notices_dir / "sentences.jsonl").read_text("utf-8").splitlines()
    ]
    meta = json.loads((notices_dir / "sentences_meta.json").read_text("utf-8"))
    assert len(rows) == meta["total"] and len(rows) > 13
    assert len({r["sentence_id"] for r in rows}) == len(rows)
    fewshot = [r for r in rows if (r.get("fields") or {}).get("fewshot")]
    assert len(fewshot) == 11 and meta["fewshot"]["sentences"] == 11  # 프롬프트 v2 예시 E1~E11
    assert sum(1 for r in rows if r["source_type"] == "smpa") == 13 + 4  # PDF 6+3+4, few-shot 4
    for r in rows:
        assert r["text"] and r["published_at"] and r["fetched_at"]
        if not (r.get("fields") or {}).get("fewshot"):
            assert r["source_url"]  # few-shot news 2건(N099·N100)은 출처 URL 미상 — 태우 보강 대기
        assert r["published_at"].endswith("+09:00")
