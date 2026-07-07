"""Tests for the unified tool-calling interface.

test_injection_payload_reaches_tool_output_flagged_not_silently_passed is
the required demonstration: a PSA record carrying one of the synthetic
dataset's real injection payloads (data/kestrel/generator.py's
_INJECTION_PAYLOADS — not a string invented for this test) comes back
through get_customer_jobs flagged, never as an unflagged pass-through an
agent might act on.
"""

import pytest
from data.kestrel import generate_kestrel_dataset
from data.kestrel.generator import _INJECTION_PAYLOADS
from data.kestrel.models import KestrelDataset, PSAJobRecord
from pydantic import ValidationError

from interop.models import ResolutionOutcome, UnifiedCustomer
from interop.resolve import ResolutionReport, resolve_dataset
from interop.review_queue import ReviewQueue
from interop.tools import (
    TOOL_DEFINITIONS,
    CustomerJobsInput,
    CustomerLookupInput,
    KestrelToolServer,
    ReviewQueueInput,
)


def _build_server(seed: int = 42) -> tuple[KestrelToolServer, KestrelDataset, ResolutionReport]:
    dataset = generate_kestrel_dataset(seed=seed)
    report = resolve_dataset(dataset.crm_records, dataset.billing_records, dataset.psa_records)
    return KestrelToolServer(report, dataset.psa_records), dataset, report


def test_lookup_customer_finds_a_known_customer_by_exact_name() -> None:
    server, dataset, _ = _build_server()
    target = dataset.canonical_customers[0]

    result = server.lookup_customer(CustomerLookupInput(query=target.canonical_name))

    assert any(m.name == target.canonical_name for m in result.matches)


def test_lookup_customer_input_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        CustomerLookupInput(query="")


def test_customer_jobs_input_rejects_overlong_id() -> None:
    with pytest.raises(ValidationError):
        CustomerJobsInput(canonical_id="x" * 100)


def test_review_queue_input_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        ReviewQueueInput(status="archived")


def test_get_customer_jobs_returns_sanitized_equipment_descriptions() -> None:
    _, _, report = _build_server()
    dataset = generate_kestrel_dataset(seed=42)
    server = KestrelToolServer(report, dataset.psa_records)

    canonical_with_jobs = next(
        c.canonical_id for c in report.unified_customers if "psa" in c.source_record_ids
    )
    result = server.get_customer_jobs(CustomerJobsInput(canonical_id=canonical_with_jobs))

    assert len(result.jobs) > 0
    for job in result.jobs:
        assert len(job.equipment_description) <= 500  # sanitize's default cap


def test_unknown_canonical_id_returns_empty_job_list_not_an_error() -> None:
    server, _, _ = _build_server()
    result = server.get_customer_jobs(CustomerJobsInput(canonical_id="UNIFIED-9999"))
    assert result.jobs == []


def test_review_queue_tool_lists_pending_items() -> None:
    server, _, report = _build_server()
    result = server.list_review_queue(ReviewQueueInput(status="pending"))
    assert len(result.items) == len(report.review_queue.pending())
    assert len(result.items) > 0  # sanity: the real corpus does produce review items


def test_tool_definitions_are_valid_json_schema_shaped() -> None:
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"lookup_customer", "get_customer_jobs", "list_review_queue"}
    for tool in TOOL_DEFINITIONS:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"


def test_injection_payload_reaches_tool_output_flagged_not_silently_passed() -> None:
    """The neutralization demonstration, built from real generator payloads
    against a hand-built resolution report — deterministic and independent
    of whether the RNG-driven full pipeline happens to resolve these
    specific records on a given seed."""
    for payload in _INJECTION_PAYLOADS:
        injected_record = PSAJobRecord(
            job_id="PSA-INJECT-TEST",
            customer_name_raw="Blue Ridge Equipment Rental",
            equipment_description=payload,
            scheduled_date="1/1/2022",
        )
        unified_customer = UnifiedCustomer(
            canonical_id="UNIFIED-0001",
            name="Blue Ridge Equipment Rental",
            source_record_ids={"psa": [injected_record.job_id]},
        )
        outcome = ResolutionOutcome(
            system="psa",
            record_id=injected_record.job_id,
            matched_canonical_id=unified_customer.canonical_id,
            confidence=1.0,
            method="exact_name",
        )
        report = ResolutionReport(
            unified_customers=[unified_customer], outcomes=[outcome], review_queue=ReviewQueue()
        )
        server = KestrelToolServer(report, [injected_record])

        result = server.get_customer_jobs(CustomerJobsInput(canonical_id="UNIFIED-0001"))

        assert len(result.jobs) == 1
        job = result.jobs[0]
        assert job.flagged is True, f"payload should have been flagged: {payload!r}"
        # The data is preserved (this is a real field, not hidden from the
        # caller) but it comes back as plain text data, never executed.
        assert isinstance(job.equipment_description, str)


def test_generated_dataset_still_contains_the_injection_payloads() -> None:
    """Guards against the generator's injection scenario silently
    disappearing in a future refactor of data/kestrel/generator.py."""
    dataset = generate_kestrel_dataset(seed=42)
    found = [r for r in dataset.psa_records if r.equipment_description in _INJECTION_PAYLOADS]
    assert len(found) == 2
