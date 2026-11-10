"""BE ↔ FE: 알림 구독·관심 지역 (INTERFACE §9, ADR-014 C, T7.8).

계정 없이 구독 endpoint(푸시 서비스 URL)가 손잡이다. GET·DELETE 는 endpoint 를 헤더
X-Push-Endpoint 로(주소·접근 로그에 안 남게), POST 는 본문으로. 좌표는 관심 지역 중심 [lng, lat].
"""

import math
import re
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from naru_contracts._base import Contract
from naru_contracts.closure import _require_offset

B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
WATCH_RADII_M = (300, 500, 1000)  # 관심 지역 반경 (ADR-014 C)
WatchKind = Literal["saved", "last_seen"]


def _endpoint(v: str) -> str:
    if not v.startswith("https://") or len(v) > 512:
        raise ValueError("endpoint 는 https 주소, 512자 안")
    return v


def _b64url(v: str) -> str:
    if not B64URL.fullmatch(v):
        raise ValueError("base64url 이 아니다")
    return v


class PushKeys(Contract):
    p256dh: str = Field(min_length=87, max_length=88)  # P-256 공개점 65바이트
    auth: str = Field(min_length=22, max_length=24)  # 16바이트

    _b64 = field_validator("p256dh", "auth")(_b64url)


class PushSubscription(Contract):
    """브라우저 PushSubscription.toJSON() 그대로."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    endpoint: str
    keys: PushKeys
    expiration_time: int | None = Field(default=None, alias="expirationTime")

    _ep = field_validator("endpoint")(_endpoint)


class SubscribeResponse(Contract):
    id: int
    active: bool
    created_at: datetime

    _tz = field_validator("created_at")(_require_offset)


class UnsubscribeRequest(Contract):
    endpoint: str

    _ep = field_validator("endpoint")(_endpoint)


class VapidPublicKey(Contract):
    public_key: str = Field(
        min_length=87, max_length=88
    )  # base64url, 브라우저 applicationServerKey

    _b64 = field_validator("public_key")(_b64url)


class WatchAreaRequest(Contract):
    endpoint: str
    kind: WatchKind
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    radius_m: int = 500

    _ep = field_validator("endpoint")(_endpoint)

    @field_validator("lng", "lat")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("숫자가 아니다")
        return v

    @field_validator("radius_m")
    @classmethod
    def _radius(cls, v: int) -> int:
        if v not in WATCH_RADII_M:
            raise ValueError(f"radius_m 은 {WATCH_RADII_M} 중 하나")
        return v


class WatchArea(Contract):
    id: int
    kind: WatchKind
    lng: float  # last_seen 은 150 m 격자로 반올림한 점
    lat: float
    radius_m: int
    created_at: datetime
    expires_at: datetime | None  # last_seen 만 (3시간)

    _tz = field_validator("created_at", "expires_at")(_require_offset)


class WatchAreasResponse(Contract):
    areas: list[WatchArea]
