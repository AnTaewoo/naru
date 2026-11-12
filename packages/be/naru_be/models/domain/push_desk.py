"""PushDesk — 알림 구독·관심 지역 (INTERFACE §9, ADR-014 C, T7.8). Flask 를 모른다.

public_key(): .env VAPID 개인키(PEM 또는 raw)에서 브라우저 applicationServerKey(base64url 공개점).
키가 없으면 PushUnavailableError(503). subscribe(): 같은 endpoint 면 id 그대로 다시 켠다.
areas(): 만료된 last_seen 은 읽을 때 지운다. add_area(): saved 는 구독당 watch_saved_max 개,
last_seen 은 하나(바꿔 끼움) — 150 m 격자로 반올림(EPSG:5179)·3시간 뒤 만료.
dispatch(now) (T7.9): 그 시각 창(진행 중 ~ push_horizon_h) 사건 x 관심 지역 →
push_dispatcher.plan_sends → push_sends 에 줄 세움 → 때가 된 것을 WebPushSender 로 보내고 상태
기록, 404·410 이면 구독을 끈다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid, b64urlencode
from pyproj import Transformer

from naru_be.config import Settings
from naru_be.errors import InvalidQueryError, NotFoundError, PushUnavailableError
from naru_be.models.domain.closure_engine import ClosureEngine
from naru_be.models.domain.closure_events import EventWindow
from naru_be.models.domain.push_dispatcher import WatchCircle, payload_of, plan_sends
from naru_be.models.domain.web_push import WebPushSender
from naru_be.models.repositories.closure_repository import ClosureRepository
from naru_be.models.repositories.push_repository import (
    PushRepository,
    SubscriptionRow,
    WatchAreaRow,
)
from naru_contracts import PushSubscription, WatchAreaRequest

_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
_5179_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def snap_to_grid(lng: float, lat: float, grid_m: float) -> tuple[float, float]:
    """점을 grid_m 격자(EPSG:5179)의 가운데로 — 마지막 위치를 정확히 남기지 않는다."""
    x, y = _4326_TO_5179.transform(lng, lat)
    gx = (round(x / grid_m - 0.5) + 0.5) * grid_m
    gy = (round(y / grid_m - 0.5) + 0.5) * grid_m
    out_lng, out_lat = _5179_TO_4326.transform(gx, gy)
    return round(float(out_lng), 6), round(float(out_lat), 6)


@dataclass(frozen=True)
class DispatchResult:
    at: datetime
    matched: int
    sent: int
    failed: int
    deactivated: int


class PushDesk:
    def __init__(
        self,
        repo: PushRepository,
        settings: Settings,
        closures: ClosureRepository | None = None,
        engine: ClosureEngine | None = None,
        sender: WebPushSender | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.closures = closures
        self.engine = engine
        self.sender = sender or WebPushSender(settings)

    def public_key(self) -> str:
        secret = self.settings.vapid_private_key.get_secret_value().strip()
        if not secret:
            raise PushUnavailableError("서버에 VAPID 키가 없다")
        # py_vapid: from_pem 은 PEM 글, from_string 은 raw/DER base64 (둘 다 .env 에 넣을 수 있다)
        vapid = (
            Vapid.from_pem(secret.encode())
            if secret.startswith("-----")
            else Vapid.from_string(secret)
        )
        raw = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        return str(b64urlencode(raw))

    def subscribe(self, sub: PushSubscription, now: datetime) -> SubscriptionRow:
        return self.repo.upsert_subscription(sub.endpoint, sub.keys.p256dh, sub.keys.auth, now)

    def unsubscribe(self, endpoint: str) -> None:
        self.repo.deactivate(endpoint)  # 없어도 조용히

    def _owner(self, endpoint: str) -> SubscriptionRow:
        found = self.repo.subscription(endpoint)
        if found is None or not found.active:
            raise NotFoundError("구독이 없다", "endpoint")
        return found

    def areas(self, endpoint: str, now: datetime) -> list[WatchAreaRow]:
        sub = self._owner(endpoint)
        self.repo.purge_expired(sub.id, now)
        return self.repo.areas(sub.id)

    def add_area(self, req: WatchAreaRequest, now: datetime) -> WatchAreaRow:
        sub = self._owner(req.endpoint)
        self.repo.purge_expired(sub.id, now)
        if req.kind == "last_seen":
            lng, lat = snap_to_grid(req.lng, req.lat, self.settings.watch_last_seen_grid_m)
            self.repo.delete_areas(sub.id, "last_seen")
            expires = now + timedelta(hours=self.settings.watch_last_seen_ttl_h)
            return self.repo.add_area(sub.id, "last_seen", lng, lat, req.radius_m, now, expires)
        saved = [a for a in self.repo.areas(sub.id) if a.kind == "saved"]
        if len(saved) >= self.settings.watch_saved_max:
            raise InvalidQueryError(
                f"저장 관심 지역은 {self.settings.watch_saved_max}개까지", "kind"
            )
        return self.repo.add_area(sub.id, "saved", req.lng, req.lat, req.radius_m, now, None)

    def remove_area(self, endpoint: str, area_id: int) -> None:
        sub = self._owner(endpoint)
        if self.repo.delete_area(sub.id, area_id) == 0:
            raise NotFoundError("관심 지역이 없다", "id")

    def dispatch(self, now: datetime) -> DispatchResult:
        """매칭 → 줄 세움 → 때가 된 것 발송 (워커가 60초마다). 사건은 그 시각 ~ push_horizon_h."""
        assert self.closures is not None and self.engine is not None, (
            "dispatch 에는 사건 저장소가 필요"
        )
        engine = self.engine
        window = EventWindow(now, now, now + timedelta(hours=self.settings.push_horizon_h))
        events = self.closures.events(
            None, None, status_of=lambda st: engine.status_of_state(st, now), window=window
        )
        subs = [
            (keys.id, [WatchCircle(a.lng, a.lat, a.radius_m) for a in areas])
            for keys, areas in self.repo.subscriptions_with_areas(now)
        ]
        planned = plan_sends(events, subs, self.repo.existing_sends(), now, self.settings)
        matched = self.repo.queue_sends(
            [(p.subscription_id, p.event_id, p.kind, p.due_at) for p in planned]
        )
        by_id = {e.id: e for e in events}
        sent = failed = 0
        gone: set[int] = set()
        for send, keys in self.repo.due_sends(now):
            event = by_id.get(send.event_id)
            if (
                event is None
            ):  # 줄 설 땐 있었는데 지금 창엔 없는 사건(지워졌거나 끝남) — 보내지 않고 닫는다
                self.repo.mark_sent(send.id, 0, now)
                continue
            status = self.sender.send(keys, payload_of(event, send.kind))
            self.repo.mark_sent(send.id, status, now)
            if 200 <= status < 300:
                sent += 1
            else:
                failed += 1
                if status in (404, 410):
                    self.repo.deactivate_id(keys.id)
                    gone.add(keys.id)
        return DispatchResult(now, matched, sent, failed, len(gone))
