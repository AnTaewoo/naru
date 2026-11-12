"""AnthropicClient — 유일한 LLM 클라이언트 (ADR-007). tool use 로 출력 스키마를 고정한다.

파라미터명은 설치된 anthropic 2.6.0 의 타입에서 확인했다 (2026-11-07):
  anthropic.types.ToolParam        = {name, description, input_schema, strict, cache_control, ...}
  anthropic.types.ToolChoiceToolParam = {type: "tool", name, disable_parallel_tool_use}
  MessageCreateParamsBase 에 temperature/top_p/top_k 가 없다 — claude-haiku-5-5 는 샘플링 파라미터를
  보내면 400 이라 보내지 않는다 (CONVENTIONS §3.2 의 temperature=0 은 적용 불가, T4.1 보고).
  tool_choice 로 강제하면 thinking 없이 바로 tool 호출이 온다 (모델 문서).
호출 수는 한 실행에 max_calls 까지 (CLAUDE.md §2: live 는 Task당 10회 이하).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import anthropic
from anthropic.types import MessageParam, TextBlockParam, ToolChoiceToolParam, ToolParam

from naru_ai.config import Settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMBudgetError(LLMError):
    pass


class LLMRefusalError(LLMError):
    pass


class LLMTruncatedError(LLMError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True)
class ToolCompletion:
    model: str
    input: dict[str, object]  # tool_use.input — JSON 으로 파싱된 dict
    stop_reason: str | None
    usage: dict[str, object]
    raw: dict[str, object]  # Message.model_dump(mode="json") 원문 (기록용)
    elapsed_ms: int


class AnthropicClient:
    def __init__(self, settings: Settings | None = None, max_calls: int | None = None) -> None:
        self.settings = settings or Settings()
        self.max_calls = max_calls or self.settings.llm_max_calls_per_run
        self.calls = 0
        self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key or None)

    def complete_tool(
        self, system: str, messages: list[MessageParam], tool: ToolSpec
    ) -> ToolCompletion:
        """system + messages → tool 하나를 강제 호출 → 그 입력을 돌려준다."""
        if self.calls >= self.max_calls:
            raise LLMBudgetError(f"호출 상한 {self.max_calls}회 — 기록(recorder)을 쓴다")
        self.calls += 1
        system_blocks: list[TextBlockParam] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        tool_param: ToolParam = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "strict": True,
        }
        choice: ToolChoiceToolParam = {"type": "tool", "name": tool.name}
        started = time.monotonic()
        message = self._client.messages.create(
            model=self.settings.llm_model,
            max_tokens=self.settings.llm_max_tokens,
            system=system_blocks,
            messages=messages,
            tools=[tool_param],
            tool_choice=choice,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        usage = message.usage.model_dump(mode="json")
        log.info(
            "anthropic messages.create",
            extra={
                "api": "anthropic",
                "model": message.model,
                "status": message.stop_reason,
                "elapsed_ms": elapsed_ms,
                "usage": usage,
            },
        )
        if message.stop_reason == "refusal":
            raise LLMRefusalError(f"거절: {message.stop_details}")
        if message.stop_reason == "max_tokens":
            raise LLMTruncatedError(f"max_tokens {self.settings.llm_max_tokens} 초과 — 잘림")
        for block in message.content:
            if block.type == "tool_use" and block.name == tool.name:
                if not isinstance(block.input, dict):
                    raise LLMError(f"tool_use.input 이 객체가 아니다: {type(block.input).__name__}")
                return ToolCompletion(
                    model=message.model,
                    input={str(k): v for k, v in block.input.items()},
                    stop_reason=message.stop_reason,
                    usage=usage,
                    raw=message.model_dump(mode="json"),
                    elapsed_ms=elapsed_ms,
                )
        raise LLMError(f"tool_use 블록 없음 (stop_reason={message.stop_reason})")
