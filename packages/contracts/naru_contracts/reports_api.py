"""FE → BE: 통제 제보 (INTERFACE §8, v0.14 보충 — 태우 지시 11/10, 교수님 멘토링 T-A).

POST /crosswalks/nearest (§8.1) · POST /reports (§8.2) · GET /reports/recent (§8.3).
기록만 — 경로·확신도·상태에 쓰지 않는다. 좌표는 §8.1 요청 본문으로만 받고 저장하지 않는다.
"""

import math
import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from naru_contracts._base import Contract
from naru_contracts.closure import LngLat, _require_offset

# OA-23081 횡단보도관리번호 — 21,776행 전부 이 모양 (2026-11-10 xlsx 3열 확인)
CROSSWALK_ID = re.compile(r"\d{2}-\d{10}")
DEVICE = re.compile(r"[A-Za-z0-9-]{16,64}")  # FE 가 처음 한 번 만든 무작위 토큰 (crypto.randomUUID)
ACCURACY_MAX_M = 1000  # 위치 정확도 상한 — 이보다 흐린 위치로는 제보를 받지 않는다
# 한 번에 묻는 횡단보도 — 경로 하나가 피한 곳(§2 avoided). 기록된 경로는 많아야 2곳
RECENT_IDS_MAX = 50

ReportState = Literal["blocked", "open"]
ReportSource = Literal["user", "field"]  # field = 현장 검증 (FE ?mode=field)


def _crosswalk_id(v: str) -> str:
    if not CROSSWALK_ID.fullmatch(v):
        raise ValueError(f"횡단보도 관리번호는 숫자 2-숫자 10 ({v})")
    return v


class NearestCrosswalkQuery(Contract):
    """§8.1 요청 본문 — 저장·로그하지 않는다."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    @field_validator("lat", "lng")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("숫자가 아니다")
        return v


class NearestCrosswalk(Contract):
    id: str  # 횡단보도관리번호
    name: str  # 교차로명 (OA-23081 — 빈 행 없음)
    district: str  # 자치구
    coord: LngLat
    distance_m: int = Field(ge=0)  # 요청 점과의 거리 (EPSG:5179, 반올림)


class NearestCrosswalkResponse(Contract):
    crosswalk: NearestCrosswalk | None  # report_snap_m 안에 없으면 null


class ReportRequest(Contract):
    crosswalk_id: str
    state: ReportState
    accuracy_m: int = Field(ge=0, le=ACCURACY_MAX_M)  # 브라우저 위치 정확도, 반올림 m
    source: ReportSource
    device: str  # BE 는 sha256 만 저장한다

    _cw = field_validator("crosswalk_id")(_crosswalk_id)

    @field_validator("device")
    @classmethod
    def _device(cls, v: str) -> str:
        if not DEVICE.fullmatch(v):
            raise ValueError("기기 토큰은 영문·숫자·- 16~64자")
        return v


class ReportResponse(Contract):
    id: int
    crosswalk_id: str
    state: ReportState
    reported_at: datetime  # 서버가 받은 시각

    _tz = field_validator("reported_at")(_require_offset)


class RecentReportsQuery(Contract):
    ids: tuple[str, ...] = Field(min_length=1)
    minutes: int = Field(default=60, ge=1, le=1440)

    @field_validator("ids", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        """쿼리 문자열 "id,id" → 튜플 (빈 칸은 뺀다)"""
        if isinstance(v, str):
            return tuple(p for p in (x.strip() for x in v.split(",")) if p)
        return v

    @field_validator("ids")
    @classmethod
    def _ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        ids = tuple(_crosswalk_id(x) for x in dict.fromkeys(v))  # 겹치면 하나, 순서 그대로
        if len(ids) > RECENT_IDS_MAX:
            raise ValueError(f"ids: 횡단보도 {RECENT_IDS_MAX}개까지 ({len(ids)}개)")
        return ids


class ReportCounts(Contract):
    blocked: int = Field(ge=0)
    open: int = Field(ge=0)


class RecentReportsResponse(Contract):
    counts: dict[str, ReportCounts]  # 그 시간 안에 제보가 있는 횡단보도만
