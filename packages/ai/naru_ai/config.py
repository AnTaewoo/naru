"""AI 워커 설정 — 키·모델·프롬프트 버전·호출 상한은 전부 여기 (CONVENTIONS §1 "설정").

os.environ 을 직접 읽지 않는다. .env 의 ANTHROPIC_API_KEY / NARU_LLM_MODEL / NARU_PROMPT_VERSION.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-haiku-5-5", validation_alias="NARU_LLM_MODEL")
    prompt_version: str = Field(default="notice_v1", validation_alias="NARU_PROMPT_VERSION")
    # tool 입력(items[] + spans)이 1024 토큰을 넘곤 한다 (CONVENTIONS §3.2 의 1024 는 v1 스키마 값)
    llm_max_tokens: int = Field(default=4096, validation_alias="NARU_LLM_MAX_TOKENS")
    # live 호출은 Task당 10회 이하 (CLAUDE.md §2)
    llm_max_calls_per_run: int = Field(default=10, validation_alias="NARU_LLM_MAX_CALLS")

    data_dir: Path = Field(default=Path("data"), validation_alias="NARU_DATA_DIR")

    @property
    def recorded_llm_dir(self) -> Path:
        """data/recorded/llm/anthropic/<model>@api/<prompt_version>/ 의 루트 (CONVENTIONS §3.3)."""
        return self.data_dir / "recorded" / "llm"
