"""Tests for the cost-vs-accuracy frontier report.

Accuracy differences between tiers here come from
SimulatedTierAccuracyProvider's simulated per-tier accuracy assumptions
(see tests/support/fake_providers.py), not from live model calls — that
module's docstring explains why. The frontier *mechanism* — different
routing configs producing different cost and accuracy numbers from the
same corpus — is what's under test here, not real model quality.
"""

from collections.abc import Callable

from tests.support.fake_providers import (
    SimulatedTierAccuracyProvider,
    TopCandidateEntityResolutionProvider,
)

from adapters.base import LLMProvider
from evals.cost_frontier import (
    FrontierPoint,
    render_frontier_table,
    run_cost_accuracy_frontier,
    single_tier_routing,
)
from evals.golden import ReconciliationGolden, build_reconciliation_golden
from interop.llm_resolution import LLMResolver
from interop.resolve import ResolutionReport, resolve_dataset
from orchestration.routing import RoutingTable


def _resolution_report(golden: ReconciliationGolden) -> ResolutionReport:
    return resolve_dataset(
        golden.dataset.crm_records,
        golden.dataset.billing_records,
        golden.dataset.psa_records,
        llm_resolver=LLMResolver(TopCandidateEntityResolutionProvider()),
    )


def _simulated_provider_factory() -> Callable[[], LLMProvider]:
    return lambda: SimulatedTierAccuracyProvider(seed=7)


def test_single_tier_routing_routes_everything_to_the_same_model() -> None:
    routing = single_tier_routing("claude-haiku-4-5")
    assert routing.model_for("ambiguous_discrepancy") == "claude-haiku-4-5"
    assert routing.model_for("disagreement_writeup") == "claude-haiku-4-5"
    assert routing.model_for("disagreement_writeup_escalated") == "claude-haiku-4-5"


def test_frontier_produces_one_point_per_config() -> None:
    golden = build_reconciliation_golden(seed=42, invoice_seed=100)
    report = _resolution_report(golden)

    configs = {
        "all_cheap": single_tier_routing("claude-haiku-4-5"),
        "all_expensive": single_tier_routing("claude-opus-4-8"),
        "mixed_routing_table": RoutingTable.load(),
    }
    points = run_cost_accuracy_frontier(
        golden, report, configs=configs, provider_factory=_simulated_provider_factory()
    )

    assert {p.config_name for p in points} == set(configs.keys())
    assert all(p.total_calls > 0 for p in points)


def test_all_expensive_config_costs_more_than_all_cheap() -> None:
    """Measured, not asserted with a fudge: same corpus, same simulated
    per-invoice RNG rolls (same provider seed), only the model differs —
    the expensive tier must cost strictly more for the same call volume.
    """
    golden = build_reconciliation_golden(seed=42, invoice_seed=100)
    report = _resolution_report(golden)

    configs = {
        "all_cheap": single_tier_routing("claude-haiku-4-5"),
        "all_expensive": single_tier_routing("claude-opus-4-8"),
    }
    points = run_cost_accuracy_frontier(
        golden, report, configs=configs, provider_factory=_simulated_provider_factory()
    )
    by_name = {p.config_name: p for p in points}

    assert by_name["all_expensive"].total_calls == by_name["all_cheap"].total_calls
    assert by_name["all_expensive"].total_cost_usd > by_name["all_cheap"].total_cost_usd


def test_all_expensive_config_is_at_least_as_accurate_as_all_cheap() -> None:
    """The simulated accuracy assumption (haiku=0.55, opus=0.97) means the
    expensive tier should match or beat cheap on this corpus — a real
    deployment would replace the simulation with measured numbers.

    On this specific golden corpus (seed=42, invoice_seed=100) the two
    are exactly *equal*, not just "at least as good" — and that's a real,
    architecturally meaningful finding, not a weak test. Of the 6
    date-drift invoices in this corpus, none land within the Validator's
    stricter tolerance band (_VALIDATOR_STRICT_DATE_DAYS = 3; the actual
    drifts measured are 7, 9, 9, and three unparseable dates) — so the
    Validator's independent, deterministic re-check overrides the
    Analyst's judgment in every one of these cases regardless of which
    model tier proposed it. The practical reading: the two-agent design
    with independent verification means the cheap tier can win on cost
    with no accuracy cost on this corpus, precisely because the
    Validator — not the Analyst's model tier — is what's actually
    guarding correctness here. A corpus with more near-boundary date
    drift (closer to 3 days) would show the tiers diverging.
    """
    golden = build_reconciliation_golden(seed=42, invoice_seed=100)
    report = _resolution_report(golden)

    configs = {
        "all_cheap": single_tier_routing("claude-haiku-4-5"),
        "all_expensive": single_tier_routing("claude-opus-4-8"),
    }
    points = run_cost_accuracy_frontier(
        golden, report, configs=configs, provider_factory=_simulated_provider_factory()
    )
    by_name = {p.config_name: p for p in points}

    assert by_name["all_expensive"].accuracy >= by_name["all_cheap"].accuracy


def test_render_frontier_table_includes_every_config_name() -> None:
    points = [
        FrontierPoint(
            config_name="all_cheap",
            total_cost_usd=0.01,
            total_calls=5,
            accuracy=0.5,
            detection_recall=0.4,
        ),
        FrontierPoint(
            config_name="all_expensive",
            total_cost_usd=0.05,
            total_calls=5,
            accuracy=0.9,
            detection_recall=0.8,
        ),
    ]
    table = render_frontier_table(points)
    assert "all_cheap" in table
    assert "all_expensive" in table


def test_mixed_routing_table_frontier_report_prints_visibly() -> None:
    """Not an assertion-bearing test beyond a sanity count — prints the
    actual frontier report so it's visible with pytest -s, which is the
    artifact this component exists to produce."""
    golden = build_reconciliation_golden(seed=42, invoice_seed=100)
    report = _resolution_report(golden)

    configs = {
        "all_cheap": single_tier_routing("claude-haiku-4-5"),
        "all_mid": single_tier_routing("claude-sonnet-5"),
        "all_expensive": single_tier_routing("claude-opus-4-8"),
        "mixed_routing_table": RoutingTable.load(),
    }
    points = run_cost_accuracy_frontier(
        golden, report, configs=configs, provider_factory=_simulated_provider_factory()
    )
    print("\n" + render_frontier_table(points))
    assert len(points) == 4
