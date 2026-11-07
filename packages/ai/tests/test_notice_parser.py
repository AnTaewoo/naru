"""T4.2a — NoticeParser: 기록 재생 → 정렬기 start/end → segments 검증. live 호출 없음."""

import json
from pathlib import Path

import pytest

from naru_ai.config import Settings
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.notice.parser import NoticeParser, RecordingMissingError


@pytest.fixture(scope="module")
def sentences(notices_dir: Path) -> dict[str, dict[str, object]]:
    rows = {}
    for line in (notices_dir / "sentences.jsonl").read_text("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["sentence_id"]] = row
    return rows


@pytest.fixture(scope="module")
def parser() -> NoticeParser:
    settings = Settings()
    recorder = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    assert recorder.list_ids(), "기록 없음: make record-llm 먼저"
    return NoticeParser(settings, recorder)  # client 없음 → 재생만


def test_replay_aligns_every_span(
    parser: NoticeParser, sentences: dict[str, dict[str, object]]
) -> None:
    ids = [i for i in parser.recorder.list_ids() if i in sentences]  # 평가 기록(K-*·C-*) 제외
    assert len(ids) >= 3
    for sid in ids:
        env = NoticeEnvelope.from_sentence(sentences[sid])
        assert env.notice_id and env.source_url.startswith("https://")
        parsed = parser.parse(env)
        assert parsed.model == "claude-haiku-5-5" and parsed.prompt_version == "notice_v1"
        assert len(parsed.items) == 1 and parsed.dropped_spans == 0
        (pi,) = parsed.items
        assert pi.dropped_segments == 0 and len(pi.segments) == len(pi.item.segments) >= 1
        for span in pi.spans:
            assert env.text[span.start : span.end] == span.text
        assert pi.tag_of(pi.segments[0].from_) == "POI"


def test_replay_values(parser: NoticeParser, sentences: dict[str, dict[str, object]]) -> None:
    # smpa-20261107-r06: "16:00~19:00 의사당역 5出 → 민주당사 <은행로 등> 5,000명 영등포"
    parsed = parser.parse(NoticeEnvelope.from_sentence(sentences["smpa-20261107-r06"]))
    (pi,) = parsed.items
    assert [(s.text, s.tag, s.start) for s in pi.spans] == [
        ("16:00~19:00", "TIME", 0),
        ("의사당역 5出", "POI", 12),
        ("민주당사", "POI", 22),
        ("은행로", "ROAD", 28),
    ]
    assert pi.area_hint() is None and pi.tag_of("은행로") == "ROAD"
    # smpa-20261109-r01: 지역 힌트 여의도(AREA), via 금감원
    parsed = parser.parse(NoticeEnvelope.from_sentence(sentences["smpa-20261109-r01"]))
    (pi,) = parsed.items
    assert pi.area_hint() == "여의도" and pi.segments[0].via == ["금감원"]
    # 기록 없는 문장 + client 없음 → 실패 (가짜 응답 없음)
    with pytest.raises(RecordingMissingError):
        parser.parse(NoticeEnvelope.from_sentence(sentences["smpa-20261107-r02"]))  # 기록 없음
