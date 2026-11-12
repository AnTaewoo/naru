"""로깅 — 표준 logging + JSON 한 줄 (CONVENTIONS §1). print 금지. 키는 남기지 않는다.

naru_be/log.py 와 같은 포맷. AI 와 BE 는 서로 import 하지 않으므로 각자 가진다.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        body: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        body.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info:
            body["exc"] = self.formatException(record.exc_info)
        return json.dumps(body, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonLineFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLineFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("httpx", "httpx2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)  # URL·헤더에 키가 섞인다
