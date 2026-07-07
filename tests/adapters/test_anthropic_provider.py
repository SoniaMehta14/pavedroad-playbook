"""AnthropicProvider tests against an injected fake client — no network calls.

The fake mimics only the surface AnthropicProvider actually touches
(response.content[].type/.text, response.usage, response.stop_reason,
response.model), which is deliberately narrow: it protects the adapter's
request-building and response-parsing logic without coupling the test
suite to the full Anthropic SDK's response schema.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from adapters.anthropic_provider import AnthropicProvider
from adapters.base import Message


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeResponse:
    content: list[_FakeTextBlock]
    model: str = "claude-opus-4-8"
    stop_reason: str = "end_turn"
    usage: _FakeUsage = field(default_factory=lambda: _FakeUsage(10, 5))


class _FakeMessages:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_request: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_request = kwargs
        return self._response


class _FakeAnthropicClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.messages = _FakeMessages(response)


def test_complete_extracts_text_and_computes_cost() -> None:
    fake_client = _FakeAnthropicClient(
        _FakeResponse(
            content=[_FakeTextBlock("hello there")], usage=_FakeUsage(1_000_000, 1_000_000)
        )
    )
    provider = AnthropicProvider(client=fake_client)  # type: ignore[arg-type]

    result = provider.complete(
        [Message(role="user", content="hi")], model="claude-opus-4-8", max_tokens=100
    )

    assert result.text == "hello there"
    assert result.usage.input_tokens == 1_000_000
    assert result.usage.cost_usd == pytest.approx(30.0)
    assert result.stop_reason == "end_turn"


def test_system_prompt_is_passed_through_and_system_role_messages_filtered() -> None:
    fake_client = _FakeAnthropicClient(_FakeResponse(content=[_FakeTextBlock("ok")]))
    provider = AnthropicProvider(client=fake_client)  # type: ignore[arg-type]

    provider.complete(
        [
            Message(role="system", content="this should be filtered out of messages"),
            Message(role="user", content="hi"),
        ],
        model="claude-opus-4-8",
        max_tokens=100,
        system="you are a helpful assistant",
    )

    sent = fake_client.messages.last_request
    assert sent is not None
    assert sent["system"] == "you are a helpful assistant"
    assert sent["messages"] == [{"role": "user", "content": "hi"}]


def test_no_system_prompt_omits_the_key_entirely() -> None:
    fake_client = _FakeAnthropicClient(_FakeResponse(content=[_FakeTextBlock("ok")]))
    provider = AnthropicProvider(client=fake_client)  # type: ignore[arg-type]

    provider.complete([Message(role="user", content="hi")], model="claude-opus-4-8", max_tokens=100)

    sent = fake_client.messages.last_request
    assert sent is not None
    assert "system" not in sent
