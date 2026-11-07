"""T4.1 — 프롬프트 v1 · strict 스키마 · 기록 재생. live 호출 없음 (CONVENTIONS §3.3).

기록이 없으면 실패한다 (make record-llm 먼저). 기록의 model·prompt_version 이 설정과 다르면 실패.
기대값은 기록 파일을 열어 확인한 값 (2026-11-07, claude-haiku-5-5 / notice_v1).
"""

import json
from pathlib import Path

import pytest

from naru_ai.config import Settings
from naru_ai.llm.notice_schema import TOOL_NAME, NoticeOutput, strict_input_schema
from naru_ai.llm.prompt import NoticeEnvelope, NoticePrompt
from naru_ai.llm.recorder import LLMRecorder, Recording, RecordingMismatchError


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="module")
def sentences(notices_dir: Path) -> dict[str, dict[str, object]]:
    rows = {}
    for line in (notices_dir / "sentences.jsonl").read_text("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["sentence_id"]] = row
    return rows


@pytest.fixture(scope="module")
def recorder(settings: Settings) -> LLMRecorder:
    rec = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    assert rec.list_ids(), f"기록 없음: {rec.dir} — make record-llm 먼저"
    return rec


def test_strict_schema_has_no_loose_objects() -> None:
    schema = strict_input_schema()
    assert "$defs" not in json.dumps(schema)
    objects: list[dict[str, object]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                objects.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    assert len(objects) >= 7  # NoticeOutput, NoticeItem, Window, Lanes, Segment, Point, Span
    for obj in objects:
        props = obj["properties"]
        assert isinstance(props, dict)
        assert obj["additionalProperties"] is False and obj["required"] == list(props)
    dumped = json.dumps(schema, ensure_ascii=False)
    for key in ("window", "approx", "kind", "impact", "impact_reason", "toward", "spans"):
        assert f'"{key}"' in dumped
    assert '"from"' in dumped and '"from_"' not in dumped  # alias 로 나간다
    assert "coordinates" not in json.dumps(schema) and "lng" not in json.dumps(schema)


def test_prompt_v1_fewshot_ids_are_real_sentences(
    settings: Settings, sentences: dict[str, dict[str, object]]
) -> None:
    prompt = NoticePrompt.load(settings.prompt_version)
    assert prompt.version == "notice_v1"
    ids = prompt.fewshot_ids()
    assert len(ids) >= 8 and set(ids) <= set(sentences)
    for sid in ids:  # few-shot 의 원문이 실제 문장 그대로인지
        assert str(sentences[sid]["text"]) in prompt.system, sid
    for rule in ("좌표", "impact", "toward", "approx", "items", "motorway", "unknown_near"):
        assert rule in prompt.system or rule == "unknown_near"
    env = NoticeEnvelope.from_sentence(sentences["smpa-20261107-r01"])
    msg = prompt.build_messages(env)
    assert msg[0]["role"] == "user" and "동화면세점" in str(msg[0]["content"])
    assert '"event_date": "2026-11-07"' in str(msg[0]["content"])


def test_recorded_replays_validate_against_schema(
    recorder: LLMRecorder, settings: Settings, sentences: dict[str, dict[str, object]]
) -> None:
    for sid in recorder.list_ids():
        rec = recorder.load(sid)
        assert rec.model == settings.llm_model and rec.prompt_version == settings.prompt_version
        tool = rec.request["tool"]
        assert isinstance(tool, dict) and tool["name"] == TOOL_NAME
        assert "api_key" not in json.dumps(rec.request) and "sk-ant" not in json.dumps(rec.response)
        out = NoticeOutput.model_validate(rec.tool_input())
        assert out.items, sid
        text = str(sentences[sid]["text"])
        for item in out.items:
            assert 0.0 <= item.confidence <= 1.0
            for span in item.spans:
                assert span.text in text, (sid, span.text)  # 정렬기(T4.2)가 찾을 수 있어야 한다
            assert all(s.from_ and s.to for s in item.segments)
    # 모델·프롬프트가 다른 recorder 로 열면 fail
    other = LLMRecorder(settings.recorded_llm_dir, "claude-other", settings.prompt_version)
    other.dir = recorder.dir
    with pytest.raises(RecordingMismatchError):
        other.load(recorder.list_ids()[0])
    with pytest.raises(FileNotFoundError):
        recorder.load("no-such-sentence")


def test_recorded_values_match_rules(recorder: LLMRecorder) -> None:
    """기대값은 기록 파일을 열어 확인한 값 (2026-11-07 기록, claude-haiku-5-5 / notice_v1)."""
    # smpa-20261107-r06: 16:00~19:00 의사당역 5出 → 민주당사 <은행로 등> 5,000명 영등포
    rec: Recording = recorder.load("smpa-20261107-r06")
    item = NoticeOutput.model_validate(rec.tool_input()).items[0]
    assert item.kind == "march" and item.impact == "blocks" and item.impact_reason is None
    assert (item.window.start, item.window.end) == (
        "2026-11-07T16:00:00+09:00",
        "2026-11-07T19:00:00+09:00",
    )
    (seg,) = item.segments
    assert (seg.from_, seg.to, seg.via, seg.direction) == (
        "의사당역 5번출구",
        "민주당사",
        [],
        "one_way",
    )
    assert seg.road is None and item.road_hints == ["은행로"]  # 힌트는 road 로 올리지 않았다
    assert item.reported_people == 5000 and item.police_stations == ["영등포"]
    assert {(s.text, s.tag) for s in item.spans} == {
        ("16:00~19:00", "TIME"),
        ("의사당역 5出", "POI"),
        ("민주당사", "POI"),
        ("은행로", "ROAD"),
    }
    assert item.confidence == 0.85 and item.approx is False
    # smpa-20261109-r01: 하나증권 앞 → 금감원·여의도역 — `·` 는 연속 두 지점 (via, to)
    item = NoticeOutput.model_validate(recorder.load("smpa-20261109-r01").tool_input()).items[0]
    (seg,) = item.segments
    assert (seg.from_, seg.via, seg.to) == ("하나증권 앞", ["금감원"], "여의도역")
    assert item.road_hints == ["여의도"] and item.reported_people == 200
    assert item.confidence == 0.75  # 행진 + 지역명 힌트(도로 아님)
    # smpa-20261109-r02: 국회의사당역 2出 → 사랑채 동측 건너편 — 방향어를 떼지 않았다
    item = NoticeOutput.model_validate(recorder.load("smpa-20261109-r02").tool_input()).items[0]
    (seg,) = item.segments
    assert (seg.from_, seg.to) == ("국회의사당역 2번출구", "사랑채 동측 건너편")
    assert item.police_stations == ["영등포", "마포", "서대문", "종로"]
    assert rec.usage["cache_creation_input_tokens"] == 11072  # 시스템 프롬프트가 캐시됐다
