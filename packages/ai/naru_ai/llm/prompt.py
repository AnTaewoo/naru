"""프롬프트 로드·입력 봉투 — llm/prompts/<version>.md 가 시스템 프롬프트, 규칙서 §1.3 이 user 턴.

프롬프트를 바꾸면 버전을 올리고 기록을 새로 만든다 (CONVENTIONS §3.2). few-shot 문장은 파일 안에
sentence_id 로 적혀 있다 (data/raw/notices/sentences.jsonl).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from anthropic.types import MessageParam

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SENTENCE_ID = re.compile(r"\b(?:smpa|topis)-[0-9]+-[lr][0-9]+\b")


@dataclass(frozen=True)
class NoticeEnvelope:
    """규칙서 §1.3 입력 봉투. sentences.jsonl 한 행에서 만든다."""

    sentence_id: str
    source: str  # smpa | topis
    text: str
    event_date: str | None
    published_at: str
    fetched_at: str

    @classmethod
    def from_sentence(cls, row: dict[str, object]) -> NoticeEnvelope:
        return cls(
            sentence_id=str(row["sentence_id"]),
            source=str(row["source_type"]),
            text=str(row["text"]),
            event_date=None if row.get("event_date") is None else str(row["event_date"]),
            published_at=str(row["published_at"]),
            fetched_at=str(row["fetched_at"]),
        )

    def as_json(self) -> str:
        body = {
            "source": self.source,
            "text": self.text,
            "event_date": self.event_date,
            "published_at": self.published_at,
            "fetched_at": self.fetched_at,
        }
        return json.dumps(body, ensure_ascii=False, indent=1)


@dataclass(frozen=True)
class NoticePrompt:
    version: str
    system: str

    @classmethod
    def load(cls, version: str, prompts_dir: Path = PROMPTS_DIR) -> NoticePrompt:
        path = prompts_dir / f"{version}.md"
        if not path.exists():
            raise FileNotFoundError(f"프롬프트 없음: {path}")
        text = path.read_text("utf-8")
        first = text.splitlines()[0] if text else ""
        if version not in first:
            raise ValueError(f"{path.name} 첫 줄에 버전 {version} 이 없다: {first!r}")
        return cls(version=version, system=text)

    def fewshot_ids(self) -> list[str]:
        seen: list[str] = []
        for m in SENTENCE_ID.findall(self.system):
            if m not in seen:
                seen.append(m)
        return seen

    def build_messages(self, envelope: NoticeEnvelope) -> list[MessageParam]:
        content = (
            "다음 공지 한 건을 규칙대로 구조화해 parse_notice 도구로만 답한다. 입력 봉투:\n"
            + envelope.as_json()
        )
        return [{"role": "user", "content": content}]
