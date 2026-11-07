"""T4.2c — CandidateBuilder: 기록된 파서 출력 + 지명사전 → ClosureCandidate (INTERFACE §1).

좌표 기대값은 카카오 기록 documents[0] (test_resolver 와 같은 값). 못 푼 이름은 후보 없음.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from naru_ai.config import Settings
from naru_ai.llm.prompt import NoticeEnvelope
from naru_ai.llm.recorder import LLMRecorder
from naru_ai.notice.candidates import CandidateBuilder
from naru_ai.notice.gazetteer import Gazetteer
from naru_ai.notice.parser import NoticeParser, ParsedNotice
from naru_ai.notice.resolver import KakaoRecords, Resolver
from naru_contracts import (
    CandidateBatch,
    ClosureType,
    EvidenceKind,
    Impact,
    PointGeom,
    SegmentGeom,
    Source,
)

KST = timezone(timedelta(hours=9))


@pytest.fixture(scope="module")
def parsed(notices_dir: Path) -> dict[str, ParsedNotice]:
    settings = Settings()
    recorder = LLMRecorder(settings.recorded_llm_dir, settings.llm_model, settings.prompt_version)
    rows = {}
    for line in (notices_dir / "sentences.jsonl").read_text("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["sentence_id"]] = row
    parser = NoticeParser(settings, recorder)
    ids = [i for i in recorder.list_ids() if i in rows]  # 평가 기록(K-*·C-*) 제외
    return {sid: parser.parse(NoticeEnvelope.from_sentence(rows[sid])) for sid in ids}


@pytest.fixture(scope="module")
def gazetteer(seoul_spatial_dir: Path, nodelink_seoul_dir: Path) -> Gazetteer:
    return Gazetteer.load(seoul_spatial_dir / "OA-23081.xlsx", nodelink_seoul_dir / "link.gpkg")


@pytest.fixture(scope="module")
def builder(gazetteer: Gazetteer, recorded_dir: Path) -> CandidateBuilder:
    return CandidateBuilder(Resolver(gazetteer, KakaoRecords(recorded_dir)))


def test_segment_candidate_from_recorded_parse(
    builder: CandidateBuilder, parsed: dict[str, ParsedNotice]
) -> None:
    # smpa-20261107-r06: 의사당역 5出 → 민주당사 <은행로 등>
    (c,) = builder.build(parsed["smpa-20261107-r06"])
    assert c.candidate_id == "smpa-20261107-r06-i1-seg1"
    assert c.source is Source.smpa and c.type is ClosureType.march and c.impact is Impact.blocks
    assert isinstance(c.geometry, SegmentGeom)
    assert c.geometry.from_.canonical == "의사당역 5번출구"
    assert c.geometry.from_.lng == 126.91724371956369  # 카카오 8200572 x
    assert c.geometry.to.gazetteer_id == "17071011" and c.geometry.via == []
    assert c.geometry.road is None and c.geometry.road_class is None  # 힌트는 road 가 아니다
    assert c.window.start == datetime(2026, 11, 7, 16, 0, tzinfo=KST)
    assert c.window.end == datetime(2026, 11, 7, 19, 0, tzinfo=KST)
    assert c.confidence == 0.85 and c.review_required is False and c.approx is False
    assert c.evidence[0].kind is EvidenceKind.notice
    assert c.evidence[0].ref.endswith("#smpa-20261107-r06")
    assert c.notice_ref is not None and c.notice_ref.notice_id == "smpa-20261107"
    assert c.notice_ref.excerpt.startswith("16:00~19:00 의사당역")
    # smpa-20261109-r01: 하나증권 앞 → 금감원 → 여의도역 (via 카카오, 끝은 교차로 사전)
    (c,) = builder.build(parsed["smpa-20261109-r01"])
    assert isinstance(c.geometry, SegmentGeom)
    assert c.geometry.from_.gazetteer_id == "452895564"  # 하나증권 본사 (여의도 힌트)
    assert [v.gazetteer_id for v in c.geometry.via] == ["8239028"]  # 금융감독원 서울본원
    assert c.geometry.to.gazetteer_source == "seoul_intersection"
    assert c.confidence == 0.75 and c.review_required is False  # 0.7 이상


def test_unresolved_end_falls_back_to_point(
    builder: CandidateBuilder, parsed: dict[str, ParsedNotice], gazetteer: Gazetteer, tmp_path: Path
) -> None:
    # smpa-20261109-r02: 국회의사당역 2出 → 사랑채 동측 건너편 — '사랑채' 는 여의도 힌트로 못 푼다
    (c,) = builder.build(parsed["smpa-20261109-r02"])
    assert c.candidate_id == "smpa-20261109-r02-i1-seg1-from"
    assert isinstance(c.geometry, PointGeom)
    assert c.geometry.coordinates == (126.91779773116284, 37.52859517485727)  # 카카오 8690984
    assert c.type is ClosureType.march and c.confidence == 0.75
    # 카카오 기록이 없으면(교차로 사전만): r06·r02 는 후보 없음, r01 은 교차로 '여의도역'(182)
    # 쪽만 point — 추측 좌표 0
    bare = CandidateBuilder(Resolver(gazetteer, KakaoRecords(tmp_path)))
    assert bare.build(parsed["smpa-20261107-r06"]) == []
    assert bare.build(parsed["smpa-20261109-r02"]) == []
    (only_to,) = bare.build(parsed["smpa-20261109-r01"])
    assert only_to.candidate_id == "smpa-20261109-r01-i1-seg1-to"
    assert isinstance(only_to.geometry, PointGeom)
    assert only_to.geometry.coordinates == (126.92429721253396, 37.52174601107977)  # 교차로 182
    # contracts 왕복
    batch = CandidateBatch(
        batch_id="t", produced_at=datetime.now(KST), producer="notice",
        candidates=[x for p in parsed.values() for x in builder.build(p)],
    )  # fmt: skip
    again = CandidateBatch.model_validate_json(batch.model_dump_json())
    assert len(again.candidates) == 6  # 문장 5건: r01 1 + r04 2 + r06·1109-r01·1109-r02 각 1
