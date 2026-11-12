"""평가 입력 — 라벨 케이스(cases_v1.jsonl)와 합성 입력(syntitan csv) 적재 (T4.3). 비교는 eval.py."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from naru_ai.llm.prompt import NoticeEnvelope

SOURCE_MAP = {"topis_notice": "topis", "topis_incident": "topis"}  # 봉투 source (프롬프트 §1)


class ExpectedSegment(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    from_: str = Field(alias="from")
    to: str
    via: list[str] = []
    road: str | None = None
    direction: str = "one_way"


class ExpectedPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str


class ExpectedItem(BaseModel):
    """라벨의 item — 비교하는 필드만. spans·인원·관할서는 라벨에 없다."""

    model_config = ConfigDict(extra="ignore")
    window: dict[str, str | None]
    approx: bool = False
    kind: str
    impact: str
    impact_reason: str | None = None
    segments: list[ExpectedSegment] = []
    points: list[ExpectedPoint] = []
    toward: str | None = None


@dataclass(frozen=True)
class Case:
    case_id: str
    notice_id: str
    source: str
    text: str
    event_date: str | None
    published_at: str
    source_url: str
    type: str
    expected: tuple[ExpectedItem, ...]

    def envelope(self) -> NoticeEnvelope:
        return NoticeEnvelope(
            sentence_id=self.case_id,
            source=SOURCE_MAP.get(self.source, self.source),
            text=self.text,
            event_date=self.event_date,
            published_at=self.published_at,
            fetched_at=self.published_at,
            notice_id=self.notice_id,
            source_url=self.source_url,
        )


def load_cases(path: Path) -> list[Case]:
    out: list[Case] = []
    for line in path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out.append(
            Case(
                case_id=row["case_id"],
                notice_id=row["notice_id"],
                source=row["source"],
                text=row["text"],
                event_date=row.get("event_date"),
                published_at=row["published_at"],
                source_url=row["source_url"],
                type=row["type"],
                expected=tuple(ExpectedItem.model_validate(i) for i in row["expected"]["items"]),
            )
        )
    return out


def load_synthetic(path: Path, published_at: str) -> list[NoticeEnvelope]:
    """Syntitan agent_questions.csv (case_id, input). 정답 없음 — 견고성용."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        NoticeEnvelope(
            sentence_id=r["case_id"],
            source="news",
            text=r["input"],
            event_date=None,
            published_at=published_at,
            fetched_at=published_at,
        )
        for r in rows
    ]
