"""NoticeParser — 공지 한 건 → ParsedNotice (ARCHITECTURE AI, T4.2a).

기록(LLMRecorder)이 있으면 재생, 없으면 client 로 호출해 기록한다(client 가 None 이면 실패).
정렬기: span.text 를 문장에서 찾아 start/end. 못 찾으면 버리고 개수를 남긴다.
segment 의 from/to 는 spans 의 canonical(또는 원문 text) 과 일치해야 한다 — 아니면 segment 를 버린다
(CONVENTIONS §3.2). 좌표는 여기 없다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from naru_ai.config import Settings
from naru_ai.llm.client import AnthropicClient, ToolSpec
from naru_ai.llm.notice_schema import (
    TOOL_DESCRIPTION,
    TOOL_NAME,
    NoticeItem,
    NoticeOutput,
    Segment,
    strict_input_schema,
)
from naru_ai.llm.prompt import NoticeEnvelope, NoticePrompt
from naru_ai.llm.recorder import LLMRecorder

log = logging.getLogger(__name__)


class RecordingMissingError(Exception):
    pass


@dataclass(frozen=True)
class AlignedSpan:
    text: str
    tag: str
    canonical: str
    start: int
    end: int


@dataclass(frozen=True)
class ParsedItem:
    item: NoticeItem
    spans: tuple[AlignedSpan, ...]
    segments: tuple[Segment, ...]  # 양 끝이 spans 에 있는 것만
    dropped_spans: int
    dropped_segments: int

    def tag_of(self, name: str) -> str | None:
        for s in self.spans:
            if name in (s.canonical, s.text):
                return s.tag
        return None

    def canonical_of(self, name: str) -> str:
        """spans 의 정규 이름 — 원문 표현("숭례문R")이면 그 span 의 canonical, 없으면 그대로."""
        for s in self.spans:
            if name in (s.canonical, s.text):
                return s.canonical
        return name

    def area_hint(self) -> str | None:
        for s in self.spans:
            if s.tag == "AREA":
                return s.canonical
        return None


@dataclass(frozen=True)
class ParsedNotice:
    envelope: NoticeEnvelope
    model: str
    prompt_version: str
    items: tuple[ParsedItem, ...] = field(default_factory=tuple)

    @property
    def dropped_spans(self) -> int:
        return sum(i.dropped_spans for i in self.items)


class NoticeParser:
    def __init__(
        self,
        settings: Settings | None = None,
        recorder: LLMRecorder | None = None,
        prompt: NoticePrompt | None = None,
        client: AnthropicClient | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.recorder = recorder or LLMRecorder(
            self.settings.recorded_llm_dir, self.settings.llm_model, self.settings.prompt_version
        )
        self.prompt = prompt or NoticePrompt.load(self.settings.prompt_version)
        self.client = client
        self.tool = ToolSpec(TOOL_NAME, TOOL_DESCRIPTION, strict_input_schema())

    def parse(self, envelope: NoticeEnvelope) -> ParsedNotice:
        output = NoticeOutput.model_validate(self._tool_input(envelope))
        items = tuple(align(item, envelope.text) for item in output.items)
        dropped = sum(i.dropped_spans for i in items)
        if dropped:
            log.warning(
                "spans dropped", extra={"sentence_id": envelope.sentence_id, "dropped": dropped}
            )
        return ParsedNotice(envelope, self.recorder.model, self.recorder.prompt_version, items)

    def _tool_input(self, envelope: NoticeEnvelope) -> dict[str, object]:
        sid = envelope.sentence_id
        if self.recorder.exists(sid):
            return self.recorder.load(sid).tool_input()
        if self.client is None:
            raise RecordingMissingError(f"{sid}: 기록 없음 — make record-llm 먼저 (live 는 기록용)")
        messages = self.prompt.build_messages(envelope)
        completion = self.client.complete_tool(self.prompt.system, messages, self.tool)
        self.recorder.save(sid, self.prompt.system, messages, self.tool, completion)
        return completion.input


def align(item: NoticeItem, text: str) -> ParsedItem:
    spans: list[AlignedSpan] = []
    dropped_spans = 0
    for s in item.spans:
        start = text.find(s.text)
        if start < 0:
            dropped_spans += 1
            continue
        spans.append(AlignedSpan(s.text, s.tag, s.canonical, start, start + len(s.text)))
    names = {s.canonical for s in spans} | {s.text for s in spans}
    kept = tuple(seg for seg in item.segments if seg.from_ in names and seg.to in names)
    return ParsedItem(
        item=item,
        spans=tuple(spans),
        segments=kept,
        dropped_spans=dropped_spans,
        dropped_segments=len(item.segments) - len(kept),
    )
