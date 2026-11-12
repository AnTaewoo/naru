"""공통 베이스 — 모르는 필드 거부, 불변 (CONVENTIONS §2)."""

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
