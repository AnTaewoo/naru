"""실제 브라우저 푸시 구독을 기록한다 (T7.8, ADR-014 C 열린 질문 3 — 가짜 구독 없이 저장·파싱).

    NARU_FE_ORIGIN=http://127.0.0.1:3060 uv run python scripts/record_push_subscription.py

헤드리스 Chrome(영속 프로필 `{D}/recorded/push/chrome-profile/`)이 실제 푸시 서비스(FCM)에 구독한다.
VAPID 키 쌍은 `{D}/recorded/push/vapid_test.pem`(없으면 여기서 만든다 — 테스트 전용, 운영 키는
.env 의 태우 것). 출력 `{D}/recorded/push/<ts>_subscription.json`: {fetched_at, origin, user_agent,
vapid_public_key, subscription}. 키·endpoint 는 그대로 둔다 — 기록 폴더는 git 에 안 올라간다
(.gitignore).
MANIFEST 에는 sha256 만.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid, b64urlencode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "recorded" / "push"
FE = ROOT / "packages" / "fe"


def public_key_of(vapid: Vapid) -> str:
    raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return str(b64urlencode(raw))


def main() -> int:
    origin = os.environ.get("NARU_FE_ORIGIN", "http://127.0.0.1:3000")
    OUT.mkdir(parents=True, exist_ok=True)
    pem = OUT / "vapid_test.pem"
    if not pem.exists():
        made = Vapid()
        made.generate_keys()
        pem.write_bytes(made.private_pem())
        print(f"{pem.relative_to(ROOT)} 새로 만듦 (테스트 전용)")
    vapid = Vapid.from_pem(pem.read_bytes())
    pub = public_key_of(vapid)
    cmd = [
        "node",
        str(ROOT / "scripts" / "record_push_subscription.mjs"),
        pub,
        origin,
        str(OUT / "chrome-profile"),
    ]
    done = subprocess.run(cmd, cwd=FE, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        print(done.stdout, done.stderr, file=sys.stderr)
        return 1
    got = json.loads(done.stdout.strip().splitlines()[-1])
    now = datetime.now(UTC)
    doc = {
        "fetched_at": now.isoformat(timespec="seconds"),
        "origin": origin,
        "user_agent": got["userAgent"],
        "vapid_public_key": pub,
        "subscription": got["subscription"],
    }
    path = OUT / f"{now.strftime('%Y%m%dT%H%M%S')}_subscription.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sub = got["subscription"]
    print(
        path.relative_to(ROOT),
        "endpoint",
        sub["endpoint"][:40] + "…",
        "keys",
        {k: len(v) for k, v in sub["keys"].items()},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
