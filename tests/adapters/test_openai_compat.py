"""OpenAICompatProvider tests against a mocked HTTP transport — no network calls."""

import json

import httpx
import pytest

from adapters.base import Message
from adapters.openai_compat import OpenAICompatProvider


def _handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/v1/chat/completions"
    body = json.loads(request.read())
    assert body["model"] == "gpt-oss-fake"
    return httpx.Response(
        200,
        json={
            "model": "gpt-oss-fake",
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        },
    )


def test_complete_parses_response_and_applies_supplied_pricing() -> None:
    provider = OpenAICompatProvider(
        base_url="https://example.test/v1",
        api_key="sk-fake",
        price_per_mtok=(1.0, 2.0),
        transport=httpx.MockTransport(_handler),
    )

    result = provider.complete(
        [Message(role="user", content="hi")], model="gpt-oss-fake", max_tokens=100
    )

    assert result.text == "hello"
    assert result.stop_reason == "stop"
    assert result.usage.input_tokens == 1_000_000
    assert result.usage.cost_usd == pytest.approx(3.0)  # 1M*$1 + 1M*$2, per MTok
    provider.close()


def test_no_pricing_supplied_reports_zero_cost() -> None:
    provider = OpenAICompatProvider(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(_handler),
    )

    result = provider.complete(
        [Message(role="user", content="hi")], model="gpt-oss-fake", max_tokens=100
    )

    assert result.usage.cost_usd == 0.0
    provider.close()


def test_system_prompt_included_as_leading_message() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "model": "gpt-oss-fake",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    provider = OpenAICompatProvider(
        base_url="https://example.test/v1", transport=httpx.MockTransport(handler)
    )
    provider.complete(
        [Message(role="user", content="hi")],
        model="gpt-oss-fake",
        max_tokens=10,
        system="be terse",
    )
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["messages"][0] == {"role": "system", "content": "be terse"}
    provider.close()
