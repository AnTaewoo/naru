"""NoticeSource — 공지 원문을 문장 레코드로 바꾼다 (ARCHITECTURE §AI, ROADMAP T0.5).

문장을 다듬거나 지어내지 않는다. 표의 셀과 본문의 줄을 그대로 옮기고, 셀 안 줄바꿈과 연속 공백만
한 칸 공백으로 바꾼다. 출처(source_url·published_at·fetched_at)는 레코드마다 붙는다.

  SmpaPdfSource      서울경찰청 '오늘의 주요집회' PDF 표 — 행 하나 = 문장 하나
                     (셀을 왼쪽부터 공백으로 이음)
  TopisNoticeSource  TOPIS 공지 (열린데이터광장 NoticeList, xml) — 제목 + 본문 줄 하나 = 문장 하나
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pdfplumber

KST = timezone(timedelta(hours=9))

# 서울경찰청 '오늘의 집회' 게시판 (로그인 필요, 첨부 PDF를 사람이 받는다).
# 2026-11-07 직접 접속은 "시스템 오류" — 태우가 받은 페이지 URL로 바꿀 것
SMPA_BOARD_URL = "https://www.smpa.go.kr/user/nd54515.do"
SMPA_HEADER = ("집회 일시", "집회 장소(행진로)", "신고인원", "관할서", "비고")
SMPA_FIELDS = ("time", "place", "headcount", "station", "note")
SMPA_BASIS_RE = re.compile(
    r"\((\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{1,2}):(\d{2})\s*기준 작성\)"
)
SMPA_DATE_RE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\(")

TOPIS_SERVICE = "NoticeList"
TOPIS_VIEW_URL = "https://topis.seoul.go.kr/notice/openNoticeView.do"
_BLOCK_TAG_RE = re.compile(r"<(?:br|/p|/div|/li|/tr|/h[1-6]|/table)\b[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class NoticeSentence:
    """공지 문장 하나. `fields`는 출처별 원문 조각(표 셀·제목 등)."""

    sentence_id: str
    notice_id: str
    text: str
    context_prev: str | None
    context_next: str | None
    source_type: str  # smpa | topis | news | seoul_press
    source_url: str
    published_at: datetime
    fetched_at: datetime
    event_date: date | None
    fields: dict[str, str]

    def to_json(self) -> dict[str, object]:
        return {
            "sentence_id": self.sentence_id,
            "notice_id": self.notice_id,
            "text": self.text,
            "context_prev": self.context_prev,
            "context_next": self.context_next,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat(),
            "fetched_at": self.fetched_at.isoformat(timespec="seconds"),
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "fields": self.fields,
        }


def _cell(value: str | None) -> str:
    return " ".join((value or "").split())


def _with_context(texts: list[str], i: int) -> tuple[str | None, str | None]:
    prev = texts[i - 1] if i > 0 else None
    nxt = texts[i + 1] if i + 1 < len(texts) else None
    return prev, nxt


class SmpaPdfSource:
    """'오늘의 주요집회' PDF 폴더 → 문장. 파일당 표 하나, 머리글이 SMPA_HEADER와 다르면 실패한다."""

    def __init__(self, pdf_dir: Path, source_url: str = SMPA_BOARD_URL) -> None:
        self.pdf_dir = pdf_dir
        self.source_url = source_url

    def sentences(self) -> list[NoticeSentence]:
        out: list[NoticeSentence] = []
        for path in sorted(self.pdf_dir.glob("*.pdf")):
            out.extend(self.parse_file(path))
        return out

    def parse_file(self, path: Path) -> list[NoticeSentence]:
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, KST)  # 폴더에 넣은 시각
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            rows = [row for page in pdf.pages for table in page.extract_tables() for row in table]
        basis = SMPA_BASIS_RE.search(text)
        event = SMPA_DATE_RE.search(text)
        if not basis or not event:
            raise ValueError(f"{path.name}: '기준 작성' 또는 날짜 줄을 못 찾음")
        y, mo, d, hh, mm = (int(v) for v in basis.groups())
        published_at = datetime(y, mo, d, hh, mm, tzinfo=KST)
        event_date = date(*(int(v) for v in event.groups()))
        if not rows or tuple(_cell(c) for c in rows[0]) != SMPA_HEADER:
            raise ValueError(f"{path.name}: 표 머리글이 다름 — {rows[:1]}")
        body = [[_cell(c) for c in row] for row in rows[1:]]
        texts = [" ".join(c for c in row if c) for row in body]
        notice_id = f"smpa-{event_date:%Y%m%d}"
        out: list[NoticeSentence] = []
        for i, (row, sentence) in enumerate(zip(body, texts, strict=True)):
            prev, nxt = _with_context(texts, i)
            fields = dict(zip(SMPA_FIELDS, row, strict=True))
            fields["file"] = path.name
            out.append(
                NoticeSentence(
                    sentence_id=f"{notice_id}-r{i + 1:02d}",
                    notice_id=notice_id,
                    text=sentence,
                    context_prev=prev,
                    context_next=nxt,
                    source_type="smpa",
                    source_url=self.source_url,
                    published_at=published_at,
                    fetched_at=fetched_at,
                    event_date=event_date,
                    fields=fields,
                )
            )
        return out


def html_lines(body: str) -> list[str]:
    """TOPIS 본문(HTML) → 줄 목록. 블록 태그에서만 줄을 나누고 인라인 태그는 지운다."""
    unescaped = html.unescape(body).replace("\xa0", " ")
    with_breaks = _BLOCK_TAG_RE.sub("\n", unescaped)
    plain = html.unescape(_TAG_RE.sub("", with_breaks))
    return [line for line in (" ".join(raw.split()) for raw in plain.splitlines()) if line]


class TopisNoticeSource:
    """기록된 NoticeList xml 응답 → 문장. 호출·기록은 scripts/build_notices.py가 한다."""

    def __init__(
        self, responses: Iterable[tuple[str, datetime]], categories: Iterable[str] | None = None
    ):
        self.responses = list(responses)  # (xml 원문, called_at)
        self.categories = set(categories) if categories else None  # 예: {"통제안내", "버스안내"}

    def sentences(self) -> list[NoticeSentence]:
        out: list[NoticeSentence] = []
        seen: set[str] = set()
        for xml_text, called_at in self.responses:
            root = ET.fromstring(xml_text)
            code = root.findtext("RESULT/CODE")
            if code != "INFO-000":
                raise ValueError(f"NoticeList 응답 오류: {code} {root.findtext('RESULT/MESSAGE')}")
            for row in root.findall("row"):
                seq = row.findtext("bdwr_seq") or ""
                category = row.findtext("bdwr_div_nm") or ""
                if seq in seen or (self.categories and category not in self.categories):
                    continue
                seen.add(seq)
                out.extend(self._row_sentences(row, seq, category, called_at))
        return out

    def _row_sentences(
        self, row: ET.Element, seq: str, category: str, called_at: datetime
    ) -> list[NoticeSentence]:
        title = _cell(row.findtext("bdwr_ttl_nm"))
        created = row.findtext("create_date") or ""
        published_at = datetime.strptime(created, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        url = (row.findtext("url") or "").strip()
        lines = [title, *html_lines(row.findtext("bdwr_cts") or "")]
        notice_id = f"topis-{seq}"
        out: list[NoticeSentence] = []
        for i, line in enumerate(lines):
            prev, nxt = _with_context(lines, i)
            out.append(
                NoticeSentence(
                    sentence_id=f"{notice_id}-l{i:03d}",
                    notice_id=notice_id,
                    text=line,
                    context_prev=prev,
                    context_next=nxt,
                    source_type="topis",
                    source_url=url,
                    published_at=published_at,
                    fetched_at=called_at,
                    event_date=None,
                    fields={"title": title, "category": category, "seq": seq, "line": str(i)},
                )
            )
        return out
