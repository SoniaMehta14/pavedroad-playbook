"""OllamaProvider tests against a mocked HTTP transport — no network calls."""

import httpx

from adapters.base import Message
from adapters.local import OllamaProvider


def _handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/chat"
    return httpx.Response(
        200,
        json={
            "model": "gemma2:9b",
            "message": {"role": "assistant", "content": "hi from ollama"},
            "done": True,
            "prompt_eval_count": 42,
            "eval_count": 7,
        },
    )


def test_complete_parses_ollama_response_with_zero_cost() -> None:
    provider = OllamaProvider(transport=httpx.MockTransport(_handler))

    result = provider.complete(
        [Message(role="user", content="hi")], model="gemma2:9b", max_tokens=50
    )

    assert result.text == "hi from ollama"
    assert result.usage.input_tokens == 42
    assert result.usage.output_tokens == 7
    assert result.usage.cost_usd == 0.0
    assert result.stop_reason == "end_turn"
    provider.close()
