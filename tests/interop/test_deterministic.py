"""Deterministic matcher tests using hand-crafted fixtures.

Hand-crafted rather than the real generator, so each threshold band
(exact key, exact name, fuzzy auto-accept, ambiguous residual, no
candidate) is exercised precisely rather than depending on what the
generator's RNG happens to produce.
"""

from data.kestrel.models import BillingCustomerRecord, CRMAccountRecord, PSAJobRecord

from interop.deterministic import EXACT_NAME_CONFIDENCE, FUZZY_AUTO_ACCEPT, DeterministicMatcher
from interop.normalize import name_similarity


def _crm(account_id: str, name: str) -> CRMAccountRecord:
    return CRMAccountRecord(account_id=account_id, account_name=name, created_date="2022-01-01")


def _billing(
    customer_id: str, name: str, crm_account_id: str | None = None
) -> BillingCustomerRecord:
    return BillingCustomerRecord(
        customer_id=customer_id,
        customer_name=name,
        crm_account_id=crm_account_id,
        signup_date="1/1/2022",
    )


def _psa(job_id: str, name: str | None) -> PSAJobRecord:
    return PSAJobRecord(
        job_id=job_id,
        customer_name_raw=name,
        equipment_description="CAT 320 Excavator",
        scheduled_date="1/1/2022",
    )


def test_crm_duplicate_row_merges_into_same_canonical_entity() -> None:
    matcher = DeterministicMatcher()
    outcomes = matcher.resolve_crm_self(
        [
            _crm("001", "Blue Ridge Equipment Rental"),
            _crm("001D", "Blue Ridge Equipment Rental"),  # exact duplicate
        ]
    )
    assert outcomes[0].method == "new_entity"
    assert outcomes[1].method == "exact_name"
    assert outcomes[0].matched_canonical_id == outcomes[1].matched_canonical_id
    assert len(matcher.registry) == 1
    assert matcher.registry[0].source_record_ids["crm"] == ["001", "001D"]


def test_two_distinct_crm_customers_stay_separate() -> None:
    matcher = DeterministicMatcher()
    matcher.resolve_crm_self(
        [_crm("001", "Blue Ridge Equipment Rental"), _crm("002", "Coastal Crane Services")]
    )
    assert len(matcher.registry) == 2


def test_billing_exact_key_match_is_free_and_certain() -> None:
    matcher = DeterministicMatcher()
    matcher.resolve_crm_self([_crm("001", "Blue Ridge Equipment Rental")])

    outcome, candidates = matcher.resolve_billing_record(
        _billing("QB-1", "Blue Rdg Eqp", crm_account_id="001")
    )

    assert outcome.method == "exact_key"
    assert outcome.confidence == 1.0
    assert candidates == []  # exact key never needed to compute name candidates


def test_billing_no_key_falls_back_to_name_matching_auto_accept() -> None:
    matcher = DeterministicMatcher()
    matcher.resolve_crm_self([_crm("001", "Blue Ridge Equipment Rental")])

    # "Eqpt" expands to "Equipment" during normalization, so this is
    # actually a byte-identical normalized match (exact_name) — the point
    # of this test is that the absent crm_account_id key doesn't block
    # resolution, not which specific auto-accept method labels it.
    outcome, _ = matcher.resolve_billing_record(_billing("QB-1", "Blue Ridge Eqpt Rental"))

    assert outcome.matched_canonical_id is not None
    assert outcome.method in {"exact_name", "fuzzy_name"}
    assert outcome.confidence >= 0.85


def test_billing_typo_variant_resolves_as_fuzzy_not_exact() -> None:
    matcher = DeterministicMatcher()
    reference_name = "Blue Ridge Equipment Rental"
    matcher.resolve_crm_self([_crm("001", reference_name)])

    variant_name = "Blue Ridge Heavy Equipment Rental"
    score = name_similarity(variant_name, reference_name)
    assert FUZZY_AUTO_ACCEPT <= score < EXACT_NAME_CONFIDENCE, (
        "fixture must land in the fuzzy-but-not-exact band for this test to mean anything; "
        f"got {score}"
    )

    outcome, _ = matcher.resolve_billing_record(_billing("QB-1", variant_name))

    assert outcome.method == "fuzzy_name"
    assert outcome.confidence == score


def test_psa_ambiguous_name_is_unresolved_but_returns_candidates_for_escalation() -> None:
    matcher = DeterministicMatcher()
    matcher.resolve_crm_self([_crm("001", "Blue Ridge Equipment Rental Partners")])

    # Deliberately weak: shares only two words with the registry entry.
    outcome, candidates = matcher.resolve_psa_record(_psa("PSA-1", "Blue Ridge job"))

    assert outcome.matched_canonical_id is None
    assert outcome.method == "unresolved"
    assert len(candidates) > 0  # a weak signal, not zero signal


def test_psa_record_with_no_customer_name_has_no_candidates_at_all() -> None:
    matcher = DeterministicMatcher()
    matcher.resolve_crm_self([_crm("001", "Blue Ridge Equipment Rental")])

    outcome, candidates = matcher.resolve_psa_record(_psa("PSA-1", None))

    assert outcome.matched_canonical_id is None
    assert candidates == []


def test_unrelated_psa_name_against_small_registry_is_unresolved() -> None:
    matcher = DeterministicMatcher()
    matcher.resolve_crm_self([_crm("001", "Blue Ridge Equipment Rental")])

    outcome, _ = matcher.resolve_psa_record(_psa("PSA-1", "Zephyr Aviation Consulting"))

    assert outcome.matched_canonical_id is None
