"""TOPIS 통제·버스 공지 — 열린데이터광장 NoticeList(OA-22861) → 공지 한 건 = 문장 하나 (T6.4).

- 원문: live 면 SeoulOpenApi 로 최신 글을 불러 `data/recorded/topis_notice/<ts>_NoticeList.json` 에
  남긴다(같은 내용이면 마지막 기록을 가리킨다). recorded 면 지정 파일, 없으면 가장 최근 기록.
  TOPIS 게시판(openNoticeList.do)과 같은 글이고 최신 글도 같다(2026-11-08 둘 다 6301) — 웹은
  긁지 않는다. 키로 쓰는 공개 API 라 주기는 ADR-013 H.
- 단위: 규칙서 §1.3 "공지 한 건" — 제목과 본문 줄을 줄바꿈으로 이은 글 하나가 문장 하나.
  줄마다 나누면(T0.5 TopisNoticeSource, 평가용) 통제일시와 통제구간이 다른 줄에 있어 묶이지
  않는다(예: 6288 "통제일시 : 2026.11.8.(일) 07:00 ~ 10:30" / "통제구간 : 서울광장~종로~…").
- sentence_id = topis-<글 번호>-u<고친 시각 YYYYMMDDHHMM> — 글이 고쳐지면 다시 파싱한다.
- 어느 글: 분류 통제안내·버스안내(빌더와 같다), 제목의 날짜(M/D) 중 가장 늦은 날이 오늘 이후,
  날짜가 없으면 3일 안에 게시·수정된 글.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

from naru_ai.ingest.topis_api import KST, FeedRecord, SeoulOpenApi
from naru_ai.notice.source import TOPIS_SERVICE, NoticeSentence, html_lines

CATEGORIES = ("통제안내", "버스안내")  # scripts/build_notices.py TOPIS_CATEGORIES 와 같다
RECENT = timedelta(days=3)  # 제목에 날짜가 없는 글
TITLE_DATE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})")


def _when(text: str) -> datetime:
    return datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)


def title_dates(title: str, today: date) -> list[date]:
    """제목의 M/D — 연도는 오늘 기준(반년 넘게 앞서거나 뒤면 해를 넘긴 것으로 본다)."""
    out: list[date] = []
    for m, d in TITLE_DATE.findall(title):
        month, day = int(m), int(d)
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        year = today.year + (1 if month < today.month - 6 else -1 if month > today.month + 6 else 0)
        try:
            out.append(date(year, month, day))
        except ValueError:
            continue  # 11/31 같은 없는 날
    return out


def post_sentences(raw: str, called_at: datetime, now: datetime) -> list[NoticeSentence]:
    """NoticeList xml → 지금 볼 글마다 문장 하나."""
    root = ET.fromstring(raw)
    code = root.findtext("RESULT/CODE")
    if code != "INFO-000":
        raise ValueError(f"NoticeList 응답 오류: {code} {root.findtext('RESULT/MESSAGE')}")
    today = now.astimezone(KST).date()
    out: list[NoticeSentence] = []
    for row in root.findall("row"):
        category = row.findtext("bdwr_div_nm") or ""
        if category not in CATEGORIES:
            continue
        seq = row.findtext("bdwr_seq") or ""
        title = " ".join((row.findtext("bdwr_ttl_nm") or "").split())
        created = _when(row.findtext("create_date") or "")
        updated = _when(row.findtext("update_date") or row.findtext("create_date") or "")
        dates = title_dates(title, today)
        if dates and max(dates) < today:
            continue
        if not dates and now - max(created, updated) > RECENT:
            continue
        body = html_lines(row.findtext("bdwr_cts") or "")
        out.append(
            NoticeSentence(
                sentence_id=f"topis-{seq}-u{updated:%Y%m%d%H%M}",
                notice_id=f"topis-{seq}",
                text="\n".join([title, *body]),
                context_prev=None,
                context_next=None,
                source_type="topis",
                source_url=(row.findtext("url") or "").strip(),
                published_at=created,
                fetched_at=called_at,
                event_date=None,
                fields={"title": title, "category": category, "seq": seq, "unit": "post"},
            )
        )
    return out


class TopisNotices:
    """TOPIS 공지 원문 — live(NoticeList 호출 + 기록) 또는 기록(지정 파일, 없으면 가장 최근)."""

    def __init__(
        self,
        recorded_dir: Path,
        api: SeoulOpenApi | None = None,
        pinned: Path | None = None,
        size: int = 50,
    ) -> None:
        self.folder = recorded_dir / "topis_notice"
        self.api = api
        self.pinned = pinned
        self.size = size

    def fetch(self) -> FeedRecord:
        if self.api is not None:
            return self.api.call("topis_notice", TOPIS_SERVICE, 1, self.size, dedupe=True)
        path = self.pinned or max(self.folder.glob("*.json"), default=None)
        if path is None:
            raise FileNotFoundError("TOPIS 공지 기록 없음 — scripts/build_notices.py --topis")
        rec = json.loads(path.read_text("utf-8"))
        return FeedRecord(path, str(rec["raw"]), datetime.fromisoformat(str(rec["called_at"])))
