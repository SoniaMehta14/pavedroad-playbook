import pytest

from adapters.pricing import anthropic_cost_usd


def test_known_model_computes_cost() -> None:
    # 1M input tokens at $5/MTok + 1M output tokens at $25/MTok = $30
    cost = anthropic_cost_usd("claude-opus-4-8", 1_000_000, 1_000_000)
    assert cost == pytest.approx(30.0)


def test_zero_tokens_is_zero_cost() -> None:
    assert anthropic_cost_usd("claude-haiku-4-5", 0, 0) == 0.0


def test_unpriced_model_raises_rather_than_silently_returning_zero() -> None:
    with pytest.raises(ValueError, match="no pricing entry"):
        anthropic_cost_usd("claude-nonexistent-9000", 100, 100)
