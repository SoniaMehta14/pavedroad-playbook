"""Unit tests for AnalystAgent and ValidatorAgent against hand-built
tool servers — each test targets exactly one branch of the deterministic
cascade or the LLM-assisted ambiguous-date path."""

from collections.abc import Generator

import pytest
from data.kestrel.invoices import InvoiceLineItem
from data.kestrel.models import PSAJobRecord

from adapters.base import CompletionResult, Message, Usage
from interop.models import ResolutionOutcome, UnifiedCustomer
from interop.resolve import ResolutionReport
from interop.review_queue import ReviewQueue
from interop.tools import KestrelToolServer
from orchestration.agents import AnalystAgent, ValidatorAgent
from orchestration.guardrails import Guardrails
from orchestration.models import AnalystProposal
from orchestration.routing import RoutingTable
from orchestration.state_store import StateStore

_CUSTOMER_NAME = "Blue Ridge Equipment Rental"
_EQUIPMENT = "CAT 320 Excavator"
_DAILY_RATE = 450.0


def _build_server(job: PSAJobRecord) -> KestrelToolServer:
    customer = UnifiedCustomer(
        canonical_id="UNIFIED-0001", name=_CUSTOMER_NAME, source_record_ids={"psa": [job.job_id]}
    )
    outcome = ResolutionOutcome(
        system="psa",
        record_id=job.job_id,
        matched_canonical_id=customer.canonical_id,
        confidence=1.0,
        method="exact_name",
    )
    report = ResolutionReport(
        unified_customers=[customer], outcomes=[outcome], review_queue=ReviewQueue()
    )
    return KestrelToolServer(report, [job])


@pytest.fixture
def store() -> Generator[StateStore, None, None]:
    s = StateStore(":memory:")
    s.start_run("run-1", "invoice_reconciliation", token_budget=1_000_000)
    yield s
    s.close()


@pytest.fixture
def guardrails(store: StateStore) -> Guardrails:
    return Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=1_000_000)


class _FixedJudgmentProvider:
    """A fake LLM whose date-ambiguity verdict is fixed at construction."""

    def __init__(self, *, is_match: bool, confidence: float = 0.8) -> None:
        self._is_match = is_match
        self._confidence = confidence

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        text = (
            f'{{"is_match": {"true" if self._is_match else "false"}, '
            f'"confidence": {self._confidence}, "rationale": "test fixture verdict"}}'
        )
        return CompletionResult(
            text=text,
            model=model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=50, output_tokens=20, cost_usd=0.0001),
        )


class _WriteupProvider:
    """A fake LLM that returns a fixed rationale string for write-up calls."""

    def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int,
        system: str | None = None,
    ) -> CompletionResult:
        return CompletionResult(
            text="This needs a human's attention because the dates don't line up.",
            model=model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=40, output_tokens=15, cost_usd=0.0001),
        )


def _clean_job(job_id: str = "PSA-1", scheduled_date: str = "2026-03-15") -> PSAJobRecord:
    return PSAJobRecord(
        job_id=job_id,
        customer_name_raw=_CUSTOMER_NAME,
        equipment_description=_EQUIPMENT,
        scheduled_date=scheduled_date,
        technician="tech_1",
    )


def _invoice(**overrides: object) -> InvoiceLineItem:
    defaults: dict[str, object] = {
        "invoice_id": "INV-1",
        "customer_name_billed": _CUSTOMER_NAME,
        "equipment_billed": _EQUIPMENT,
        "service_date": "2026-03-15",
        "days_billed": 1,
        "amount_usd": _DAILY_RATE,
    }
    defaults.update(overrides)
    return InvoiceLineItem.model_validate(defaults)


# --- AnalystAgent ---


