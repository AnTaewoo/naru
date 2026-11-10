"""PushDesk — 알림 구독·관심 지역 (INTERFACE §9, ADR-014 C, T7.8). Flask 를 모른다.

public_key(): .env VAPID 개인키(PEM 또는 raw)에서 브라우저 applicationServerKey(base64url 공개점).
키가 없으면 PushUnavailableError(503). subscribe(): 같은 endpoint 면 id 그대로 다시 켠다.
areas(): 만료된 last_seen 은 읽을 때 지운다. add_area(): saved 는 구독당 watch_saved_max 개,
last_seen 은 하나(바꿔 끼움) — 150 m 격자로 반올림(EPSG:5179)·3시간 뒤 만료. 발송·매칭은 T7.9.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid, b64urlencode
from pyproj import Transformer

from naru_be.config import Settings
from naru_be.errors import InvalidQueryError, NotFoundError, PushUnavailableError
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


class PushDesk:
    def __init__(self, repo: PushRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

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
