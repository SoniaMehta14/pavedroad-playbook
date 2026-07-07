from collections.abc import Generator

import pytest

from adapters.base import Usage
from orchestration.guardrails import (
    BudgetExceededError,
    Guardrails,
    IterationCapExceededError,
)
from orchestration.routing import RoutingTable
from orchestration.state_store import StateStore


@pytest.fixture
def store() -> Generator[StateStore, None, None]:
    s = StateStore(":memory:")
    s.start_run("run-1", "invoice_reconciliation", token_budget=1000)
    yield s
    s.close()


@pytest.fixture
def routing() -> RoutingTable:
    return RoutingTable.load()


def test_route_returns_model_and_tier(store: StateStore, routing: RoutingTable) -> None:
    guardrails = Guardrails(state_store=store, routing=routing, token_budget=1000)
    model, tier = guardrails.route("ambiguous_discrepancy")
    assert model == "claude-haiku-4-5"
    assert tier == "cheap"


def test_check_iteration_within_cap_does_not_raise(
    store: StateStore, routing: RoutingTable
) -> None:
    guardrails = Guardrails(state_store=store, routing=routing, token_budget=1000)
    for _ in range(5):
        guardrails.check_iteration("task-1")  # default cap is 5 — should not raise


def test_check_iteration_exceeds_cap_raises(store: StateStore, routing: RoutingTable) -> None:
    guardrails = Guardrails(
        state_store=store, routing=routing, token_budget=1000, max_iterations_per_task=2
    )
    guardrails.check_iteration("task-1")
    guardrails.check_iteration("task-1")
    with pytest.raises(IterationCapExceededError):
        guardrails.check_iteration("task-1")


def test_check_iteration_is_scoped_per_task(store: StateStore, routing: RoutingTable) -> None:
    guardrails = Guardrails(
        state_store=store, routing=routing, token_budget=1000, max_iterations_per_task=1
    )
    guardrails.check_iteration("task-1")
    guardrails.check_iteration("task-2")  # different task, its own counter


def test_record_usage_updates_state_store_and_local_tracking(
    store: StateStore, routing: RoutingTable
) -> None:
    guardrails = Guardrails(state_store=store, routing=routing, token_budget=1000)
    guardrails.record_usage(
        "run-1", tier="cheap", usage=Usage(input_tokens=50, output_tokens=20, cost_usd=0.001)
    )

    run = store.get_run("run-1")
    assert run.tokens_used == 70
    assert run.cost_usd == pytest.approx(0.001)


def test_record_usage_over_budget_raises_but_still_records(
    store: StateStore, routing: RoutingTable
) -> None:
    guardrails = Guardrails(state_store=store, routing=routing, token_budget=100)
    with pytest.raises(BudgetExceededError):
        guardrails.record_usage(
            "run-1", tier="cheap", usage=Usage(input_tokens=80, output_tokens=80, cost_usd=0.01)
        )

    # The overage itself is still logged — a budget breach halts forward
    # progress, it doesn't hide the spend that already happened.
    run = store.get_run("run-1")
    assert run.tokens_used == 160


def test_cost_report_with_no_calls_has_zero_savings_pct(
    store: StateStore, routing: RoutingTable
) -> None:
    guardrails = Guardrails(state_store=store, routing=routing, token_budget=1000)
    report = guardrails.cost_report()
    assert report.total_calls == 0
    assert report.savings_pct == 0.0


def test_cost_report_cheap_tier_call_is_cheaper_than_opus_baseline(
    store: StateStore, routing: RoutingTable
) -> None:
    guardrails = Guardrails(state_store=store, routing=routing, token_budget=3_000_000)
    guardrails.record_usage(
        "run-1",
        tier="cheap",
        usage=Usage(input_tokens=1_000_000, output_tokens=1_000_000, cost_usd=6.0),
    )

    report = guardrails.cost_report()
    assert report.total_calls == 1
    assert report.actual_cost_usd == pytest.approx(6.0)
    # claude-opus-4-8 pricing: $5 + $25 per MTok = $30 for 1M in + 1M out
    assert report.all_opus_baseline_cost_usd == pytest.approx(30.0)
    assert report.savings_usd == pytest.approx(24.0)
    assert report.savings_pct == pytest.approx(80.0)
    assert report.by_tier["cheap"].calls == 1
