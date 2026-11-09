"""TOPIS 교통통제 지도 — 예정 통제 (T7.3, ADR-014 B, T6.5 조사).

https://topis.seoul.go.kr/map/openControlMap.do 가 부르는 AJAX 둘을 웹 페이지 수집 규칙
(ADR-011 E — robots 허용 경로, 같은 곳 10분에 한 번, NaruBot, 원문 기록)으로 받는다:
- 목록 `POST /map/accMap/selectAccAllListASC.do {accDate: NOW, trafficdataAppyYn: Y}` — accId,
  accDtype(10B02 집회), accInfo, occrDt·clrDt("YYYY-MM-DD HH:MM" KST), linkId,
  accRoadYn(전체·부분 통제), ingYn(Y 통제 중·N 예정), posX·posY(EPSG:5181)
- 통제 도로 `POST /map/accMap/selectAccLinkList.do {accId, trafficdataAppyYn: Y}` — linkId,
  roadName, stNodeNm·edNodeNm, axisCd, linkSeq
한 번에 요청 하나 — 목록, 또는 통제 도로가 아직 없는 예정 집회 하나(번갈아). 원문은
recorded/topis_web/.

후보는 예정(N) 집회(10B02, "(인도)" 보도 집회 빼고)만. 경로 = 통제 도로 링크를 노드 이름(앞 링크
끝 = 다음 링크 시작)으로 이은 선, 꼭짓점은 OA-13311 LinkVerInfo(LinkBook). 링크 목록이 아직 없으면
대표 링크 하나, 그것도 없으면 점. 확신도 0.85·공지 근거(source topis) — 시작해 OA-13315 돌발이 오면
같은 횡단보도·겹치는 시각이라 T6.1 연결로 '통제 중'. 돌발 후보(incident-<acc_id>)와 ID 를 같이 쓰지
않는다: 돌발은 링크 하나라 시작 때 경로가 그 링크로 줄어든다.
"""

from __future__ import annotations

import itertools
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from naru_ai.ingest.incident import RALLY, SIDEWALK
from naru_ai.ingest.topis_api import KST, USER_AGENT, LinkBook, lnglat_5181
from naru_contracts import (
    CandidateSummary,
    ClosureCandidate,
    ClosureType,
    Evidence,
    EvidenceKind,
    Impact,
    LineGeom,
    NoticeRef,
    PointGeom,
    Source,
    Status,
    SummarySegment,
    Window,
)

log = logging.getLogger(__name__)

PAGE_URL = "https://topis.seoul.go.kr/map/openControlMap.do"
LIST_URL = "https://topis.seoul.go.kr/map/accMap/selectAccAllListASC.do"
LINKS_URL = "https://topis.seoul.go.kr/map/accMap/selectAccLinkList.do"
CONFIDENCE = 0.85  # 예정 단계는 공지처럼 — '통제 중'은 OA-13315 돌발이 와야 (ADR-014 B)
FULL = "전체 통제"


@dataclass(frozen=True)
class MapControl:
    acc_id: str
    dtype: str  # accDtype — 10B02 집회
    info: str
    start: datetime | None
    end: datetime | None
    link_id: str
    full: bool  # accRoadYn 전체 통제
    live: bool  # ingYn Y(통제 중)
    x: float  # EPSG:5181
    y: float


@dataclass(frozen=True)
class MapLink:
    link_id: str
    road: str
    start_name: str
    end_name: str
    axis: str
    seq: int


def _kst(value: str | None) -> datetime | None:
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=KST) if value else None


def parse_controls(raw: str) -> list[MapControl]:
    out = []
    for r in json.loads(raw).get("rows") or []:
        out.append(
            MapControl(
                acc_id=str(r["accId"]),
                dtype=str(r.get("accDtype") or ""),
                info=str(r.get("accInfo") or "").replace("\r\n", "\n").strip(),
                start=_kst(r.get("occrDt")),
                end=_kst(r.get("clrDt")),
                link_id=str(r.get("linkId") or ""),
                full=r.get("accRoadYn") == FULL,
                live=r.get("ingYn") == "Y",
                x=float(r["posX"]),
                y=float(r["posY"]),
            )
        )
    return out


