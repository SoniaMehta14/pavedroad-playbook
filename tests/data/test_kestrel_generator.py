"""Tests for the Kestrel synthetic data generator.

These tests check the generator's contract — determinism, realistic noise
rates, and ground-truth completeness — not any particular downstream
resolution behavior.
"""

from data.kestrel import generate_kestrel_dataset
from data.kestrel.generator import _INJECTION_PAYLOADS


def test_same_seed_produces_identical_corpus() -> None:
    a = generate_kestrel_dataset(seed=42)
    b = generate_kestrel_dataset(seed=42)
    assert a.model_dump() == b.model_dump()


def test_different_seed_produces_different_corpus() -> None:
    a = generate_kestrel_dataset(seed=42)
    b = generate_kestrel_dataset(seed=7)
    assert a.crm_records != b.crm_records


def test_canonical_customer_count() -> None:
    dataset = generate_kestrel_dataset(seed=42, n_customers=40)
    assert len(dataset.canonical_customers) == 40
    names = {c.canonical_name for c in dataset.canonical_customers}
    assert len(names) == 40  # no accidental collisions


def test_every_raw_record_has_a_ground_truth_link() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    crm_ids = {r.account_id for r in dataset.crm_records}
    billing_ids = {r.customer_id for r in dataset.billing_records}
    psa_ids = {r.job_id for r in dataset.psa_records}

    linked_crm = {link.record_id for link in dataset.ground_truth if link.system == "crm"}
    linked_billing = {link.record_id for link in dataset.ground_truth if link.system == "billing"}
    linked_psa = {link.record_id for link in dataset.ground_truth if link.system == "psa"}

    assert crm_ids == linked_crm
    assert billing_ids == linked_billing
    assert psa_ids == linked_psa


def test_billing_join_key_only_present_for_post_cutover_customers() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    by_canonical = {c.canonical_id: c for c in dataset.canonical_customers}
    canonical_by_billing = {
        link.record_id: link.canonical_id
        for link in dataset.ground_truth
        if link.system == "billing"
    }

    for record in dataset.billing_records:
        customer = by_canonical[canonical_by_billing[record.customer_id]]
        if customer.onboarded_year < 2021:
            assert record.crm_account_id is None


def test_some_psa_records_have_no_customer_name() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    missing = [r for r in dataset.psa_records if r.customer_name_raw is None]
    assert len(missing) > 0, "the PSA data must include the realistic unlinked-record case"


def test_injection_payloads_present_and_findable() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    found = [r for r in dataset.psa_records if r.equipment_description in _INJECTION_PAYLOADS]
    assert len(found) == 2, "exactly two deliberately-injected PSA records are expected"


def test_some_crm_customers_have_duplicate_rows() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    canonical_by_crm = {
        link.record_id: link.canonical_id for link in dataset.ground_truth if link.system == "crm"
    }
    counts: dict[str, int] = {}
    for record in dataset.crm_records:
        cid = canonical_by_crm[record.account_id]
        counts[cid] = counts.get(cid, 0) + 1
    assert any(count > 1 for count in counts.values())
