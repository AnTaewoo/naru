"""BusIntake — 버스 위치 배치를 저장한다 (T6.2, ADR-013 D). 판단은 T6.3(BusCorrection) 몫."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from naru_be.models.repositories.bus_repository import BusRepository
from naru_contracts import BusPositionBatch

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BusIntakeResult:
    batch_id: str
    accepted: int  # 새로 저장한 위치 수


class BusIntake:
    def __init__(self, repo: BusRepository) -> None:
        self.repo = repo

    def accept(self, batch: BusPositionBatch) -> BusIntakeResult:
        accepted = self.repo.save(batch)
        log.info(
            "bus batch",
            extra={
                "batch_id": batch.batch_id,
                "route_id": batch.route_id,
                "positions": len(batch.positions),
                "accepted": accepted,
            },
        )
        return BusIntakeResult(batch.batch_id, accepted)
