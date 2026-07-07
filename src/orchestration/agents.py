"""Analyst and Validator agents for invoice reconciliation.

Deterministic checks handle every clear-cut case for free — the same
discipline src/interop applies to entity resolution, extended here to a
second workflow: an unmatched customer, a job that doesn't exist at all,
or an amount that's off by more than a plausible rounding error are all
decided without spending a token. An LLM is only asked to weigh in on the
genuinely ambiguous case (a service date a few days off from an
otherwise-matching job — sloppy paperwork, or a different booking
entirely?), and only at the cheap tier unless the routing table's
documented escalation criterion is met.

The Validator never rubber-stamps the Analyst's proposal. It independently
re-derives the customer and job match from the same source data and
compares its own conclusion — including applying a stricter date
tolerance than the Analyst's first pass — before agreeing. Disagreement
always escalates; it is never silently overridden in either direction.
"""

import json
import re

from data.kestrel import EQUIPMENT_RATES, InvoiceLineItem
from pydantic import BaseModel

from adapters.base import LLMProvider, Message
from interop.dates import day_distance
from interop.tools import CustomerJobsInput, CustomerLookupInput, JobSummary, KestrelToolServer

from .guardrails import Guardrails
from .models import AnalystProposal, DiscrepancyKind, ValidatorDecision

_CUSTOMER_MATCH_THRESHOLD = 0.75
_AMOUNT_TOLERANCE_PCT = 0.05
_DATE_CLEAN_TOLERANCE_DAYS = 1
_VALIDATOR_STRICT_DATE_DAYS = 3
_DEFAULT_DAILY_RATE = 300.0


class _DateJudgment(BaseModel):
    is_match: bool
    confidence: float
    rationale: str


def _expected_amount(equipment: str, days: int) -> float:
    return EQUIPMENT_RATES.get(equipment, _DEFAULT_DAILY_RATE) * days


def _amount_delta_pct(invoice: InvoiceLineItem) -> float:
    expected = _expected_amount(invoice.equipment_billed, invoice.days_billed)
    if expected == 0:
        return 1.0
    return abs(invoice.amount_usd - expected) / expected


def _nearest_candidate(
    invoice: InvoiceLineItem, jobs: list[JobSummary]
) -> tuple[JobSummary, int | None] | None:
    candidates = [j for j in jobs if j.equipment_description == invoice.equipment_billed]
    if not candidates:
        return None
    scored = [(job, day_distance(invoice.service_date, job.scheduled_date)) for job in candidates]
    scored.sort(key=lambda pair: (pair[1] is None, pair[1] if pair[1] is not None else 999))
    return scored[0]


