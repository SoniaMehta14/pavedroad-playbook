"""Deterministic-first, LLM-second, human-last entity resolution pipeline.

Ties DeterministicMatcher, the optional LLMResolver, and the ReviewQueue
into the cascade described in
docs/architecture/0001-deterministic-first-entity-resolution.md: try free
and fast first, spend tokens only on the ambiguous residual, and never let
a low-confidence guess — machine or human-pending — silently become a
"fact" in the unified customer registry.
"""

from data.kestrel.models import BillingCustomerRecord, CRMAccountRecord, PSAJobRecord

from .deterministic import FUZZY_LLM_FLOOR, DeterministicMatcher
from .llm_resolution import LLMResolver
from .models import MatchCandidate, ResolutionOutcome, UnifiedCustomer
from .review_queue import ReviewQueue

# LLM-proposed matches below this confidence still land in the review
# queue rather than being auto-applied — an LLM's own uncertainty is a
# signal too, not just its final answer.
LLM_ACCEPT_THRESHOLD = 0.75


class ResolutionReport:
    """Bundles the outputs of a full resolution run."""

    def __init__(
        self,
        unified_customers: list[UnifiedCustomer],
        outcomes: list[ResolutionOutcome],
        review_queue: ReviewQueue,
    ) -> None:
        self.unified_customers = unified_customers
        self.outcomes = outcomes
        self.review_queue = review_queue


def resolve_dataset(
    crm_records: list[CRMAccountRecord],
    billing_records: list[BillingCustomerRecord],
    psa_records: list[PSAJobRecord],
    *,
    llm_resolver: LLMResolver | None = None,
) -> ResolutionReport:
    matcher = DeterministicMatcher()
    review_queue = ReviewQueue()
    outcomes: list[ResolutionOutcome] = []

    outcomes.extend(matcher.resolve_crm_self(crm_records))

    for billing_record in billing_records:
        outcome, candidates = matcher.resolve_billing_record(billing_record)
        outcomes.append(
            _escalate_if_needed(
                outcome,
                candidates,
                matcher,
                llm_resolver,
                review_queue,
                system="billing",
                record_display=f"{billing_record.customer_name} ({billing_record.customer_id})",
            )
        )

    for psa_record in psa_records:
        outcome, candidates = matcher.resolve_psa_record(psa_record)
        psa_name = psa_record.customer_name_raw or "(no name)"
        outcomes.append(
            _escalate_if_needed(
                outcome,
                candidates,
                matcher,
                llm_resolver,
                review_queue,
                system="psa",
                record_display=f"{psa_name} ({psa_record.job_id})",
            )
        )

    return ResolutionReport(matcher.registry, outcomes, review_queue)


def _escalate_if_needed(
    outcome: ResolutionOutcome,
    candidates: list[MatchCandidate],
    matcher: DeterministicMatcher,
    llm_resolver: LLMResolver | None,
    review_queue: ReviewQueue,
    *,
    system: str,
    record_display: str,
) -> ResolutionOutcome:
    if outcome.matched_canonical_id is not None:
        return outcome  # deterministic match already accepted

    if not candidates:
        review_queue.add(
            system=system,
            record_id=outcome.record_id,
            record_display=record_display,
            candidates=[],
            reason="no name or identifier present in the source record",
        )
        return outcome

    top_score = candidates[0].score
    if top_score < FUZZY_LLM_FLOOR or llm_resolver is None:
        reason = (
            "below deterministic-match confidence and no LLM resolver configured"
            if llm_resolver is None
            else "below deterministic-match confidence"
        )
        review_queue.add(
            system=system,
            record_id=outcome.record_id,
            record_display=record_display,
            candidates=candidates,
            reason=reason,
        )
        return outcome

    decision = llm_resolver.resolve_ambiguous(
        record_name=record_display,
        candidates=[(c.canonical_id, matcher.name_for(c.canonical_id)) for c in candidates],
    )

    if decision.chosen_canonical_id and decision.confidence >= LLM_ACCEPT_THRESHOLD:
        matcher.attach(decision.chosen_canonical_id, system, outcome.record_id)
        return ResolutionOutcome(
            system=system,
            record_id=outcome.record_id,
            matched_canonical_id=decision.chosen_canonical_id,
            confidence=decision.confidence,
            method="llm",
        )

    review_queue.add(
        system=system,
        record_id=outcome.record_id,
        record_display=record_display,
        candidates=candidates,
        reason=f"LLM uncertain: {decision.rationale}",
    )
    return outcome
