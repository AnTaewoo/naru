"""AI 워커 설정 — 키·모델·프롬프트 버전·호출 상한은 전부 여기 (CONVENTIONS §1 "설정").

os.environ 을 직접 읽지 않는다. .env 의 ANTHROPIC_API_KEY / NARU_LLM_MODEL / NARU_PROMPT_VERSION.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-haiku-5-5", validation_alias="NARU_LLM_MODEL")
    prompt_version: str = Field(default="notice_v2", validation_alias="NARU_PROMPT_VERSION")
    # tool 입력(items[] + spans)이 1024 토큰을 넘곤 한다 (CONVENTIONS §3.2 의 1024 는 v1 스키마 값)
    llm_max_tokens: int = Field(default=4096, validation_alias="NARU_LLM_MAX_TOKENS")
    # live 호출은 Task당 10회 이하 (CLAUDE.md §2)
    llm_max_calls_per_run: int = Field(default=10, validation_alias="NARU_LLM_MAX_CALLS")
    # 운영 워커 live 파싱 하루 상한 (ADR-011 D) — 넘으면 다음 날로
    llm_daily_cap: int = Field(default=200, validation_alias="NARU_LLM_DAILY_CAP")

    data_dir: Path = Field(default=Path("data"), validation_alias="NARU_DATA_DIR")

    # 워커 → BE (T4.4). 토큰은 BE 의 NARU_INTERNAL_TOKEN 과 같은 값
    be_url: str = Field(default="http://localhost:5000", validation_alias="NARU_BE_URL")
    internal_token: str = Field(default="", validation_alias="NARU_INTERNAL_TOKEN")
    notice_interval_s: int = Field(
        default=300, validation_alias="NARU_NOTICE_INTERVAL_S"
    )  # 공지 5분
    # T6.1 TOPIS 실시간 돌발(OA-13315). recorded = 기록 재생(키 없이, 개발·테스트),
    # live = 호출 + 기록(운영 워커). incident_record 는 recorded 에서 쓸 파일(없으면 가장 최근)
    incident_source: Literal["live", "recorded"] = Field(
        default="recorded", validation_alias="NARU_INCIDENT_SOURCE"
    )
    incident_record: Path | None = Field(default=None, validation_alias="NARU_INCIDENT_RECORD")
    incident_interval_s: int = Field(
        default=300, validation_alias="NARU_INCIDENT_INTERVAL_S"
    )  # 돌발 5분 — 키로 쓰는 공개 API 라 ADR-011 E 의 10분 대상이 아니다 (ADR-013 H)
    seoul_opendata_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="SEOUL_OPENDATA_KEY"
    )
    seoul_api_url: str = Field(
        default="http://openapi.seoul.go.kr:8088", validation_alias="NARU_SEOUL_API_URL"
    )
    # T6.4 TOPIS 통제·버스 공지(NoticeList OA-22861). recorded = 기록(지정 파일, 없으면 최근)
    topis_source: Literal["live", "recorded"] = Field(
        default="recorded", validation_alias="NARU_TOPIS_SOURCE"
    )
    topis_record: Path | None = Field(default=None, validation_alias="NARU_TOPIS_RECORD")
    topis_interval_s: int = Field(default=600, validation_alias="NARU_TOPIS_INTERVAL_S")  # 10분
    topis_size: int = Field(default=50, validation_alias="NARU_TOPIS_SIZE")  # 최신 50건
    # T6.2 버스 위치 (ADR-013 D·G). recorded = 노선별 가장 최근 기록 재생, live = 호출 + 기록
    bus_source: Literal["live", "recorded"] = Field(
        default="recorded", validation_alias="NARU_BUS_SOURCE"
    )
    bus_interval_s: int = Field(default=60, validation_alias="NARU_BUS_INTERVAL_S")
    bus_daily_cap: int = Field(default=900, validation_alias="NARU_BUS_DAILY_CAP")  # 개발계정 1,000
    bus_routes_per_event: int = Field(default=3, validation_alias="NARU_BUS_ROUTES_PER_EVENT")
    data_go_kr_key: SecretStr = Field(default=SecretStr(""), validation_alias="DATA_GO_KR_KEY")
    # 2순위 TOPIS 집회·행사 돌발 — 기준 데이터, 돌발마다 노선 1개 (태우 2026-11-08)
    bus_incident_interval_s: int = Field(
        default=120, validation_alias="NARU_BUS_INCIDENT_INTERVAL_S"
    )
    bus_incident_daily_cap: int = Field(default=300, validation_alias="NARU_BUS_INCIDENT_DAILY_CAP")
    bus_incident_calls_each: int = Field(
        default=30, validation_alias="NARU_BUS_INCIDENT_CALLS_EACH"
    )  # 돌발 하나 하루 30회(약 1시간) — 300회를 몇 건이 다 쓰지 않게
    # 노선 경로 getRoutePath(노선정보조회 15000193). 따로 받은 키가 있으면, 없으면 DATA_GO_KR_KEY
    data_go_kr_route_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="DATA_GO_KR_ROUTE_KEY"
    )

    @property
    def recorded_llm_dir(self) -> Path:
        """data/recorded/llm/anthropic/<model>@api/<prompt_version>/ 의 루트 (CONVENTIONS §3.3)."""
        return self.data_dir / "recorded" / "llm"
