"""OpenAI-compatible provider — the fallback adapter.

Works with anything that speaks the OpenAI chat-completions REST shape:
OpenAI itself, or any self-hosted or third-party endpoint that mimics it
(vLLM, LM Studio, Together, Groq, and most inference gateways). No SDK
dependency — the wire format is simple enough that a thin HTTP client is
the whole adapter, and it avoids pinning this repo to a second heavyweight
vendor SDK just to prove vendor neutrality.

Cost is not computed automatically: third-party endpoint pricing varies
too widely to hardcode, and self-hosted deployments often have no
per-token price at all. Supply price_per_mtok explicitly if the
orchestration layer's cost guardrails should see a nonzero number here.
"""

import httpx

from .base import CompletionResult, Message, Usage


class OpenAICompatProvider:
    """Adapter over any OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        price_per_mtok: tuple[float, float] | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._price_per_mtok = price_per_mtok
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

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = self._client.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json={"model": model, "max_tokens": max_tokens, "messages": payload_messages},
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        text: str = choice["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        cost = 0.0
        if self._price_per_mtok is not None:
            in_price, out_price = self._price_per_mtok
            cost = (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price

        return CompletionResult(
            text=text,
            model=data.get("model", model),
            stop_reason=choice.get("finish_reason", "unknown"),
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost),
        )

    def close(self) -> None:
        self._client.close()
