"""CandidateBuilder — ParsedNotice → ClosureCandidate (INTERFACE §1, ADR-008, T4.2c).

- impact none 은 후보 없음. blocks → Impact.blocks, unknown → Impact.unknown(confidence ≤ 0.65)
- segment: from·to 둘 다 풀리면 SegmentGeom(via 는 풀린 것만, road 는 사전에 있을 때 road_class),
  하나라도 못 풀면 풀린 쪽만 PointGeom. 틀린 선보다 빠진 점이 낫다. 끝점은 AREA 태그라도 교차로
  사전에 같은 이름이 있으면 그 교차로(Resolver.resolve_endpoint, T6.4 — TOPIS 의 '서울광장')
- points: 풀리면 PointGeom. toward 가 있고 풀리면 출발지 → toward SegmentGeom, confidence 0.65 상한
- confidence 는 파서의 규칙 값(규칙서 §3.8)에 위 상한만 적용. 0.7 미만이면 review_required
- 못 푼 정규형은 후보를 만들지 않는다 (추측 좌표 0)
- summary(ADR-012): item 의 구간·지점 이름(spans 정규 이름)·reported_people·roads 를 구조화
  칸 그대로. 좌표가 안 풀린 이름도 남는다. 같은 item 의 후보는 같은 summary. Claude 스키마는 그대로
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from naru_ai.notice.parser import ParsedItem, ParsedNotice
from naru_ai.notice.resolver import Resolver
from naru_contracts import (
    CandidateSummary,
    ClosureCandidate,
    ClosureType,
    Evidence,
    EvidenceKind,
    Impact,
    NoticeRef,
    PlacePoint,
    PointGeom,
    SegmentGeom,
    Source,
    Status,
    SummarySegment,
    Window,
)

log = logging.getLogger(__name__)
TOWARD_CONFIDENCE_CAP = 0.65  # ADR-008 toward_confidence_cap (BE config 와 같다)
UNKNOWN_CONFIDENCE_CAP = 0.65  # ADR-008 / naru_contracts.UNKNOWN_IMPACT_MAX_CONFIDENCE
REVIEW_CONFIDENCE = 0.7
KIND_TO_TYPE = {
    "march": ClosureType.march,
    "rally_point": ClosureType.rally,
    "rally_stretch": ClosureType.rally,
    "closure": ClosureType.event,
    "marathon": ClosureType.marathon,
    "unknown": ClosureType.event,
}
SENTENCES_REF = "data/raw/notices/sentences.jsonl"
# TOPIS 공지 글 버전(T6.4 topis-<번호>-u<고친 시각>) — 후보 ID 는 버전 없이(고친 글이 덮는다)
POST_VERSION = re.compile(r"-u\d{12}$")


@dataclass(frozen=True)
class _Base:
    """한 item 의 후보들이 공유하는 필드."""

    source: Source
    type: ClosureType
    impact: Impact
    window: Window
    evidence: Evidence
    notice_ref: NoticeRef
    approx: bool
    summary: CandidateSummary


class CandidateBuilder:
    def __init__(self, resolver: Resolver) -> None:
        self.resolver = resolver

    def build(self, parsed: ParsedNotice, ref: str = SENTENCES_REF) -> list[ClosureCandidate]:
        """ref = 근거가 가리킬 원문 (기본 sentences.jsonl, live TOPIS 공지는 그 NoticeList 기록)."""
        out: list[ClosureCandidate] = []
        for i, pi in enumerate(parsed.items, start=1):
            item = pi.item
            if item.impact == "none":
                continue
            window = _window(item.window.start, item.window.end)
            if window is None:
                log.warning("no window", extra={"sentence_id": parsed.envelope.sentence_id})
                continue
            hint = pi.area_hint()
            base = _Base(
                source=Source(parsed.envelope.source),
                type=KIND_TO_TYPE[item.kind],
                impact=Impact.blocks if item.impact == "blocks" else Impact.unknown,
                window=window,
                evidence=_evidence(parsed, ref),
                notice_ref=_notice_ref(parsed),
                approx=item.approx,
                summary=_summary(pi),
            )
            prefix = f"{candidate_stem(parsed.envelope.sentence_id)}-i{i}"
            for k, seg in enumerate(pi.segments, start=1):
                src = self.resolver.resolve_endpoint(seg.from_, pi.tag_of(seg.from_), hint)
                dst = self.resolver.resolve_endpoint(seg.to, pi.tag_of(seg.to), hint)
                if src is not None and dst is not None:
                    via = [
                        p
                        for name in seg.via
                        if (p := self.resolver.resolve(name, pi.tag_of(name), hint)) is not None
                    ]
                    road = self.resolver.resolve_road(seg.road) if seg.road else None
                    geom = SegmentGeom(
                        from_=src,
                        to=dst,
                        via=via,
                        road=road[0] if road else None,
                        road_class=road[1] if road else None,
                    )
                    out.append(self._candidate(f"{prefix}-seg{k}", geom, item.confidence, base))
                    continue
                for label, point in (("from", src), ("to", dst)):
                    if point is not None:
                        geom_pt = PointGeom(coordinates=(point.lng, point.lat))
                        cid = f"{prefix}-seg{k}-{label}"
                        out.append(self._candidate(cid, geom_pt, item.confidence, base))
            for k, pt in enumerate(item.points, start=1):
                place = self.resolver.resolve(pt.name, pi.tag_of(pt.name), hint)
                if place is None:
                    # extra 에 name 은 LogRecord 예약어라 KeyError — INFO 에서 build 가 죽었다(T6.4)
                    log.info("unresolved point", extra={"place": pt.name})
                    continue
                out.extend(self._point_candidates(f"{prefix}-pt{k}", place, pi, base))
        return out

    def _point_candidates(
        self, cid: str, place: PlacePoint, pi: ParsedItem, base: _Base
    ) -> list[ClosureCandidate]:
        item = pi.item
        if item.toward:
            target = self.resolver.resolve(item.toward, pi.tag_of(item.toward), pi.area_hint())
            if target is not None:
                geom = SegmentGeom(from_=place, to=target)
                conf = min(item.confidence, TOWARD_CONFIDENCE_CAP)
                return [self._candidate(cid, geom, conf, base, toward=item.toward)]
        geom_pt = PointGeom(coordinates=(place.lng, place.lat))
        return [self._candidate(cid, geom_pt, item.confidence, base, toward=item.toward)]

    @staticmethod
    def _candidate(
        cid: str,
        geometry: PointGeom | SegmentGeom,
        confidence: float,
        base: _Base,
        toward: str | None = None,
    ) -> ClosureCandidate:
        if base.impact is Impact.unknown:
            confidence = min(confidence, UNKNOWN_CONFIDENCE_CAP)
        confidence = round(confidence, 2)
        return ClosureCandidate(
            candidate_id=cid,
            source=base.source,
            type=base.type,
            status_hint=Status.scheduled,
            impact=base.impact,
            geometry=geometry,
            window=base.window,
            confidence=confidence,
            evidence=[base.evidence],
            notice_ref=base.notice_ref,
            toward=toward,
            approx=base.approx,
            review_required=confidence < REVIEW_CONFIDENCE,
            summary=base.summary,
        )


FULL_SCOPES = frozenset({"full", "one_side_full"})


def full_closure_stems(parsed: ParsedNotice) -> tuple[str, ...]:
    """차로 전부(양방향·한쪽 방향)를 막는 item 의 후보 ID 앞부분 — 버스 기록 대상(ADR-013 보류,
    태우 2026-11-09). 부분 차로(1개 차로 행진)는 버스가 그대로 지나가 대상이 아니다."""
    stem = candidate_stem(parsed.envelope.sentence_id)
    return tuple(
        f"{stem}-i{i}-"
        for i, pi in enumerate(parsed.items, start=1)
        if any(seg.lanes.scope in FULL_SCOPES for seg in pi.segments)
    )


def candidate_stem(sentence_id: str) -> str:
    """후보 ID 앞부분 — TOPIS 글 버전(-u<고친 시각>)을 뗀다. 고친 글이 같은 ID 로 덮는다 (T6.4)."""
    return POST_VERSION.sub("", sentence_id)


def _summary(pi: ParsedItem) -> CandidateSummary:
    """item 의 구조화 칸 (ADR-012) — 이름은 spans 정규 이름, roads 는 road_hints 와 구간 road."""
    name = pi.canonical_of
    roads: list[str] = []
    for r in [*pi.item.road_hints, *(s.road for s in pi.segments if s.road)]:
        if r and name(r) not in roads:
            roads.append(name(r))
    return CandidateSummary(
        segments=[
            SummarySegment(from_=name(s.from_), to=name(s.to), via=[name(v) for v in s.via])
            for s in pi.segments
        ],
        points=[name(p.name) for p in pi.item.points],
        reported_people=pi.item.reported_people,
        roads=roads,
    )


def _window(start: str | None, end: str | None) -> Window | None:
    s = _dt(start)
    e = _dt(end)
    if s is None and e is None:
        return None
    return Window(start=s, end=e)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"오프셋 없는 시각: {value}")
    return dt


def _evidence(parsed: ParsedNotice, ref: str = SENTENCES_REF) -> Evidence:
    env = parsed.envelope
    return Evidence(
        kind=EvidenceKind.notice,
        ref=f"{ref}#{env.sentence_id}",
        at=datetime.fromisoformat(env.published_at),
        detail={"model": parsed.model, "prompt_version": parsed.prompt_version},
    )


def _notice_ref(parsed: ParsedNotice) -> NoticeRef:
    env = parsed.envelope
    return NoticeRef(
        notice_id=env.notice_id,
        sentence_id=env.sentence_id,
        source_url=env.source_url,
        published_at=datetime.fromisoformat(env.published_at),
        excerpt=env.text,
    )
