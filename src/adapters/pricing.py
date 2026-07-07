"""Per-model pricing for cost accounting.

Anthropic pricing is pinned here because rates are public and change on a
predictable release cadence — this table is the single place to update
when a new model ships or a price changes. OpenAI-compatible and local
endpoints have no fixed rate: cost is either supplied by the caller (a
self-hosted deployment with a known amortized cost) or reported as zero.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float


ANTHROPIC_PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-8": ModelPricing(5.00, 25.00),
    "claude-sonnet-5": ModelPricing(3.00, 15.00),
    "claude-haiku-4-5": ModelPricing(1.00, 5.00),
}


def anthropic_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost for an Anthropic model call.

    Raises on an unpriced model rather than silently returning zero — a
    silent zero would corrupt every cost report downstream in the
    orchestration guardrails, and that failure mode is worse than a loud
    one caught in code review.
    """
    if model not in ANTHROPIC_PRICING:
        raise ValueError(
            f"no pricing entry for model {model!r} — add it to ANTHROPIC_PRICING "
            "before routing traffic to it"
        )
    pricing = ANTHROPIC_PRICING[model]
    return (input_tokens / 1_000_000) * pricing.input_per_mtok + (
        output_tokens / 1_000_000
    ) * pricing.output_per_mtok
