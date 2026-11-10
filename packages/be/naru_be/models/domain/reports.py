"""ReportDesk — 통제 제보 (T7.15, INTERFACE §8). 기록만 — 경로·확신도·상태에 쓰지 않는다.

nearest(lng, lat)  지금 위치 → report_snap_m(100 m) 안 가장 가까운 횡단보도. 좌표는 여기서 끝난다
submit(req, now)   범위 안 횡단보도인지 → 같은 기기·횡단보도 간격(600초) → 저장(기기는 sha256)
recent(ids, m)     최근 m 분 제보 수 (blocked, open) — 통제 근거 "최근 1시간 제보 N건"
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from naru_be.config import Settings
from naru_be.errors import InvalidQueryError, TooManyReportsError
from naru_be.models.domain.crosswalk_index import Crosswalk, CrosswalkIndex
from naru_be.models.repositories.report_repository import ReportRepository, ReportRow
from naru_contracts import ReportRequest


@dataclass(frozen=True)
class NearestHit:
    crosswalk: Crosswalk
    distance_m: float


class ReportDesk:
    def __init__(self, index: CrosswalkIndex, repo: ReportRepository, settings: Settings) -> None:
        self.index = index
        self.repo = repo
        self.settings = settings

    def nearest(self, lng: float, lat: float) -> NearestHit | None:
        crosswalk, distance_m = self.index.nearest(lng, lat)
        if distance_m > self.settings.report_snap_m:
            return None
        return NearestHit(crosswalk, distance_m)

    def submit(self, req: ReportRequest, now: datetime | None = None) -> ReportRow:
        now = now or datetime.now(UTC)
        if self.index.find(req.crosswalk_id) is None:
            raise InvalidQueryError("crosswalk_id: 서비스 범위에 없는 횡단보도", "crosswalk_id")
        device_hash = hashlib.sha256(req.device.encode()).hexdigest()
        last = self.repo.last_at(device_hash, req.crosswalk_id)
        interval = timedelta(seconds=self.settings.report_min_interval_s)
        if last is not None and now - last < interval:
            raise TooManyReportsError(
                "같은 횡단보도는 잠시 뒤에 다시 제보할 수 있다", "crosswalk_id"
            )
        return self.repo.add(
            req.crosswalk_id, req.state, req.accuracy_m, req.source, device_hash, now
        )

    def recent(
        self, ids: Collection[str], minutes: int, now: datetime | None = None
    ) -> dict[str, tuple[int, int]]:
        now = now or datetime.now(UTC)
        return self.repo.recent_counts(ids, now - timedelta(minutes=minutes), now)