def _parse_date_judgment(text: str) -> _DateJudgment:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return _DateJudgment(is_match=False, confidence=0.0, rationale="unparseable LLM response")
    try:
        payload = json.loads(match.group(0))
        return _DateJudgment(
            is_match=bool(payload.get("is_match", False)),
            confidence=float(payload.get("confidence", 0.0)),
            rationale=str(payload.get("rationale", "")),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return _DateJudgment(is_match=False, confidence=0.0, rationale="unparseable LLM response")


class AnalystAgent:
    """Extracts, matches, and proposes a reconciliation for one invoice."""

    def __init__(
        self,
        *,
        tool_server: KestrelToolServer,
        guardrails: Guardrails,
        run_id: str,
        provider: LLMProvider | None = None,
    ) -> None:
        self._tool_server = tool_server
        self._guardrails = guardrails
        self._run_id = run_id
        self._provider = provider

    def analyze(self, invoice: InvoiceLineItem) -> AnalystProposal:
        lookup = self._tool_server.lookup_customer(
            CustomerLookupInput(query=invoice.customer_name_billed)
        )
        best = lookup.matches[0] if lookup.matches else None

        if best is None or best.match_score < _CUSTOMER_MATCH_THRESHOLD:
            best_score = best.match_score if best else 0.0
            return AnalystProposal(
                invoice_id=invoice.invoice_id,
                matched_canonical_id=None,
                matched_job_id=None,
                discrepancy="unknown_customer",
                confidence=0.95,
                rationale=(
                    f"No registry customer matches {invoice.customer_name_billed!r} closely "
                    f"enough (best score {best_score:.2f})."
                ),
                used_llm=False,
            )

        jobs = self._tool_server.get_customer_jobs(
            CustomerJobsInput(canonical_id=best.canonical_id)
        ).jobs
        candidate = _nearest_candidate(invoice, jobs)

        if candidate is None:
            return AnalystProposal(
                invoice_id=invoice.invoice_id,
                matched_canonical_id=best.canonical_id,
                matched_job_id=None,
                discrepancy="no_matching_job",
                confidence=0.9,
                rationale=f"No PSA job for {best.name} references {invoice.equipment_billed!r}.",
                used_llm=False,
            )

        job, distance = candidate
        delta_pct = _amount_delta_pct(invoice)

        if delta_pct > _AMOUNT_TOLERANCE_PCT:
            return AnalystProposal(
                invoice_id=invoice.invoice_id,
                matched_canonical_id=best.canonical_id,
                matched_job_id=job.job_id,
                discrepancy="amount_mismatch",
                confidence=0.9,
                rationale=(
                    f"Billed ${invoice.amount_usd:.2f} is {delta_pct * 100:.0f}% off the expected "
                    f"${_expected_amount(invoice.equipment_billed, invoice.days_billed):.2f}."
                ),
                used_llm=False,
            )

        if distance is not None and distance <= _DATE_CLEAN_TOLERANCE_DAYS:
            return AnalystProposal(
                invoice_id=invoice.invoice_id,
                matched_canonical_id=best.canonical_id,
                matched_job_id=job.job_id,
                discrepancy="none",
                confidence=0.97,
                rationale=f"Matches job {job.job_id} for {best.name} within tolerance.",
                used_llm=False,
            )

        return self._judge_ambiguous_date(invoice, job, distance, best.canonical_id)

    def _judge_ambiguous_date(
        self,
        invoice: InvoiceLineItem,
        job: JobSummary,
        distance: int | None,
        canonical_id: str,
    ) -> AnalystProposal:
        discrepancy: DiscrepancyKind = "unparseable_date" if distance is None else "date_drift"

        if self._provider is None:
            return AnalystProposal(
                invoice_id=invoice.invoice_id,
                matched_canonical_id=canonical_id,
                matched_job_id=job.job_id,
                discrepancy=discrepancy,
                confidence=0.5,
                rationale="Date mismatch; no LLM resolver configured, escalating for review.",
                used_llm=False,
            )

        self._guardrails.check_iteration(invoice.invoice_id)
        model, tier = self._guardrails.route("ambiguous_discrepancy")

        distance_desc = "unparseable" if distance is None else f"{distance} day(s)"
        prompt = (
            "An invoice's service date may or may not refer to the same rental job as a "
            "scheduling record. Decide whether they are the same booking.\n\n"
            f"<invoice_service_date>\n{invoice.service_date}\n</invoice_service_date>\n"
            f"<job_scheduled_date>\n{job.scheduled_date}\n</job_scheduled_date>\n"
            f"<day_distance>{distance_desc}</day_distance>\n\n"
            'Respond with ONLY a JSON object: {"is_match": <bool>, "confidence": <0.0-1.0>, '
            '"rationale": "<one sentence>"}'
        )
        result = self._provider.complete(
            [Message(role="user", content=prompt)], model=model, max_tokens=250
        )
        self._guardrails.record_usage(self._run_id, tier=tier, usage=result.usage)
        judgment = _parse_date_judgment(result.text)

        return AnalystProposal(
            invoice_id=invoice.invoice_id,
            matched_canonical_id=canonical_id,
            matched_job_id=job.job_id if judgment.is_match else None,
            discrepancy="none" if judgment.is_match else discrepancy,
            confidence=judgment.confidence,
            rationale=judgment.rationale,
            used_llm=True,
            model_used=model,
        )


class ValidatorAgent:
    """Independently re-checks the Analyst's proposal against source data."""

    def __init__(
        self,
        *,
        tool_server: KestrelToolServer,
        guardrails: Guardrails,
        run_id: str,
        provider: LLMProvider | None = None,
    ) -> None:
        self._tool_server = tool_server
        self._guardrails = guardrails
        self._run_id = run_id
        self._provider = provider

    def validate(self, invoice: InvoiceLineItem, proposal: AnalystProposal) -> ValidatorDecision:
        lookup = self._tool_server.lookup_customer(
            CustomerLookupInput(query=invoice.customer_name_billed)
        )
        best = lookup.matches[0] if lookup.matches else None
        customer_ok = best is not None and best.match_score >= _CUSTOMER_MATCH_THRESHOLD

        if not customer_ok:
            agrees = proposal.discrepancy == "unknown_customer"
            discrepancy: DiscrepancyKind = "unknown_customer"
        else:
            assert best is not None  # customer_ok implies best is not None
            jobs = self._tool_server.get_customer_jobs(
                CustomerJobsInput(canonical_id=best.canonical_id)
            ).jobs
            candidate = _nearest_candidate(invoice, jobs)

            if candidate is None:
                agrees = proposal.discrepancy == "no_matching_job"
                discrepancy = "no_matching_job"
            else:
                job, distance = candidate
                delta_pct = _amount_delta_pct(invoice)

                if delta_pct > _AMOUNT_TOLERANCE_PCT:
                    agrees = proposal.discrepancy == "amount_mismatch"
                    discrepancy = "amount_mismatch"
                elif distance is not None and distance <= _VALIDATOR_STRICT_DATE_DAYS:
                    # The Validator's own bar for "close enough" is
                    # stricter than the Analyst's clean-match threshold —
                    # this is the independent check catching a case the
                    # Analyst's LLM may have judged too leniently.
                    agrees = (
                        proposal.discrepancy == "none" and proposal.matched_job_id == job.job_id
                    )
                    discrepancy = "none"
                else:
                    agrees = False
                    discrepancy = "date_drift" if distance is not None else "unparseable_date"

        if agrees:
            return ValidatorDecision(
                invoice_id=invoice.invoice_id,
                agrees=True,
                discrepancy=discrepancy,
                rationale="Independent re-check matches the Analyst's proposal.",
                used_llm=False,
            )

        return self._write_up_disagreement(
            invoice, proposal, discrepancy, route_name="disagreement_writeup"
        )

    def confirm_escalation(
        self,
        invoice: InvoiceLineItem,
        proposal: AnalystProposal,
        prior_decision: ValidatorDecision,
    ) -> ValidatorDecision:
        """A first disagreement write-up (mid tier) alone doesn't resolve
        anything automatically — this is the documented escalation
        criterion: get the expensive tier's take before handing the
        invoice to a human, since that's cheaper than a human's time."""
        return self._write_up_disagreement(
            invoice,
            proposal,
            prior_decision.discrepancy,
            route_name="disagreement_writeup_escalated",
        )

    def _write_up_disagreement(
        self,
        invoice: InvoiceLineItem,
        proposal: AnalystProposal,
        discrepancy: DiscrepancyKind,
        *,
        route_name: str,
    ) -> ValidatorDecision:
        if self._provider is None:
            return ValidatorDecision(
                invoice_id=invoice.invoice_id,
                agrees=False,
                discrepancy=discrepancy,
                rationale=(
                    f"Independent check disagrees with the Analyst's proposal "
                    f"({proposal.discrepancy!r}); no LLM configured for write-up."
                ),
                used_llm=False,
            )

        self._guardrails.check_iteration(invoice.invoice_id)
        model, tier = self._guardrails.route(route_name)
        proposal_block = f"{proposal.discrepancy}: {proposal.rationale}"
        prompt = (
            "Write a one-sentence rationale for a human reviewer explaining why an automated "
            "invoice reconciliation disagreement needs their attention.\n\n"
            f"<analyst_proposal>\n{proposal_block}\n</analyst_proposal>\n"
            f"<validator_independent_finding>\n{discrepancy}\n</validator_independent_finding>"
        )
        result = self._provider.complete(
            [Message(role="user", content=prompt)], model=model, max_tokens=200
        )
        self._guardrails.record_usage(self._run_id, tier=tier, usage=result.usage)

        return ValidatorDecision(
            invoice_id=invoice.invoice_id,
            agrees=False,
            discrepancy=discrepancy,
            rationale=result.text.strip(),
            used_llm=True,
            model_used=model,
        )
