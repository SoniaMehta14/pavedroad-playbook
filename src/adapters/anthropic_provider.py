"""Anthropic provider — the default adapter.

Uses the official Anthropic SDK. Reasoning depth (adaptive thinking, effort)
is exposed but off by default: this adapter executes whatever model and
tier the orchestration layer's routing table chose, and cost discipline
means reasoning depth is a routing decision, not a hardcoded default.
"""

from typing import Any

import anthropic

from .base import CompletionResult, Message, Usage
from .pricing import anthropic_cost_usd


class AnthropicProvider:
    """Adapter over the Anthropic Messages API."""

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic()

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages if m.role != "system"
            ],
        }
        if system is not None:
            request["system"] = system

        response = self._client.messages.create(**request)

        text = "".join(block.text for block in response.content if block.type == "text")
        cost = anthropic_cost_usd(model, response.usage.input_tokens, response.usage.output_tokens)
        return CompletionResult(
            text=text,
            model=response.model,
            stop_reason=response.stop_reason or "unknown",
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=cost,
            ),
        )
