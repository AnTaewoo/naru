"""AI → BE 버스 위치 (INTERFACE §1.2 v0.13, ADR-013 D).

서울 버스위치정보 getBusPosByRtid 의 itemList 를 판단 없이 그대로 옮긴다(이름만 snake_case,
gpsX/gpsY → lng/lat). 버스는 후보(통제)를 만들지 않는다 — BE 가 이 위치로 기존 통제의 확신도만
고친다(T6.3).
"""

from datetime import datetime

from pydantic import Field, field_validator

from naru_contracts._base import Contract
from naru_contracts.closure import _require_offset


class BusPosition(Contract):
    """차량 하나의 한 시점."""

    veh_id: str  # vehId
    plain_no: str | None = None  # plainNo (차량 번호)
    data_tm: datetime  # dataTm — YYYYMMDDHHmmss KST 를 +09:00 로
    lng: float = Field(ge=-180.0, le=180.0)  # gpsX (WGS84)
    lat: float = Field(ge=-90.0, le=90.0)  # gpsY
    sect_ord: int | None = None  # sectOrd — 노선의 몇 번째 구간
    section_id: str | None = None  # sectionId
    sect_dist: float | None = None  # sectDist — 응답 값 그대로(km 로 보임: fullSectDist 0.214)
    stop_flag: bool | None = None  # stopFlag — 1 이면 정류소 도착
    last_stn_id: str | None = None  # lastStnId — 마지막으로 지난 정류소
    next_st_id: str | None = None  # nextStId
    is_run: bool | None = None  # isrunyn

    _tz = field_validator("data_tm")(_require_offset)


class BusPositionBatch(Contract):
    """노선 하나를 한 번 부른 결과. 같은 차량·같은 dataTm 은 BE 가 한 번만 저장한다(멱등)."""

    batch_id: str  # bus-<노선>-<원문 sha1 앞 12자리>
    produced_at: datetime
    route_id: str  # busRouteId (9자리)
    ref: str  # 원문 기록 파일 (data/recorded/bus/…)
    called_at: datetime  # 부른 시각
    positions: list[BusPosition]

    _tz = field_validator("produced_at", "called_at")(_require_offset)


class BusPositionBatchResponse(Contract):
    batch_id: str
    accepted: int  # 새로 저장한 위치 수
