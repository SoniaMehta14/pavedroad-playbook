"""Tests for the reconciliation scorer.

Hand-crafted cases exercise the metric's exact arithmetic; the
real-pipeline test measures (does not assert a hand-picked number for)
the Analyst/Validator pipeline's actual achieved score.
"""

import pytest
from tests.support.fake_providers import (
    FakeReconciliationProvider,
    TopCandidateEntityResolutionProvider,
)

from evals.golden import build_reconciliation_golden
from evals.reconciliation import score_reconciliation
from interop.llm_resolution import LLMResolver
from interop.resolve import resolve_dataset
from interop.tools import KestrelToolServer
from orchestration.guardrails import Guardrails
from orchestration.pipeline import HumanReviewItem, ReconciliationRunResult, reconcile_invoices
from orchestration.routing import RoutingTable
from orchestration.state_store import StateStore


def _fake_decision(invoice_id: str, discrepancy: str) -> HumanReviewItem:
    from orchestration.models import AnalystProposal, ValidatorDecision

    return HumanReviewItem(
        invoice_id=invoice_id,
        analyst_proposal=AnalystProposal(
            invoice_id=invoice_id,
            matched_canonical_id=None,
            matched_job_id=None,
            discrepancy=discrepancy,  # type: ignore[arg-type]
            confidence=0.9,
            rationale="test",
            used_llm=False,
        ),
        validator_decision=ValidatorDecision(
            invoice_id=invoice_id,
            agrees=False,
            discrepancy=discrepancy,  # type: ignore[arg-type]
            rationale="test",
            used_llm=False,
        ),
    )


def test_perfect_predictions_score_1_0() -> None:
    result = ReconciliationRunResult(
        run_id="r1",
        workflow_name="invoice_reconciliation",
        status="completed",
        closed_invoice_ids=["INV-1", "INV-2"],
        human_review=[_fake_decision("INV-3", "amount_mismatch")],
        resume_index=3,
    )
    true_discrepancy = {"INV-1": "none", "INV-2": "none", "INV-3": "amount_mismatch"}

    score = score_reconciliation(result, true_discrepancy)

    assert score.accuracy == 1.0
    assert score.detection_precision == 1.0
    assert score.detection_recall == 1.0
    assert score.detection_f1 == 1.0


def test_false_positive_hurts_precision_not_recall() -> None:
    # INV-1 is truly clean but the pipeline escalated it anyway.
    result = ReconciliationRunResult(
        run_id="r1",
        workflow_name="invoice_reconciliation",
        status="completed",
        closed_invoice_ids=[],
        human_review=[_fake_decision("INV-1", "date_drift")],
        resume_index=1,
    )
    true_discrepancy = {"INV-1": "none"}

    score = score_reconciliation(result, true_discrepancy)

    assert score.detection_precision == 0.0
    assert score.detection_recall == 0.0  # no true discrepancies exist to recall
    assert score.accuracy == 0.0  # wrong exact label too


def test_false_negative_hurts_recall() -> None:
    # INV-1 truly has an amount mismatch but the pipeline closed it clean.
    result = ReconciliationRunResult(
        run_id="r1",
        workflow_name="invoice_reconciliation",
        status="completed",
        closed_invoice_ids=["INV-1"],
        human_review=[],
        resume_index=1,
    )
    true_discrepancy = {"INV-1": "amount_mismatch"}

    score = score_reconciliation(result, true_discrepancy)

    assert score.detection_recall == 0.0
    assert score.accuracy == 0.0


def test_exact_label_mismatch_hurts_accuracy_but_not_detection() -> None:
    # Correctly detected *a* discrepancy, but filed under the wrong reason.
    result = ReconciliationRunResult(
        run_id="r1",
        workflow_name="invoice_reconciliation",
        status="completed",
        closed_invoice_ids=[],
        human_review=[_fake_decision("INV-1", "unknown_customer")],
        resume_index=1,
    )
    true_discrepancy = {"INV-1": "amount_mismatch"}

    score = score_reconciliation(result, true_discrepancy)

    assert score.detection_precision == 1.0  # correctly flagged as *some* discrepancy
    assert score.detection_recall == 1.0
    assert score.accuracy == 0.0  # but the exact reason code is wrong


def test_mismatched_invoice_sets_raises() -> None:
    result = ReconciliationRunResult(
        run_id="r1",
        workflow_name="invoice_reconciliation",
        status="completed",
        closed_invoice_ids=["INV-1"],
        human_review=[],
        resume_index=1,
    )
    with pytest.raises(ValueError, match="must cover exactly the same invoices"):
        score_reconciliation(result, {"INV-999": "none"})


def test_real_pipeline_reconciliation_quality() -> None:
    """Measures, not asserts, the two-agent pipeline's actual achieved
    score against the real synthetic corpus — see
    tests/evals/test_regression_gates.py for the CI-enforced floor."""
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
    print(
        f"\nReconciliation: accuracy={score.accuracy:.3f} "
        f"detection_precision={score.detection_precision:.3f} "
        f"detection_recall={score.detection_recall:.3f} detection_f1={score.detection_f1:.3f} "
        f"({score.correctly_detected_discrepancies}/{score.true_discrepancies} "
        f"true discrepancies caught)"
    )
    store.close()
    assert 0.0 <= score.accuracy <= 1.0
