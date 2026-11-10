"""CandidateIntake — 후보 배치 → CrosswalkIndex(kind 별) → ClosureEngine → Repository (T3.4, §1.1).

batch_id 멱등: 이미 처리한 배치면 저장된 결과를 그대로 돌려주고 아무것도 안 한다.
geometry: point → from_point(30 m) · line → from_line(15 m) · segment → from_segment(RoadGraph
최단경로 + 등급별 버퍼) · zone → 횡단보도 상태 없음(ZoneMatcher v1 뒤, 로그만).
impact unknown 인 point 는 도로 링크 30 m 안이면 blocks 로 승격(evidence detail.rule
unknown_near_road, ADR-008). 승격해도 confidence 는 그대로라 review_required 는 안 풀린다.
상태 판정 시각은 적재 시각(지금).
돌발(source incident)과 공지(smpa·topis·news·seoul_press)가 같은 횡단보도·겹치는 시각이면 공지 후보
전체에 그 돌발의 topis_incident 근거를 붙인다 — 어느 쪽이 먼저 와도 (T6.1, README '실제 근거').
같은 배치를 다시 받으면 받은 시각만 새로 한다(돌발 수신 시각 = data_as_of).
행진(T7.16, ADR-015 B): 구간·선 후보의 경로 선을 버리지 않고 사건마다 march_profile 로 모아 사건
행에 남긴다 — 대상이 아니면 null.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime

import shapely

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.closure_events import event_id
from naru_be.models.domain.crosswalk_index import CrosswalkIndex, road_class_of
from naru_be.models.domain.event_area import event_area
from naru_be.models.domain.march import MarchPart, march_profile
from naru_be.models.domain.road_graph import RoadGraph
from naru_be.models.domain.types import CandidateMeta, IntakeResult
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_contracts import (
    CandidateBatch,
    ClosureCandidate,
    Evidence,
    Impact,
    LineGeom,
    PointGeom,
    SegmentGeom,
    Source,
    ZoneGeom,
)

log = logging.getLogger(__name__)
NOTICE_SOURCES = frozenset(
    s.value for s in (Source.smpa, Source.topis, Source.news, Source.seoul_press)
)


class CandidateIntake:
    def __init__(
        self,
        index: CrosswalkIndex,
        engine: ClosureEngine,
        repo: ClosureRepository,
        road_graph: RoadGraph,
        settings: Settings | None = None,
    ) -> None:
        self.index = index
        self.engine = engine
        self.repo = repo
        self.road_graph = road_graph
        self.settings = settings or Settings()

    def accept(self, batch: CandidateBatch) -> IntakeResult:
        done = self.repo.batch_result(batch.batch_id)
        if done is not None:
            self.repo.touch_batch(batch.batch_id)
            log.info("batch duplicate", extra={"batch_id": batch.batch_id})
            return done
        at = datetime.now(UTC)
        accepted = review = updated = 0
        shapes: dict[tuple[str, datetime | None, datetime | None], list[shapely.Geometry]] = {}
        grouped: dict[tuple[str, datetime | None, datetime | None], list[ClosureCandidate]] = {}
        parts: dict[str, MarchPart] = {}
        for raw in batch.candidates:
            candidate = self.promote_unknown(raw)
            ids, shape, part = self.selection(candidate)
            candidate = self.link_incidents(candidate, ids)
            states = self.engine.apply(candidate, ids, at=at)
            meta = CandidateMeta.of(candidate)
            updated += self.repo.upsert_many(states, candidate.candidate_id, meta)
            if states and shape is not None:  # 사건 = (reason, 시작, 끝) — 후보의 상태는 다 같다
                key = (states[0].reason, states[0].window.start, states[0].window.end)
                shapes.setdefault(key, []).append(shape)
                grouped.setdefault(key, []).append(candidate)
                if part is not None:
                    parts[candidate.candidate_id] = part
            if candidate.source is Source.incident and ids:
                window, _ = self.engine.effective_window(candidate)
                linked = self.repo.attach(ids, window, NOTICE_SOURCES, list(candidate.evidence))
                if linked:
                    log.info(
                        "incident linked",
                        extra={"candidate_id": candidate.candidate_id, "notices": linked},
                    )
            accepted += 1
            review += int(candidate.review_required)
        # 사건 구역 (T7.2) — 한 사건의 후보는 한 배치에서 온다(같은 문장·같은 돌발 묶음):
        # 배치마다 다시 만든다
        for (reason, start, end), pieces in shapes.items():
            eid = event_id(reason, start, end)
            cands = grouped[(reason, start, end)]
            own = {c.candidate_id: parts[c.candidate_id] for c in cands if c.candidate_id in parts}
            march = march_profile(cands, own, self.index, self.settings)  # 대상 아니면 None
            self.repo.save_event_area(eid, reason, start, end, event_area(pieces), march)
        result = IntakeResult(batch.batch_id, accepted, review, updated)
        self.repo.save_batch(result, batch.producer, batch.produced_at)
        log.info(
            "batch accepted",
            extra={"batch_id": batch.batch_id, "accepted": accepted, "crosswalks": updated},
        )
        return result

    def link_incidents(self, c: ClosureCandidate, ids: set[str]) -> ClosureCandidate:
        """공지 후보에 이미 저장된 돌발(같은 횡단보도·겹치는 시각) 근거를 더한다 (T6.1)."""
        if c.source.value not in NOTICE_SOURCES or not ids:
            return c
        window, _ = self.engine.effective_window(c)
        found = self.repo.linked_evidence(ids, window, Source.incident.value)
        refs = {e.ref for e in c.evidence}
        add = [e for e in found if e.ref not in refs]
        return c.model_copy(update={"evidence": [*c.evidence, *add]}) if add else c

    def selection(
        self, c: ClosureCandidate
    ) -> tuple[set[str], shapely.Geometry | None, MarchPart | None]:
        """후보 → (횡단보도, 고른 모양 EPSG:5179, 경로 선). 모양은 사건 구역(T7.2)이, 선은 행진
        프로필(T7.16)이 다시 쓴다 — 경로는 한 번만 계산한다."""
        g = c.geometry
        part: MarchPart | None = None
        if isinstance(g, PointGeom):
            if c.impact is Impact.unknown:
                return set(), None, None  # 승격 안 된 unknown: 표시만, 횡단보도 상태 없음
            shape = self.index.area_of_point(*g.coordinates)
        elif isinstance(g, LineGeom):
            line = self.index.line_of(g.coordinates)
            shape = line.buffer(self.settings.line_buffer_m)
            roads = tuple(c.summary.roads) if c.summary else ()
            part = MarchPart(c.candidate_id, line, frozenset(), roads, None)
        elif isinstance(g, SegmentGeom):
            line, path = self.index.line_of_segment(g)
            shape = line.buffer(self.index.buffer_of_segment(g))
            cls = g.road_class or road_class_of(g.road)
            part = MarchPart(
                c.candidate_id, line, frozenset(), path.roads, cls.value if cls else None
            )
        else:
            assert isinstance(g, ZoneGeom)
            log.warning("zone candidate skipped", extra={"candidate_id": c.candidate_id})
            return set(), None, None
        ids = self.index.within(shape)
        if part is not None:
            part = replace(part, crosswalk_ids=frozenset(ids))
        return ids, shape, part

    def promote_unknown(self, c: ClosureCandidate) -> ClosureCandidate:
        """impact unknown 인 지점이 도로 링크 30 m 안이면 blocks 로 (ADR-008 §9.2-12)."""
        if c.impact is not Impact.unknown or not isinstance(c.geometry, PointGeom):
            return c
        lng, lat = c.geometry.coordinates
        dist = self.road_graph.nearest_link_distance_m(lng, lat)
        if dist > self.settings.unknown_impact_road_m:
            return c
        base = c.evidence[0]
        note = Evidence(
            kind=base.kind,
            ref=base.ref,
            at=c.window.start or base.at,
            detail={"rule": "unknown_near_road", "road_distance_m": round(dist, 1)},
        )
        return c.model_copy(update={"impact": Impact.blocks, "evidence": [*c.evidence, note]})
