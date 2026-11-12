"""LLMRecorder — 요청·응답 원문 기록·재생 (CONVENTIONS §3.3).

경로: data/recorded/llm/anthropic/<model>@api/<prompt_version>/<sentence_id>.json
파일: api, model, prompt_version, sentence_id, called_at, request(system·messages·tool),
response(원문), usage, elapsed_ms. 키는 들어 있지 않다. 손으로 고치지 않는다.
재생 시 파일의 model·prompt_version 이 지금 설정과 다르면 RecordingMismatchError — 옛 기록으로
테스트가 통과하는 일을 막는다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from anthropic.types import MessageParam

from naru_ai.llm.client import ToolCompletion, ToolSpec


class RecordingMismatchError(Exception):
    pass


@dataclass(frozen=True)
class Recording:
    api: str
    model: str
    prompt_version: str
    sentence_id: str
    called_at: str
    request: dict[str, object]
    response: dict[str, object]
    usage: dict[str, object]
    elapsed_ms: int

    def tool_input(self) -> dict[str, object]:
        """response.content 의 tool_use.input (파서 입력)."""
        content = self.response.get("content")
        assert isinstance(content, list)
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                inp = block.get("input")
                if isinstance(inp, dict):
                    return {str(k): v for k, v in inp.items()}
        raise ValueError(f"{self.sentence_id}: 기록에 tool_use 가 없다")


class LLMRecorder:
    def __init__(self, root: Path, model: str, prompt_version: str, api: str = "anthropic") -> None:
        self.api = api
        self.model = model
        self.prompt_version = prompt_version
        self.dir = root / api / f"{model}@api" / prompt_version

    def path(self, sentence_id: str) -> Path:
        return self.dir / f"{sentence_id}.json"

    def exists(self, sentence_id: str) -> bool:
        return self.path(sentence_id).exists()

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def saved_today(self, now: datetime) -> int:
        """오늘(KST) 남긴 기록 수 = 오늘 live 로 부른 수 (ADR-011 D 하루 상한, T6.4).

        파일 시각(mtime)으로 센다 — 기록은 손대지 않으니 쓴 시각이다. 복사로 시각이 새로 되면
        더 세어 덜 부른다(상한 쪽으로만 틀린다). 기록이 안 남는 거절·잘림은 안 센다(워커가 막는다).
        """
        kst = timezone(timedelta(hours=9))
        today = now.astimezone(kst).date()
        return sum(
            1
            for p in self.dir.glob("*.json")
            if datetime.fromtimestamp(p.stat().st_mtime, kst).date() == today
        )

    def save(
        self,
        sentence_id: str,
        system: str,
        messages: list[MessageParam],
        tool: ToolSpec,
        completion: ToolCompletion,
    ) -> Recording:
        rec = Recording(
            api=self.api,
            model=self.model,
            prompt_version=self.prompt_version,
            sentence_id=sentence_id,
            called_at=datetime.now(UTC).isoformat(timespec="seconds"),
            request={
                "system": system,
                "messages": [dict(m) for m in messages],
                "tool": asdict(tool),
            },
            response=completion.raw,
            usage=completion.usage,
            elapsed_ms=completion.elapsed_ms,
        )
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path(sentence_id).write_text(
            json.dumps(asdict(rec), ensure_ascii=False, indent=1) + "\n", "utf-8"
        )
        return rec

    def load(self, sentence_id: str) -> Recording:
        path = self.path(sentence_id)
        if not path.exists():
            raise FileNotFoundError(f"기록 없음: {path} — make record-llm 먼저")
        rec = Recording(**json.loads(path.read_text("utf-8")))
        if rec.model != self.model or rec.prompt_version != self.prompt_version:
            raise RecordingMismatchError(
                f"{path.name}: 기록 {rec.model}/{rec.prompt_version} ≠ "
                f"설정 {self.model}/{self.prompt_version}"
            )
        return rec
