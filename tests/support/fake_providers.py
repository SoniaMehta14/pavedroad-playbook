"""Fake LLM providers shared across interop, orchestration, and eval tests.

None of these make network calls or require an API key — each computes a
real per-tier cost from the actual pricing table (so cost reports built
on top of them reflect genuine tier pricing) while faking only the
judgment content itself.
"""

import random
import re
from typing import ClassVar

from adapters.base import CompletionResult, Message, Usage
from adapters.pricing import anthropic_cost_usd

_FAKE_INPUT_TOKENS = 200
_FAKE_OUTPUT_TOKENS = 60


class TopCandidateEntityResolutionProvider:
    """A fake LLM for interop.llm_resolution.LLMResolver that always picks
    the first candidate it's offered, at high confidence — deterministic
    enough for integration testing while still exercising the full LLM
    round-trip (prompt building, response parsing, threshold check,
    matcher.attach)."""

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        prompt = messages[0].content
        match = re.search(r"UNIFIED-\d+", prompt)
        assert match is not None, "resolve.py should never call the LLM with zero candidates"
        chosen_id = match.group(0)
        return CompletionResult(
            text=f'{{"chosen_canonical_id": "{chosen_id}", "confidence": 0.9, '
            f'"rationale": "top candidate"}}',
            model=model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=10, cost_usd=0.0),
        )


class FakeReconciliationProvider:
    """Serves both the Analyst's ambiguous-date judgment prompt and the
    Validator's disagreement write-up prompt, branching on prompt content.
    Always judges "is_match": deliberately lenient, so the Validator's
    stricter independent check is what produces real disagreements on
    the larger date drifts, exercising the escalation path on real data.
    """

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        prompt = messages[0].content
        cost = anthropic_cost_usd(model, _FAKE_INPUT_TOKENS, _FAKE_OUTPUT_TOKENS)
        if "is_match" in prompt:
            text = '{"is_match": true, "confidence": 0.8, "rationale": "plausible same booking"}'
        else:
            text = "Escalating: independent check does not confirm the analyst's proposed match."
        return CompletionResult(
            text=text,
            model=model,
            stop_reason="end_turn",
            usage=Usage(
                input_tokens=_FAKE_INPUT_TOKENS, output_tokens=_FAKE_OUTPUT_TOKENS, cost_usd=cost
            ),
        )


class SimulatedTierAccuracyProvider:
    """Simulates model judgment quality varying by tier, for the
    cost-vs-accuracy frontier report.

    This is a deliberate simulation, not a measurement: a real accuracy
    difference between tiers would come from live model calls, which
    this reference implementation's test suite cannot depend on (no
    network access, no API key, no per-CI-run cost). The accuracy rates
    below are stated assumptions, not benchmarked numbers — the frontier
    report exists to demonstrate the cost/accuracy tradeoff mechanism a
    real deployment would populate with real eval data.

    Ground truth for every invoice that reaches the Analyst's
    ambiguous-date judgment in the synthetic corpus is "not a match" (see
    data/kestrel/invoices.py's date_drift case) — so the correct answer
    to simulate against is always is_match=False, and "accuracy" is the
    probability this fake gets that right for a given tier.
    """

    _ACCURACY_BY_MODEL: ClassVar[dict[str, float]] = {
        "claude-haiku-4-5": 0.55,
        "claude-sonnet-5": 0.80,
        "claude-opus-4-8": 0.97,
    }
    _DEFAULT_ACCURACY = 0.7

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        prompt = messages[0].content
        cost = anthropic_cost_usd(model, _FAKE_INPUT_TOKENS, _FAKE_OUTPUT_TOKENS)
        accuracy = self._ACCURACY_BY_MODEL.get(model, self._DEFAULT_ACCURACY)

        if "is_match" in prompt:
            correct = self._rng.random() < accuracy
            is_match = not correct  # the true answer is always "not a match" here
            text = (
                f'{{"is_match": {"true" if is_match else "false"}, '
                '"confidence": 0.8, "rationale": "simulated tier judgment"}'
            )
        else:
            text = "Escalating: independent check does not confirm the analyst's proposed match."

        return CompletionResult(
            text=text,
            model=model,
            stop_reason="end_turn",
            usage=Usage(
                input_tokens=_FAKE_INPUT_TOKENS, output_tokens=_FAKE_OUTPUT_TOKENS, cost_usd=cost
            ),
        )
