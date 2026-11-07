"""CandidatePublisher — CandidateBatch 를 BE 로 POST (ARCHITECTURE ⑥, CONVENTIONS §3.1).

httpx 로 `POST {NARU_BE_URL}/internal/candidates`, 헤더 X-Naru-Internal-Token. 연결 오류·5xx 는 3회
재시도, 4xx 는 바로 실패(토큰·스키마 문제는 재시도해도 같다). 단위 테스트하지 않는다 — e2e 에서
실제 BE 로만 (packages/be/tests/test_e2e_worker.py, httpx WSGITransport 로 실제 Flask 앱 호출).
"""

from __future__ import annotations

import logging
import time

import httpx

from naru_contracts import CandidateBatch, CandidateBatchResponse

log = logging.getLogger(__name__)


class PublishError(Exception):
    pass


class CandidatePublisher:
    def __init__(
        self,
        base_url: str,
        token: str,
        client: httpx.Client | None = None,
        retries: int = 3,
        backoff_s: float = 1.0,
    ) -> None:
        if not token:
            raise ValueError("NARU_INTERNAL_TOKEN 없음 — BE 가 전부 401 로 거절한다")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.retries = retries
        self.backoff_s = backoff_s
        self._client = client or httpx.Client(timeout=30.0)

    def publish(self, batch: CandidateBatch) -> CandidateBatchResponse:
        url = f"{self.base_url}/internal/candidates"
        body = batch.model_dump(mode="json")
        headers = {"X-Naru-Internal-Token": self.token}
        last = "?"
        for attempt in range(1, self.retries + 1):
            started = time.monotonic()
            try:
                r = self._client.post(url, json=body, headers=headers)
            except httpx.TransportError as exc:
                last = repr(exc)
                log.warning("publish transport error", extra={"attempt": attempt, "error": last})
                time.sleep(self.backoff_s * attempt)
                continue
            elapsed_ms = int((time.monotonic() - started) * 1000)
            log.info(
                "publish",
                extra={
                    "api": "naru_be",
                    "params": {"batch_id": batch.batch_id, "n": len(batch.candidates)},
                    "status": r.status_code,
                    "elapsed_ms": elapsed_ms,
                },
            )
            if r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(self.backoff_s * attempt)
                continue
            if r.status_code != 202:
                raise PublishError(f"{batch.batch_id}: HTTP {r.status_code} {r.text[:200]}")
            return CandidateBatchResponse.model_validate(r.json())
        raise PublishError(f"{batch.batch_id}: {self.retries}회 실패 — {last}")
