"""Integration tests for the full resolution pipeline, run against the real
Kestrel synthetic dataset (not hand-crafted fixtures) — this is where we
check the pipeline behaves sensibly end-to-end, not that any single
threshold band is exactly right (that's test_deterministic.py's job).
"""

from data.kestrel import generate_kestrel_dataset
from tests.support.fake_providers import TopCandidateEntityResolutionProvider

from interop.llm_resolution import LLMResolver
from interop.resolve import resolve_dataset


def test_every_crm_record_resolves() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    report = resolve_dataset(dataset.crm_records, [], [])

    crm_outcomes = [o for o in report.outcomes if o.system == "crm"]
    assert len(crm_outcomes) == len(dataset.crm_records)
    assert all(o.matched_canonical_id is not None for o in crm_outcomes)


def test_post_cutover_billing_records_resolve_via_exact_key() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    report = resolve_dataset(dataset.crm_records, dataset.billing_records, [])

    exact_key_hits = [o for o in report.outcomes if o.method == "exact_key"]
    assert len(exact_key_hits) > 0


def test_psa_records_missing_a_name_land_in_review_queue() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    report = resolve_dataset(dataset.crm_records, dataset.billing_records, dataset.psa_records)

    nameless_psa = [r for r in dataset.psa_records if r.customer_name_raw is None]
    assert len(nameless_psa) > 0  # sanity: the generator does produce this case

    review_record_ids = {item.record_id for item in report.review_queue.pending()}
    for record in nameless_psa:
        assert record.job_id in review_record_ids


def test_llm_resolver_reduces_review_queue_size_versus_deterministic_only() -> None:
    dataset = generate_kestrel_dataset(seed=42)

    without_llm = resolve_dataset(dataset.crm_records, dataset.billing_records, dataset.psa_records)
    with_llm = resolve_dataset(
        dataset.crm_records,
        dataset.billing_records,
        dataset.psa_records,
        llm_resolver=LLMResolver(TopCandidateEntityResolutionProvider()),
    )

    assert len(with_llm.review_queue) <= len(without_llm.review_queue)
    llm_resolved = [o for o in with_llm.outcomes if o.method == "llm"]
    assert len(llm_resolved) > 0


def test_no_outcome_is_ever_dropped() -> None:
    """Every raw record produces exactly one outcome — resolved or not."""
    dataset = generate_kestrel_dataset(seed=42)
    report = resolve_dataset(dataset.crm_records, dataset.billing_records, dataset.psa_records)

    expected_total = (
        len(dataset.crm_records) + len(dataset.billing_records) + len(dataset.psa_records)
    )
    assert len(report.outcomes) == expected_total
