"""Cost-vs-accuracy frontier: comparing routing configurations.

Runs the same golden reconciliation corpus through the Analyst/Validator
pipeline under several routing configurations — single-tier baselines
(all cheap, all mid, all expensive) and the production mixed routing
table — and reports each configuration's total cost against its
reconciliation accuracy side by side.

Entity resolution (src/interop) is held fixed across every frontier
point: it's resolved once, outside this function, and reused. Only the
orchestration routing table's tier assignments vary between configs —
that isolates the comparison to what this report is actually about.

This module takes no dependency on any specific LLM provider or test
fixture — callers supply a provider factory, so `src/evals` never
imports from `tests/`. The reference implementation's own test suite
(tests/evals/test_cost_frontier.py) supplies a provider whose accuracy
is *simulated* per tier rather than measured from live calls; see that
test file's docstring for why, and treat the frontier's accuracy numbers
as illustrating the mechanism, not benchmarking real model quality.
"""

from collections.abc import Callable

from pydantic import BaseModel

from adapters.base import LLMProvider
from interop.resolve import ResolutionReport
from interop.tools import KestrelToolServer
from orchestration.guardrails import Guardrails
from orchestration.pipeline import reconcile_invoices
from orchestration.routing import RoutingTable
from orchestration.state_store import StateStore

from .golden import ReconciliationGolden
from .reconciliation import score_reconciliation


class FrontierPoint(BaseModel):
    config_name: str
    total_cost_usd: float
    total_calls: int
    accuracy: float
    detection_recall: float


def single_tier_routing(model: str) -> RoutingTable:
    """A routing table that sends every route to the same model — the
    "all cheap" / "all mid" / "all expensive" baselines on the frontier.
    """
    return RoutingTable(
        tiers={"single": model},
        routes={
            "ambiguous_discrepancy": "single",
            "disagreement_writeup": "single",
            "disagreement_writeup_escalated": "single",
        },
    )


def run_cost_accuracy_frontier(
    golden: ReconciliationGolden,
    resolution_report: ResolutionReport,
    *,
    configs: dict[str, RoutingTable],
    provider_factory: Callable[[], LLMProvider],
) -> list[FrontierPoint]:
    """Run `golden.invoices` through the pipeline once per named routing
    config, holding entity resolution and the invoice corpus fixed.

    `provider_factory` is called fresh for each config so a
    stateful/seeded fake (e.g. one whose "accuracy" is simulated via an
    internal RNG) produces the same sequence of decisions in each config
    — the comparison isolates the routing table's effect, not RNG luck.
    """
    tool_server = KestrelToolServer(resolution_report, golden.dataset.psa_records)
    points: list[FrontierPoint] = []

    for name, routing in configs.items():
        store = StateStore(":memory:")
        guardrails = Guardrails(state_store=store, routing=routing, token_budget=10_000_000)
        provider = provider_factory()

        result = reconcile_invoices(
            golden.invoices,
            tool_server=tool_server,
            state_store=store,
            guardrails=guardrails,
            analyst_provider=provider,
            validator_provider=provider,
        )
        score = score_reconciliation(result, golden.true_discrepancy)
        cost_report = guardrails.cost_report()

        points.append(
            FrontierPoint(
                config_name=name,
                total_cost_usd=cost_report.actual_cost_usd,
                total_calls=cost_report.total_calls,
                accuracy=score.accuracy,
                detection_recall=score.detection_recall,
            )
        )
        store.close()

    return points


def render_frontier_table(points: list[FrontierPoint]) -> str:
    """A plain-text table suitable for a report or CI log."""
    header = f"{'config':<20} {'cost ($)':>10} {'calls':>7} {'accuracy':>10} {'recall':>8}"
    lines = [header, "-" * len(header)]
    for p in points:
        lines.append(
            f"{p.config_name:<20} {p.total_cost_usd:>10.4f} {p.total_calls:>7} "
            f"{p.accuracy:>10.3f} {p.detection_recall:>8.3f}"
        )
    return "\n".join(lines)
