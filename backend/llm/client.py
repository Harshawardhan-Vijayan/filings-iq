"""OpenAI chat client with JSON-mode and tool-calling helpers."""

import json
from dataclasses import dataclass, field
from typing import Any

from backend.config import settings
from backend.retrieval.embeddings import _client  # reuse the cached OpenAI client


@dataclass
class LLMResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[Any] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def chat(
    messages: list[dict[str, Any]],
    json_mode: bool = False,
    tools: list[dict] | None = None,
    model: str | None = None,
) -> LLMResult:
    """Single chat completion. Returns content, token usage, and any tool calls."""
    client = _client()
    kwargs: dict[str, Any] = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    usage = resp.usage

    return LLMResult(
        content=choice.message.content or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        tool_calls=list(choice.message.tool_calls or []),
    )


def chat_json(messages: list[dict[str, Any]]) -> tuple[dict, LLMResult]:
    """Chat in JSON mode and parse the response into a dict."""
    result = chat(messages, json_mode=True)
    try:
        parsed = json.loads(result.content)
    except json.JSONDecodeError:
        parsed = {}
    return parsed, result