def parse_links(raw: str) -> list[MapLink]:
    return [
        MapLink(
            str(r["linkId"]),
            str(r.get("roadName") or ""),
            str(r.get("stNodeNm") or ""),
            str(r.get("edNodeNm") or ""),
            str(r.get("axisCd") or ""),
            int(r.get("linkSeq") or 0),
        )
        for r in json.loads(raw).get("rows") or []
    ]


def chains(links: Sequence[MapLink]) -> list[list[MapLink]]:
    """노드 이름으로 잇는다 — 앞 링크 끝 = 다음 링크 시작. 다른 링크의 끝이 아닌 시작에서 출발하고,
    이어지지 않으면 따로. 남는 것(고리)은 하나씩."""
    ordered = sorted(links, key=lambda x: (x.axis, x.seq, x.link_id))
    by_start: dict[str, MapLink] = {}
    for link in ordered:
        by_start.setdefault(link.start_name, link)
    ends = {x.end_name for x in ordered}
    used: set[str] = set()
    out: list[list[MapLink]] = []
    for head in [x for x in ordered if x.start_name not in ends]:
        chain: list[MapLink] = []
        cur: MapLink | None = head
        while cur is not None and cur.link_id not in used:
            chain.append(cur)
            used.add(cur.link_id)
            cur = by_start.get(cur.end_name)
        if chain:
            out.append(chain)
    out.extend([x] for x in ordered if x.link_id not in used)
    return out


def next_request(last: str | None, pending: Sequence[str]) -> str:
    """이번 요청 — 직전이 목록이고 통제 도로가 없는 예정 집회가 있으면 그 통제 도로(acc_id),
    아니면 목록."""
    return pending[0] if last == "list" and pending else "list"


class TopisMapIngestor:
    def __init__(self, links: LinkBook) -> None:
        self.links = links

    @staticmethod
    def targets(controls: Sequence[MapControl]) -> list[MapControl]:
        """예정 집회 — 통제 중(Y)은 OA-13315 돌발이 맡는다."""
        out = []
        for c in controls:
            if c.live or c.dtype != RALLY or c.start is None:
                continue
            if SIDEWALK.search(c.info.splitlines()[0] if c.info else ""):
                log.info("sidewalk rally skipped", extra={"acc_id": c.acc_id})
                continue
            out.append(c)
        return out

    def _lines(self, chain: Sequence[MapLink]) -> list[list[tuple[float, float]]]:
        """한 줄의 링크 꼭짓점을 이어 붙인다 — 꼭짓점이 없는 링크에서 끊는다."""
        lines: list[list[tuple[float, float]]] = [[]]
        for link in chain:
            got = self.links.get(link.link_id)
            if got is None:
                lines.append([])
                continue
            pts = list(got.coords)
            if lines[-1] and pts and lines[-1][-1] == pts[0]:
                pts = pts[1:]
            lines[-1].extend(pts)
        return [ln for ln in lines if len(ln) >= 2]

    def build(
        self,
        controls: Sequence[MapControl],
        link_lists: Mapping[str, Sequence[MapLink]],
        ref: str,
        fetched_at: datetime,
    ) -> list[ClosureCandidate]:
        out: list[ClosureCandidate] = []
        for c in self.targets(controls):
            found = link_lists.get(c.acc_id)
            groups = chains(found) if found else []
            lines = [ln for g in groups for ln in self._lines(g)]
            if not lines and c.link_id:  # 통제 도로를 아직 못 받았으면 대표 링크
                one = self.links.get(c.link_id)
                lines = [list(one.coords)] if one is not None else []
            geoms: list[LineGeom | PointGeom] = [LineGeom(coordinates=ln) for ln in lines] or [
                PointGeom(coordinates=lnglat_5181(c.x, c.y))
            ]
            out.extend(self._candidates(c, geoms, groups, ref, fetched_at))
        return out

    @staticmethod
    def _candidates(
        c: MapControl,
        geoms: Sequence[LineGeom | PointGeom],
        groups: Sequence[Sequence[MapLink]],
        ref: str,
        fetched_at: datetime,
    ) -> list[ClosureCandidate]:
        roads: list[str] = []
        for link in (x for g in groups for x in g):
            if link.road and link.road not in roads:
                roads.append(link.road)
        segments = [
            SummarySegment(
                from_=g[0].start_name,
                to=g[-1].end_name,
                via=[x.end_name for x, y in itertools.pairwise(g) if x.road != y.road],
            )
            for g in groups
        ]
        evidence = Evidence(
            kind=EvidenceKind.notice,
            ref=f"{ref}#acc-{c.acc_id}",
            at=fetched_at,
            detail={"feed": "topis_map", "acc_id": c.acc_id, "full": c.full},
        )
        notice = NoticeRef(
            notice_id=f"topismap-{c.acc_id}",
            sentence_id=f"topismap-{c.acc_id}",
            source_url=PAGE_URL,
            published_at=fetched_at,
            excerpt=c.info,
        )
        return [
            ClosureCandidate(
                candidate_id=f"topismap-{c.acc_id}-{k}",
                source=Source.topis,
                type=ClosureType.march if "행진" in c.info else ClosureType.rally,
                status_hint=Status.scheduled,
                impact=Impact.blocks,
                geometry=geom,
                window=Window(start=c.start, end=c.end),
                confidence=CONFIDENCE,
                evidence=[evidence],
                notice_ref=notice,
                review_required=False,
                summary=CandidateSummary(segments=segments, points=[], roads=roads),
            )
            for k, geom in enumerate(geoms)
        ]


