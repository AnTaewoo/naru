"""IncidentIngestor — TOPIS 실시간 돌발(OA-13315 AccInfo) → ClosureCandidate (T6.1).

ARCHITECTURE AI 표·INTERFACE §1: 돌발은 링크 선(`line`), impact 는 늘 blocks.
- 집회(acc_dtype 10B02)만 후보로 만든다. 행사(10B01 축제·10B03 차 없는 거리)·공사·기타(버스
  무정차 등)·사고는 차만 막거나 보도 일이라 README impact 규칙상 none 이다. 2026-11-07 15:40
  기록에서 그래프 범위 안은 집회 8 · 차 없는 거리 2 · 축제 1 · 버스 무정차 2 · 시설물보수 3.
- "(인도)"처럼 보도 위 집회라고 적힌 것도 뺀다 (README: 보도·광장 집회는 none).
- 같은 링크·같은 시각은 한 후보로 묶고 근거는 돌발마다 하나씩. 후보 ID 는 가장 작은 acc_id.
- 선·이름은 TOPIS 링크(LinkBook — LinkVerInfo 꼭짓점·LinkInfo 도로명과 시작·끝 노드), 링크가
  없으면 돌발 좌표 점.
- 확신도 0.9, status_hint scheduled — 시작이 지나면 엔진이 topis_incident 근거로 confirmed.
  근거 at = 수신 시각 (INTERFACE §3.1 data_as_of 의 topis_incident).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from naru_ai.ingest.topis_api import KST, LinkBook, lnglat_5181, seoul_rows
from naru_contracts import (
    CandidateSummary,
    ClosureCandidate,
    ClosureType,
    Evidence,
    EvidenceKind,
    Impact,
    LineGeom,
    PointGeom,
    Source,
    Status,
    SummarySegment,
    Window,
)

log = logging.getLogger(__name__)

RALLY = "10B02"  # AccSubCode 10B02 집회 (MANIFEST recorded/incident)
CONFIDENCE = 0.9  # TOPIS 가 실제로 등록한 통제 — 규칙서의 TOPIS 통제 공지(시간·구간 다 있음)와 같게
SIDEWALK = re.compile(r"\((?:인도|보도)\)")


@dataclass(frozen=True)
class Incident:
    acc_id: str
    acc_type: str
    acc_dtype: str
    link_id: str
    start: datetime | None
    end: datetime | None
    x: float  # EPSG:5181
    y: float
    info: str


def _kst(date: str, time: str) -> datetime | None:
    """YYYYMMDD + HHMM 또는 HHMMSS (AccInfo 는 둘 다 온다 — 1444 · 150000)."""
    date, time = date.strip(), time.strip()
    if len(date) != 8 or len(time) not in (4, 6):
        return None
    fmt = "%Y%m%d%H%M%S" if len(time) == 6 else "%Y%m%d%H%M"
    return datetime.strptime(date + time, fmt).replace(tzinfo=KST)


def parse_accinfo(raw: str) -> list[Incident]:
    out: list[Incident] = []
    for r in seoul_rows(raw, "AccInfo"):
        out.append(
            Incident(
                acc_id=r.get("acc_id", ""),
                acc_type=r.get("acc_type", ""),
                acc_dtype=r.get("acc_dtype", ""),
                link_id=r.get("link_id", ""),
                start=_kst(r.get("occr_date", ""), r.get("occr_time", "")),
                end=_kst(r.get("exp_clr_date", ""), r.get("exp_clr_time", "")),
                x=float(r.get("grs80tm_x") or 0.0),
                y=float(r.get("grs80tm_y") or 0.0),
                info=r.get("acc_info", ""),
            )
        )
    return out


class IncidentIngestor:
    def __init__(self, links: LinkBook) -> None:
        self.links = links

    def build(
        self, incidents: Sequence[Incident], ref: str, received_at: datetime
    ) -> list[ClosureCandidate]:
        groups: dict[tuple[str, datetime | None, datetime | None], list[Incident]] = {}
        for i in incidents:
            if i.acc_dtype != RALLY or i.start is None:
                continue
            if SIDEWALK.search(i.info.splitlines()[0] if i.info else ""):
                log.info("sidewalk rally skipped", extra={"acc_id": i.acc_id})
                continue
            groups.setdefault((i.link_id, i.start, i.end), []).append(i)
        out = [self._candidate(g, ref, received_at) for g in groups.values()]
        return sorted(out, key=lambda c: c.candidate_id)

    def _candidate(
        self, group: list[Incident], ref: str, received_at: datetime
    ) -> ClosureCandidate:
        group = sorted(group, key=lambda i: int(i.acc_id))
        first = group[0]
        link = self.links.get(first.link_id)
        named = link is not None and link.start_name and link.end_name
        if link is not None and named:
            section = f"{link.road_name or ''} {link.start_name}→{link.end_name}".strip()
        else:
            section = (first.info.splitlines() or [""])[0][:60]
        geometry: LineGeom | PointGeom = (
            LineGeom(coordinates=list(link.coords))
            if link is not None
            else PointGeom(coordinates=lnglat_5181(first.x, first.y))
        )
        summary = None
        if link is not None and named:
            summary = CandidateSummary(
                segments=[SummarySegment(from_=link.start_name, to=link.end_name)],
                points=[],
                reported_people=None,
                roads=[link.road_name] if link.road_name else [],
            )
        evidence = [
            Evidence(
                kind=EvidenceKind.topis_incident,
                ref=f"{ref}#{i.acc_id}",
                at=received_at,
                detail={"acc_id": i.acc_id, "link_id": i.link_id, "section": section},
            )
            for i in group
        ]
        return ClosureCandidate(
            candidate_id=f"incident-{first.acc_id}",
            source=Source.incident,
            type=ClosureType.rally,
            status_hint=Status.scheduled,
            impact=Impact.blocks,
            geometry=geometry,
            window=Window(start=first.start, end=first.end),
            confidence=CONFIDENCE,
            evidence=evidence,
            notice_ref=None,
            review_required=False,
            summary=summary,
        )
