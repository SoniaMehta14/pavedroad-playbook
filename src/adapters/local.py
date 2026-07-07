"""Local model provider — Ollama.

Self-hosted inference is a deliberate cost lever, not a fallback of last
resort: an open-source model run locally (Gemma via Ollama, or anything
else Ollama serves) carries no per-token API cost, which matters when the
routing table can send high-volume, low-stakes work here instead of a
metered endpoint. Cost is always reported as zero — the real cost is
amortized compute the orchestration layer's guardrails don't currently
model, not a token price.
"""

import httpx

from .base import CompletionResult, Message, Usage


class OllamaProvider:
    """Adapter over a local Ollama server's native /api/chat endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        payload_messages: list[dict[str, str]] = []
        if system is not None:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        )

        response = self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": model,
                "messages": payload_messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        data = response.json()

        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return CompletionResult(
            text=data["message"]["content"],
            model=data.get("model", model),
            stop_reason="end_turn" if data.get("done") else "unknown",
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=0.0),
        )

    def close(self) -> None:
        self._client.close()
