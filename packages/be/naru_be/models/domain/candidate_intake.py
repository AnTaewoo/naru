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
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
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
        for raw in batch.candidates:
            candidate = self.promote_unknown(raw)
            ids = self.crosswalk_ids(candidate)
            candidate = self.link_incidents(candidate, ids)
            states = self.engine.apply(candidate, ids, at=at)
            meta = CandidateMeta.of(candidate)
            updated += self.repo.upsert_many(states, candidate.candidate_id, meta)
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

    def crosswalk_ids(self, c: ClosureCandidate) -> set[str]:
        g = c.geometry
        if isinstance(g, PointGeom):
            if c.impact is Impact.unknown:
                return set()  # 승격 안 된 unknown: 표시만 (zone_scheduled), 횡단보도 상태 없음
            return self.index.from_point(*g.coordinates)
        if isinstance(g, LineGeom):
            return self.index.from_line(g.coordinates)
        if isinstance(g, SegmentGeom):
            return self.index.from_segment(g)
        assert isinstance(g, ZoneGeom)
        log.warning("zone candidate skipped", extra={"candidate_id": c.candidate_id})
        return set()

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
