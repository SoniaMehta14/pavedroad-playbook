"""End-to-end tests for the invoice reconciliation pipeline.

test_reconciliation_routing_saves_money_versus_all_opus_baseline is the
required demonstration: messy synthetic data in, reconciled invoices out,
and a cost report computed from real per-call token counts showing the
routing table's savings against an all-Opus baseline — measured, not
asserted with a hardcoded percentage.
"""

from data.kestrel import generate_invoices, generate_kestrel_dataset
from data.kestrel.invoices import InvoiceLineItem
from tests.support.fake_providers import FakeReconciliationProvider

from interop.resolve import resolve_dataset
from interop.tools import KestrelToolServer
from orchestration.guardrails import Guardrails
from orchestration.pipeline import reconcile_invoices, resume_reconciliation
from orchestration.routing import RoutingTable
from orchestration.state_store import StateStore


def _build_pipeline_inputs() -> tuple[KestrelToolServer, list[InvoiceLineItem]]:
    dataset = generate_kestrel_dataset(seed=42)
    report = resolve_dataset(dataset.crm_records, dataset.billing_records, dataset.psa_records)
    tool_server = KestrelToolServer(report, dataset.psa_records)
    invoices = generate_invoices(dataset, seed=100)
    return tool_server, invoices


def test_every_invoice_ends_up_closed_or_in_human_review() -> None:
    tool_server, invoices = _build_pipeline_inputs()
    store = StateStore(":memory:")
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=10_000_000)
    provider = FakeReconciliationProvider()

    result = reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=provider,
        validator_provider=provider,
    )

    assert result.status == "completed"
    assert len(result.closed_invoice_ids) + len(result.human_review) == len(invoices)
    assert len(result.closed_invoice_ids) > 0
    assert len(result.human_review) > 0  # the synthetic data guarantees some real discrepancies
    store.close()


def test_state_store_has_a_transition_log_for_every_invoice() -> None:
    tool_server, invoices = _build_pipeline_inputs()
    store = StateStore(":memory:")
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=10_000_000)
    provider = FakeReconciliationProvider()

    result = reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=provider,
        validator_provider=provider,
    )

    transitions = store.transitions_for_run(result.run_id)
    task_ids_seen = {t.task_id for t in transitions}
    assert task_ids_seen == {inv.invoice_id for inv in invoices}
    store.close()


def test_reconciliation_routing_saves_money_versus_all_opus_baseline() -> None:
    """The required end-to-end demonstration: measure actual routing cost
    against a same-token-count all-Opus baseline, don't assert a
    hardcoded percentage."""
    tool_server, invoices = _build_pipeline_inputs()
    store = StateStore(":memory:")
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=10_000_000)
    provider = FakeReconciliationProvider()

    result = reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=provider,
        validator_provider=provider,
    )
    assert result.status == "completed"

    report = guardrails.cost_report()
    assert report.total_calls > 0, "the synthetic corpus must produce at least one LLM call"
    assert report.actual_cost_usd < report.all_opus_baseline_cost_usd
    assert report.savings_pct > 0

    tier_counts = {tier: spend.calls for tier, spend in report.by_tier.items()}
    print(
        f"\nCost report: {report.total_calls} LLM calls, "
        f"${report.actual_cost_usd:.4f} actual vs ${report.all_opus_baseline_cost_usd:.4f} "
        f"all-Opus baseline ({report.savings_pct:.1f}% saved). By tier: {tier_counts}"
    )
    store.close()


def test_budget_breach_halts_gracefully_with_a_resumable_checkpoint() -> None:
    tool_server, invoices = _build_pipeline_inputs()
    store = StateStore(":memory:")
    # A tiny budget guarantees a breach partway through a corpus this size.
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=300)
    provider = FakeReconciliationProvider()

    result = reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=provider,
        validator_provider=provider,
    )

    assert result.status == "halted"
    assert result.resume_index < len(invoices)
    assert store.get_run(result.run_id).status == "halted"
    store.close()


def test_resume_reconciliation_continues_without_reprocessing_closed_invoices() -> None:
    tool_server, invoices = _build_pipeline_inputs()
    store = StateStore(":memory:")
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=300)
    provider = FakeReconciliationProvider()

    first = reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=provider,
        validator_provider=provider,
    )
    assert first.status == "halted"

    # Fresh guardrails with headroom to finish the rest — same state
    # store, same run_id, so resume reads the real checkpoint.
    guardrails_resumed = Guardrails(
        state_store=store, routing=RoutingTable.load(), token_budget=10_000_000
    )
    final = resume_reconciliation(
        first.run_id,
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails_resumed,
        analyst_provider=provider,
        validator_provider=provider,
    )

    assert final.status == "completed"
    assert set(first.closed_invoice_ids).isdisjoint(set(final.closed_invoice_ids))

    total_before = len(first.closed_invoice_ids) + len(first.human_review)
    total_after = len(final.closed_invoice_ids) + len(final.human_review)
    assert total_before + total_after == len(invoices)
    store.close()