def test_analyst_flags_unknown_customer(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    proposal = analyst.analyze(_invoice(customer_name_billed="Zzyzx Industrial Holdings ###"))

    assert proposal.discrepancy == "unknown_customer"
    assert proposal.used_llm is False
    assert proposal.matched_canonical_id is None


def test_analyst_flags_no_matching_job(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    proposal = analyst.analyze(_invoice(equipment_billed="Grove RT530E Rough Terrain Crane"))

    assert proposal.discrepancy == "no_matching_job"
    assert proposal.matched_canonical_id == "UNIFIED-0001"
    assert proposal.used_llm is False


def test_analyst_flags_amount_mismatch(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    proposal = analyst.analyze(_invoice(amount_usd=_DAILY_RATE * 1.4))

    assert proposal.discrepancy == "amount_mismatch"
    assert proposal.used_llm is False


def test_analyst_clean_match_needs_no_llm(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    proposal = analyst.analyze(_invoice())

    assert proposal.discrepancy == "none"
    assert proposal.matched_job_id == "PSA-1"
    assert proposal.used_llm is False


def test_analyst_date_drift_without_llm_escalates_deterministically(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    proposal = analyst.analyze(_invoice(service_date="2026-03-22"))  # 7 days off

    assert proposal.discrepancy == "date_drift"
    assert proposal.used_llm is False
    assert proposal.confidence == 0.5


def test_analyst_date_drift_with_llm_confirming_match(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(
        tool_server=server,
        guardrails=guardrails,
        run_id="run-1",
        provider=_FixedJudgmentProvider(is_match=True),
    )

    proposal = analyst.analyze(_invoice(service_date="2026-03-22"))

    assert proposal.discrepancy == "none"
    assert proposal.matched_job_id == "PSA-1"
    assert proposal.used_llm is True
    assert proposal.model_used == "claude-haiku-4-5"  # the "cheap" tier for this route


def test_analyst_date_drift_with_llm_rejecting_match(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(
        tool_server=server,
        guardrails=guardrails,
        run_id="run-1",
        provider=_FixedJudgmentProvider(is_match=False),
    )

    proposal = analyst.analyze(_invoice(service_date="2026-03-22"))

    assert proposal.discrepancy == "date_drift"
    assert proposal.matched_job_id is None
    assert proposal.used_llm is True


# --- ValidatorAgent ---


def test_validator_agrees_with_correct_clean_proposal(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(tool_server=server, guardrails=guardrails, run_id="run-1")
    validator = ValidatorAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    invoice = _invoice()
    proposal = analyst.analyze(invoice)
    decision = validator.validate(invoice, proposal)

    assert decision.agrees is True
    assert decision.used_llm is False


def test_validator_disagrees_when_analyst_llm_is_too_lenient(guardrails: Guardrails) -> None:
    # Analyst's LLM says "matches" for a 7-day drift, but the Validator's
    # own bar (_VALIDATOR_STRICT_DATE_DAYS = 3) is stricter — it should
    # independently disagree rather than trust the Analyst's conclusion.
    server = _build_server(_clean_job())
    analyst = AnalystAgent(
        tool_server=server,
        guardrails=guardrails,
        run_id="run-1",
        provider=_FixedJudgmentProvider(is_match=True),
    )
    validator = ValidatorAgent(
        tool_server=server, guardrails=guardrails, run_id="run-1", provider=_WriteupProvider()
    )

    invoice = _invoice(service_date="2026-03-22")
    proposal = analyst.analyze(invoice)
    assert proposal.discrepancy == "none"  # the analyst's LLM was fooled

    decision = validator.validate(invoice, proposal)

    assert decision.agrees is False
    assert decision.used_llm is True
    assert decision.model_used == "claude-sonnet-5"  # "mid" tier for disagreement_writeup


def test_validator_disagreement_without_llm_gives_canned_rationale(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    analyst = AnalystAgent(
        tool_server=server,
        guardrails=guardrails,
        run_id="run-1",
        provider=_FixedJudgmentProvider(is_match=True),
    )
    validator = ValidatorAgent(tool_server=server, guardrails=guardrails, run_id="run-1")

    invoice = _invoice(service_date="2026-03-22")
    proposal = analyst.analyze(invoice)
    decision = validator.validate(invoice, proposal)

    assert decision.agrees is False
    assert decision.used_llm is False


def test_confirm_escalation_uses_the_expensive_tier(guardrails: Guardrails) -> None:
    server = _build_server(_clean_job())
    validator = ValidatorAgent(
        tool_server=server, guardrails=guardrails, run_id="run-1", provider=_WriteupProvider()
    )
    invoice = _invoice(service_date="2026-03-22")  # 7-day drift
    proposal = AnalystProposal(
        invoice_id=invoice.invoice_id,
        matched_canonical_id="UNIFIED-0001",
        matched_job_id="PSA-1",
        discrepancy="none",
        confidence=0.6,
        rationale="analyst said match",
        used_llm=True,
        model_used="claude-haiku-4-5",
    )
    first_decision = validator.validate(invoice, proposal)
    assert first_decision.agrees is False  # the drift exceeds the Validator's own strict bar

    final = validator.confirm_escalation(invoice, proposal, first_decision)

    assert final.model_used == "claude-opus-4-8"  # "expensive" tier, escalated route
    assert final.agrees is False
