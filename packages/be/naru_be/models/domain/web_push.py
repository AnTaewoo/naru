"""WebPushSender — pywebpush 로 실제 푸시 서비스에 보낸다 (ADR-014 C·D, T7.9). Flask·DB 를 모른다.

VAPID 개인키(.env, PEM 또는 raw)·subject(mailto:) 로 서명, aes128gcm 암호화는 pywebpush. 응답 상태만
돌려준다 — 2xx 성공, 404·410 은 구독이 사라진 것(PushDesk 가 끈다). 가짜 push 서버는 없다 —
테스트는 헤드리스 Chrome 이 실제 FCM 에 만든 구독으로(recorded/push).
"""

from __future__ import annotations

import json
import logging

from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from naru_be.config import Settings
from naru_be.errors import PushUnavailableError
from naru_be.models.repositories.push_repository import SubscriptionKeys

log = logging.getLogger(__name__)


class WebPushSender:
    def __init__(self, settings: Settings, timeout_s: float = 10.0) -> None:
        self.settings = settings
        self.timeout_s = timeout_s

    def vapid(self) -> Vapid:
        secret = self.settings.vapid_private_key.get_secret_value().strip()
        if not secret or not self.settings.vapid_subject.startswith("mailto:"):
            raise PushUnavailableError("서버에 VAPID 키·subject 가 없다")
        return (
            Vapid.from_pem(secret.encode())
            if secret.startswith("-----")
            else Vapid.from_string(secret)
        )

    def send(self, keys: SubscriptionKeys, payload: dict[str, object]) -> int:
        """HTTP 상태 — 2xx 성공. 거절이면 그 상태(404·410 = 구독 없음), 연결 실패는 0."""
        info = {"endpoint": keys.endpoint, "keys": {"p256dh": keys.p256dh, "auth": keys.auth}}
        try:
            resp = webpush(
                subscription_info=info,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self.vapid(),
                vapid_claims={"sub": self.settings.vapid_subject},
                ttl=self.settings.push_ttl_s,
                timeout=self.timeout_s,
            )
        except WebPushException as e:
            code = e.status_code
            status = int(code) if isinstance(code, int) else 0
            log.warning("push rejected", extra={"status": status, "endpoint": keys.endpoint[:40]})
            return status
        ok = getattr(resp, "status_code", None)
        return int(ok) if isinstance(ok, int) else 0
