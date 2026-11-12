"""View 공용 — 시각을 +09:00 으로 (CONVENTIONS §4.5). 한국어 라벨은 넣지 않는다 (FE i18n)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from naru_be.models.domain.types import KST
from naru_contracts import Evidence


def kst(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("오프셋 없는 시각은 응답에 넣지 않는다")
    return value.astimezone(KST)


def evidence_kst(items: Iterable[Evidence]) -> list[Evidence]:
    return [ev.model_copy(update={"at": kst(ev.at)}) for ev in items]
