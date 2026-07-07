"""Tests for the pairwise entity-resolution scorer.

Hand-crafted cases exercise the metric's exact arithmetic; the real-corpus
test measures (does not assert a hand-picked number for) the resolution
pipeline's actual achieved score.
"""

from data.kestrel.models import GroundTruthLink
from tests.support.fake_providers import TopCandidateEntityResolutionProvider

from evals.entity_resolution import score_entity_resolution
from evals.golden import build_entity_resolution_golden
from interop.llm_resolution import LLMResolver
from interop.models import ResolutionOutcome
from interop.resolve import ResolutionReport
from interop.resolve import resolve_dataset as resolve_dataset_fn
from interop.review_queue import ReviewQueue


def _report(outcomes: list[ResolutionOutcome]) -> ResolutionReport:
    return ResolutionReport(unified_customers=[], outcomes=outcomes, review_queue=ReviewQueue())


def test_perfect_resolution_scores_1_0() -> None:
    ground_truth = [
        GroundTruthLink(canonical_id="KEST-1", system="crm", record_id="C1"),
        GroundTruthLink(canonical_id="KEST-1", system="billing", record_id="B1"),
    ]
    outcomes = [
        ResolutionOutcome(
            system="crm",
            record_id="C1",
            matched_canonical_id="X",
            confidence=1.0,
            method="exact_key",
        ),
        ResolutionOutcome(
            system="billing",
            record_id="B1",
            matched_canonical_id="X",
            confidence=1.0,
            method="exact_key",
        ),
    ]
    score = score_entity_resolution(_report(outcomes), ground_truth)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_completely_wrong_resolution_scores_0() -> None:
    ground_truth = [
        GroundTruthLink(canonical_id="KEST-1", system="crm", record_id="C1"),
        GroundTruthLink(canonical_id="KEST-1", system="billing", record_id="B1"),
        GroundTruthLink(canonical_id="KEST-2", system="crm", record_id="C2"),
        GroundTruthLink(canonical_id="KEST-2", system="billing", record_id="B2"),
    ]
    # Resolver groups C1 with B2 instead of B1 — wrong pairing entirely.
    outcomes = [
        ResolutionOutcome(
            system="crm",
            record_id="C1",
            matched_canonical_id="X",
            confidence=1.0,
            method="exact_key",
        ),
        ResolutionOutcome(
            system="billing",
            record_id="B2",
            matched_canonical_id="X",
            confidence=1.0,
            method="exact_key",
        ),
        ResolutionOutcome(
            system="crm",
            record_id="C2",
            matched_canonical_id="Y",
            confidence=1.0,
            method="exact_key",
        ),
        ResolutionOutcome(
            system="billing",
            record_id="B1",
            matched_canonical_id="Y",
            confidence=1.0,
            method="exact_key",
        ),
    ]
    score = score_entity_resolution(_report(outcomes), ground_truth)
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.f1 == 0.0


def test_unresolved_records_are_excluded_from_predicted_pairs() -> None:
    ground_truth = [
        GroundTruthLink(canonical_id="KEST-1", system="crm", record_id="C1"),
        GroundTruthLink(canonical_id="KEST-1", system="billing", record_id="B1"),
    ]
    outcomes = [
        ResolutionOutcome(
            system="crm",
            record_id="C1",
            matched_canonical_id=None,
            confidence=0.0,
            method="unresolved",
        ),
        ResolutionOutcome(
            system="billing",
            record_id="B1",
            matched_canonical_id=None,
            confidence=0.0,
            method="unresolved",
        ),
    ]
    score = score_entity_resolution(_report(outcomes), ground_truth)
    assert score.predicted_pairs == 0
    assert score.resolution_rate == 0.0


def test_resolution_rate_reflects_records_placed_in_any_cluster() -> None:
    ground_truth = [
        GroundTruthLink(canonical_id="KEST-1", system="crm", record_id="C1"),
        GroundTruthLink(canonical_id="KEST-1", system="billing", record_id="B1"),
    ]
    outcomes = [
        ResolutionOutcome(
            system="crm",
            record_id="C1",
            matched_canonical_id="X",
            confidence=1.0,
            method="exact_key",
        ),
        ResolutionOutcome(
            system="billing",
            record_id="B1",
            matched_canonical_id=None,
            confidence=0.0,
            method="unresolved",
        ),
    ]
    score = score_entity_resolution(_report(outcomes), ground_truth)
    assert score.resolved_record_count == 1
    assert score.total_record_count == 2
    assert score.resolution_rate == 0.5


def test_real_corpus_resolution_quality_deterministic_only() -> None:
    """Measures the deterministic-only mode's achieved score — a fully
    supported configuration (no LLM resolver at all), e.g. for a
    regulated deployment that cannot send customer data to a model."""
    golden = build_entity_resolution_golden(seed=42)
    report = resolve_dataset_fn(golden.crm_records, golden.billing_records, golden.psa_records)
    score = score_entity_resolution(report, golden.ground_truth)

    print(
        f"\nEntity resolution (deterministic only): precision={score.precision:.3f} "
        f"recall={score.recall:.3f} f1={score.f1:.3f} "
        f"resolution_rate={score.resolution_rate:.3f} "
        f"({score.resolved_record_count}/{score.total_record_count} records placed)"
    )
    assert 0.0 <= score.precision <= 1.0
    assert 0.0 <= score.recall <= 1.0


def test_real_corpus_resolution_quality_with_llm_assist() -> None:
    """Measures, not asserts, the deterministic-first-plus-LLM-assist
    pipeline's actual achieved score against the real synthetic corpus —
    the realistically-deployed configuration. See
    tests/evals/test_regression_gates.py for the CI-enforced floor."""
    golden = build_entity_resolution_golden(seed=42)
    report = resolve_dataset_fn(
        golden.crm_records,
        golden.billing_records,
        golden.psa_records,
        llm_resolver=LLMResolver(TopCandidateEntityResolutionProvider()),
    )
    score = score_entity_resolution(report, golden.ground_truth)

    print(
        f"\nEntity resolution (with LLM assist): precision={score.precision:.3f} "
        f"recall={score.recall:.3f} f1={score.f1:.3f} "
        f"resolution_rate={score.resolution_rate:.3f} "
        f"({score.resolved_record_count}/{score.total_record_count} records placed)"
    )
    assert 0.0 <= score.precision <= 1.0
    assert 0.0 <= score.recall <= 1.0