class TopisMapFeed:
    """목록·통제 도로 원문 — live(요청 하나 + 기록) 또는 기록(목록은 지정 파일, 없으면 최근)."""

    def __init__(
        self,
        recorded_dir: Path,
        live: bool = False,
        pinned: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.root = recorded_dir / "topis_web"
        self.live = live
        self.pinned = pinned
        self._client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})
        self._last: str | None = None

    def controls(self) -> tuple[list[MapControl], str, datetime] | None:
        """가장 최근 목록 — (통제, 원문 경로, 받은 시각). 기록이 없으면 None."""
        path = self.pinned
        if path is None:
            files = sorted(self.root.glob("*_selectAccAllListASC.json"))
            if not files:
                return None
            path = files[-1]
        rec = json.loads(path.read_text("utf-8"))
        return parse_controls(rec["raw"]), path.as_posix(), datetime.fromisoformat(rec["called_at"])

    def links_of(self, acc_id: str) -> list[MapLink] | None:
        files = sorted(self.root.glob(f"*_selectAccLinkList_{acc_id}.json"))
        return parse_links(json.loads(files[-1].read_text("utf-8"))["raw"]) if files else None

    def step(self, now: datetime, pending: Sequence[str]) -> None:
        """live 면 이번 요청 하나(next_request) — 같은 곳은 워커 소스 주기(10분)에 한 번."""
        if not self.live:
            return
        which = next_request(self._last, pending)
        if which == "list":
            self._post(
                LIST_URL, {"accDate": "NOW", "trafficdataAppyYn": "Y"}, "selectAccAllListASC", now
            )
        else:
            body = {"accId": which, "trafficdataAppyYn": "Y"}
            self._post(LINKS_URL, body, f"selectAccLinkList_{which}", now)
        self._last = "list" if which == "list" else "links"

    def _post(self, url: str, body: dict[str, str], name: str, now: datetime) -> Path:
        called = now.astimezone(KST)
        r = self._client.post(url, data=body)
        r.raise_for_status()
        rec = {
            "api": "topis_web",
            "endpoint": url,
            "params": {"method": "POST", "body": body},
            "called_at": called.isoformat(timespec="seconds"),
            "status": r.status_code,
            "content_type": r.headers.get("content-type"),
            "raw": r.text,
        }
        path = self.root / f"{called:%Y%m%dT%H%M%S}_{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8")
        log.info("topis map", extra={"request": name, "status": r.status_code})
        return path
