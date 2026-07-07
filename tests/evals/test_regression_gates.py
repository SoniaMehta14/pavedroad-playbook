"""CI regression gate: evals must pass before merge.

Every threshold here was set by running the eval and reading the actual
number off — see the sibling test files' printed output for exactly what
was measured (deterministic-only entity resolution: precision=0.632,
recall=0.259, f1=0.367; reconciliation with LLM-assisted entity
resolution: accuracy=0.471, detection_recall=0.143). Floors are set
below those measurements with margin, so this gate catches a future
regression in matching or reconciliation logic without being flaky on
day one.

Gated on the deterministic-only entity resolution configuration
specifically, not the LLM-assisted one — deterministic mode has no
fake-provider-quality confound and produces the exact same number on
every run, which is what a CI gate needs.

To raise these floors: improve the matching logic, re-run
tests/evals/test_entity_resolution.py and test_reconciliation.py with
-s to read the new numbers, then move the floor up with margin — never
move it down to make a regression pass.
"""

import pytest
from tests.support.fake_providers import (
    FakeReconciliationProvider,
    TopCandidateEntityResolutionProvider,
)

from evals.entity_resolution import score_entity_resolution
from evals.golden import build_entity_resolution_golden, build_reconciliation_golden
from evals.reconciliation import score_reconciliation
from interop.llm_resolution import LLMResolver
from interop.resolve import resolve_dataset
from interop.tools import KestrelToolServer
from orchestration.guardrails import Guardrails
from orchestration.pipeline import reconcile_invoices
from orchestration.routing import RoutingTable
from orchestration.state_store import StateStore

# Entity resolution floors (deterministic-only, measured 0.632 / 0.259 / 0.367)
_MIN_ENTITY_RESOLUTION_PRECISION = 0.55
_MIN_ENTITY_RESOLUTION_RECALL = 0.20
_MIN_ENTITY_RESOLUTION_F1 = 0.30

# Reconciliation floors (with LLM-assisted entity resolution, measured 0.471 / 0.143)
_MIN_RECONCILIATION_ACCURACY = 0.35
_MIN_RECONCILIATION_DETECTION_RECALL = 0.10


@pytest.mark.eval_gate
def test_entity_resolution_meets_the_regression_floor() -> None:
    golden = build_entity_resolution_golden(seed=42)
    report = resolve_dataset(golden.crm_records, golden.billing_records, golden.psa_records)
    score = score_entity_resolution(report, golden.ground_truth)

    assert score.precision >= _MIN_ENTITY_RESOLUTION_PRECISION, (
        f"entity resolution precision regressed: {score.precision:.3f} < "
        f"{_MIN_ENTITY_RESOLUTION_PRECISION}"
    )
    assert score.recall >= _MIN_ENTITY_RESOLUTION_RECALL, (
        f"entity resolution recall regressed: {score.recall:.3f} < {_MIN_ENTITY_RESOLUTION_RECALL}"
    )
    assert score.f1 >= _MIN_ENTITY_RESOLUTION_F1, (
        f"entity resolution F1 regressed: {score.f1:.3f} < {_MIN_ENTITY_RESOLUTION_F1}"
    )


@pytest.mark.eval_gate
def test_reconciliation_meets_the_regression_floor() -> None:
    golden = build_reconciliation_golden(seed=42, invoice_seed=100)
    report = resolve_dataset(
        golden.dataset.crm_records,
        golden.dataset.billing_records,
        golden.dataset.psa_records,
        llm_resolver=LLMResolver(TopCandidateEntityResolutionProvider()),
    )
    tool_server = KestrelToolServer(report, golden.dataset.psa_records)
    store = StateStore(":memory:")
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=10_000_000)
    provider = FakeReconciliationProvider()

    result = reconcile_invoices(
        golden.invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=provider,
        validator_provider=provider,
    )
    assert result.status == "completed"
    score = score_reconciliation(result, golden.true_discrepancy)
    store.close()

    assert score.accuracy >= _MIN_RECONCILIATION_ACCURACY, (
        f"reconciliation accuracy regressed: {score.accuracy:.3f} < {_MIN_RECONCILIATION_ACCURACY}"
    )
    assert score.detection_recall >= _MIN_RECONCILIATION_DETECTION_RECALL, (
        f"reconciliation discrepancy-detection recall regressed: "
        f"{score.detection_recall:.3f} < {_MIN_RECONCILIATION_DETECTION_RECALL}"
    )
