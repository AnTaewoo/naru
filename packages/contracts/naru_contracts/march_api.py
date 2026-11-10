"""BE → FE: 행진 예상 위치 키프레임 (INTERFACE §3.2, ADR-015 F, T7.16).

GET /closures/events/{id}/march?from=&to= — 통제 시간 동안 1분마다 표본 점·중심·반경·횡단보도별 P.
대상이 아닌 사건(방향을 모르거나 갈라진 행진, 집회·마라톤)은 404 not_modeled. ClosureEvent 스키마는
그대로.
"""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator, model_validator

from naru_contracts._base import Contract
from naru_contracts.closure import LngLat, Window, _require_offset

EVENT_ID_PATTERN = r"^[0-9a-f]{12}$"  # §3.1 사건 id


class MarchQuery(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    event_id: str = Field(pattern=EVENT_ID_PATTERN)
    from_: datetime | None = Field(default=None, alias="from")  # 기본 통제 시작
    to: datetime | None = None  # 기본 통제 끝

    _tz = field_validator("from_", "to")(_require_offset)

    @model_validator(mode="after")
    def _order(self) -> "MarchQuery":
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValueError("from 이 to 보다 늦다")
        return self


class MarchKeyframe(Contract):
    t: datetime
    samples: list[list[LngLat]]  # 표본(속도)별 머리~꼬리 점, 경로 위 일정 간격
    center: LngLat  # 그 점들의 가운데
    radius_m: float = Field(ge=0)  # 그 점들이 퍼진 반경 (표시용)
    crosswalks: dict[str, float]  # 경로 위 횡단보도 id → 그 시각 막혀 있을 확률 0~1

    _tz = field_validator("t")(_require_offset)

    @field_validator("crosswalks")
    @classmethod
    def _unit(cls, v: dict[str, float]) -> dict[str, float]:
        bad = next((k for k, p in v.items() if not 0 <= p <= 1), None)
        if bad is not None:
            raise ValueError(f"P 는 0~1 ({bad}: {v[bad]})")
        return v


class MarchResponse(Contract):
    event_id: str = Field(pattern=EVENT_ID_PATTERN)
    window: Window  # 통제 시작·끝 — 대상 사건은 둘 다 있다
    step_s: int = Field(ge=1)  # 키프레임 간격
    crosswalk_points: dict[str, LngLat]  # 경로 위 횡단보도 id → [lng, lat] (FE 가 P 색을 칠할 점)
    keyframes: list[MarchKeyframe]  # [from, to] ∩ 통제 시간, 시각 순

    @model_validator(mode="after")
    def _window_closed(self) -> "MarchResponse":
        if self.window.start is None or self.window.end is None:
            raise ValueError("행진 모델 사건은 시작·끝이 다 있다")
        return self
