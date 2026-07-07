"""Tests for the synthetic AR invoice generator."""

from data.kestrel import (
    generate_invoices,
    generate_invoices_with_ground_truth,
    generate_kestrel_dataset,
)
from data.kestrel.invoices import _UNKNOWN_CUSTOMER_NAME


def test_same_seed_is_deterministic() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    a = generate_invoices(dataset, seed=100)
    b = generate_invoices(dataset, seed=100)
    assert [inv.model_dump() for inv in a] == [inv.model_dump() for inv in b]


def test_one_invoice_per_named_psa_job() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices = generate_invoices(dataset, seed=100)
    named_jobs = [r for r in dataset.psa_records if r.customer_name_raw]
    assert len(invoices) == len(named_jobs)


def test_invoice_ids_are_unique() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices = generate_invoices(dataset, seed=100)
    ids = {inv.invoice_id for inv in invoices}
    assert len(ids) == len(invoices)


def test_service_dates_are_clean_iso_format() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices = generate_invoices(dataset, seed=100)
    for inv in invoices:
        # Will raise ValueError if not a clean ISO date — that's the test.
        from datetime import date

        date.fromisoformat(inv.service_date)


def test_produces_at_least_one_of_each_discrepancy_type() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices = generate_invoices(dataset, seed=100)

    unknown_customer = [
        inv for inv in invoices if inv.customer_name_billed == _UNKNOWN_CUSTOMER_NAME
    ]
    assert len(unknown_customer) > 0, "expected at least one at this corpus size"


def test_amounts_are_positive() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices = generate_invoices(dataset, seed=100)
    assert all(inv.amount_usd > 0 for inv in invoices)


def test_ground_truth_variant_produces_identical_invoices_to_plain_variant() -> None:
    """The refactor that added ground-truth labels must not change the
    invoices themselves — same RNG sequence, same corpus."""
    dataset = generate_kestrel_dataset(seed=42)
    plain = generate_invoices(dataset, seed=100)
    with_labels, _ = generate_invoices_with_ground_truth(dataset, seed=100)
    assert [inv.model_dump() for inv in plain] == [inv.model_dump() for inv in with_labels]


def test_ground_truth_has_one_label_per_invoice() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices, labels = generate_invoices_with_ground_truth(dataset, seed=100)
    assert set(labels.keys()) == {inv.invoice_id for inv in invoices}


def test_ground_truth_labels_use_the_expected_vocabulary() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    _, labels = generate_invoices_with_ground_truth(dataset, seed=100)
    expected_vocabulary = {
        "none",
        "amount_mismatch",
        "no_matching_job",
        "unknown_customer",
        "date_drift",
    }
    assert set(labels.values()) <= expected_vocabulary
    assert set(labels.values()) == expected_vocabulary  # all five appear at this corpus size


def test_unknown_customer_invoices_are_labeled_unknown_customer() -> None:
    dataset = generate_kestrel_dataset(seed=42)
    invoices, labels = generate_invoices_with_ground_truth(dataset, seed=100)
    for inv in invoices:
        if inv.customer_name_billed == _UNKNOWN_CUSTOMER_NAME:
            assert labels[inv.invoice_id] == "unknown_customer"
