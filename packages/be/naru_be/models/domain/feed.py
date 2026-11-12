"""FeedDesk — 공개 GeoJSON 피드의 Model (INTERFACE §3.3, T7.17). Flask 를 모른다.

collection_at(at): 그 시각 걸린 사건(Repository.events 창 = 그 시각)·그 사건들의 횡단보도 상태
(그 시각으로 다시 판정)·행진 프로필(경로 위 횡단보도 P, ADR-015)을 모은다 — /closures·
/closures/events·/route 와 같은 조회와 판정. 분 단위로 내린 시각을 열쇠로 feed_cache_s 동안
캐시(gunicorn 워커마다).
RateLimiter: 열쇠(IP)마다 토큰 통 — 분당 feed_rate_per_min 회. 워커마다 따로 센다(2 워커면 두 배).
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime

from naru_be.config import Settings
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.closure_events import EventWindow, event_id
from naru_be.models.domain.crosswalk_index import CrosswalkIndex
from naru_be.models.domain.march import MarchProfile, p_at
from naru_be.models.domain.types import KST, LngLat
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_contracts import ClosureEvent, ClosureState, Status

ATTRIBUTION = (
    "나루(naru.antaewoo.com) — 서울 열린데이터광장(횡단보도 OA-23081, TOPIS 돌발 OA-13315, "
    "공공누리 1유형)·서울경찰청 집회 공지·TOPIS 통제 공지·서울마라톤 공지를 읽어 만든 추정값. "
    "실제 통제와 다를 수 있다"
)


@dataclass(frozen=True)
class FeedCrosswalk:
    state: ClosureState  # status 는 at 기준
    event: ClosureEvent
    name: str | None  # 교차로명
    p: float | None  # 행진 경로 위면 그 시각 P


@dataclass(frozen=True)
class FeedResult:
    at: datetime
    generated_at: datetime
    events: list[ClosureEvent]  # 구역(area)이 있으면 Polygon 피처
    crosswalks: list[FeedCrosswalk]
    paths: dict[str, tuple[LngLat, ...]]  # 사건 id → 행진 경로


class RateLimiter:
    """토큰 통 — 열쇠마다 분당 rate 회, 통 크기 rate. 시각은 호출자가 준다(단조 초)."""

    def __init__(self, rate_per_min: int) -> None:
        self.rate = rate_per_min
        self._buckets: dict[str, tuple[float, float]] = {}  # key → (tokens, last)
        self._lock = threading.Lock()

    def allow(self, key: str, now_s: float) -> bool:
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.rate), now_s))
            tokens = min(float(self.rate), tokens + (now_s - last) * self.rate / 60.0)
            if tokens < 1.0:
                self._buckets[key] = (tokens, now_s)
                return False
            self._buckets[key] = (tokens - 1.0, now_s)
            if len(self._buckets) > 10_000:  # 오래된 열쇠 정리
                self._buckets = {k: v for k, v in self._buckets.items() if now_s - v[1] < 120}
            return True


class FeedDesk:
    def __init__(
        self,
        repo: ClosureRepository,
        engine: ClosureEngine,
        index: CrosswalkIndex,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.engine = engine
        self.index = index
        self.settings = settings
        self.limiter = RateLimiter(settings.feed_rate_per_min)
        self._cache: OrderedDict[str, tuple[float, FeedResult]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def floor_minute(at: datetime) -> datetime:
        return at.astimezone(KST).replace(second=0, microsecond=0)

    def collection_at(self, at: datetime) -> FeedResult:
        key = self.floor_minute(at).isoformat()
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and now - hit[0] < self.settings.feed_cache_s:
                return hit[1]
        result = self._build(self.floor_minute(at))
        with self._lock:
            self._cache[key] = (now, result)
            while len(self._cache) > self.settings.feed_cache_max:
                self._cache.popitem(last=False)
        return result

    def _build(self, at: datetime) -> FeedResult:
        window = EventWindow(at, at, at)
        events = self.repo.events(
            None,
            self.index.district_of,
            status_of=lambda st: self.engine.status_of_state(st, at),
            window=window,
        )
        by_id = {e.id: e for e in events}
        keys = {(e.reason, e.window.start, e.window.end): e.id for e in events}
        marches = self.repo.marches_of(list(keys))
        states = self.engine.restate(self.repo.states_of_events(list(by_id)), at)
        seen: dict[tuple[str, str], FeedCrosswalk] = {}
        for st in states:
            key = (st.reason, st.window.start, st.window.end)
            eid = keys.get(key) or event_id(st.reason, st.window.start, st.window.end)
            event = by_id.get(eid)
            if event is None:
                continue
            p = self._p(st, marches.get(key), at)
            cw = self.index.find(st.crosswalk_id)
            item = FeedCrosswalk(st, event, cw.intersection_name if cw else None, p)
            prev = seen.get((eid, st.crosswalk_id))
            if prev is None or _worse(st.status, prev.state.status):
                seen[(eid, st.crosswalk_id)] = item
        paths = {keys[k]: m.path for k, m in marches.items() if k in keys}
        return FeedResult(at, datetime.now(UTC).astimezone(KST), events, list(seen.values()), paths)

    def _p(self, st: ClosureState, march: MarchProfile | None, at: datetime) -> float | None:
        if march is None or st.crosswalk_id not in march.s:
            return None
        start, end = st.window.start, st.window.end
        if start is None or end is None:
            return None
        return p_at(
            march, start, end, st.crosswalk_id, at, self.settings, st.status is Status.confirmed
        )


_SEVERITY = {Status.confirmed: 0, Status.scheduled: 1, Status.zone_scheduled: 2, Status.released: 3}


def _worse(a: Status, b: Status) -> bool:
    return _SEVERITY[a] < _SEVERITY[b]
