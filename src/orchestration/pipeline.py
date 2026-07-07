"""Two-agent invoice reconciliation pipeline.

Wires the Analyst and Validator through the explicit handoff state
machine defined in models.py, logging every transition to the state
store, and respecting Guardrails at every LLM-touching step. A token
budget breach halts the whole run gracefully at a resumable checkpoint;
a single task exceeding its iteration cap escalates only that task to
human review, so one runaway invoice doesn't stop the rest of the batch.
Disagreement between the two agents always escalates — never a silent
override.
"""

import uuid

from data.kestrel import InvoiceLineItem
from pydantic import BaseModel

from adapters.base import LLMProvider
from interop import KestrelToolServer

from .agents import AnalystAgent, ValidatorAgent
from .guardrails import BudgetExceededError, Guardrails, IterationCapExceededError
from .models import AnalystProposal, ValidatorDecision
from .state_store import StateStore


class HumanReviewItem(BaseModel):
    invoice_id: str
    analyst_proposal: AnalystProposal
    validator_decision: ValidatorDecision


class ReconciliationRunResult(BaseModel):
    run_id: str
    workflow_name: str
    status: str
    closed_invoice_ids: list[str]
    human_review: list[HumanReviewItem]
    resume_index: int


def _iteration_cap_fallback(
    invoice: InvoiceLineItem, exc: IterationCapExceededError
) -> HumanReviewItem:
    """A task that exceeds its iteration cap escalates automatically with
    a note explaining why — the same "never silently drop it" principle
    as any other disagreement, just triggered by a safety net rather than
    a genuine agent conflict."""
    return HumanReviewItem(
        invoice_id=invoice.invoice_id,
        analyst_proposal=AnalystProposal(
            invoice_id=invoice.invoice_id,
            matched_canonical_id=None,
            matched_job_id=None,
            discrepancy="no_matching_job",
            confidence=0.0,
            rationale=f"Automatically escalated: {exc}",
            used_llm=False,
        ),
        validator_decision=ValidatorDecision(
            invoice_id=invoice.invoice_id,
            agrees=False,
            discrepancy="no_matching_job",
            rationale=f"Automatically escalated: {exc}",
            used_llm=False,
        ),
    )


def reconcile_invoices(
    invoices: list[InvoiceLineItem],
    *,
    tool_server: KestrelToolServer,
    state_store: StateStore,
    guardrails: Guardrails,
    run_id: str | None = None,
    analyst_provider: LLMProvider | None = None,
    validator_provider: LLMProvider | None = None,
    start_index: int = 0,
) -> ReconciliationRunResult:
    run_id = run_id or f"run-{uuid.uuid4()}"
    if start_index == 0:
        state_store.start_run(
            run_id, "invoice_reconciliation", token_budget=guardrails.token_budget
        )

    analyst = AnalystAgent(
        tool_server=tool_server, guardrails=guardrails, run_id=run_id, provider=analyst_provider
    )
    validator = ValidatorAgent(
        tool_server=tool_server, guardrails=guardrails, run_id=run_id, provider=validator_provider
    )

    closed: list[str] = []
    human_review: list[HumanReviewItem] = []

    for idx in range(start_index, len(invoices)):
        invoice = invoices[idx]
        task_id = invoice.invoice_id
        try:
            state_store.log_transition(
                run_id=run_id,
                task_id=task_id,
                step_index=idx,
                agent_name="pipeline",
                from_state="received",
                to_state="analyst_reviewing",
                thought_process={},
            )
            try:
                proposal = analyst.analyze(invoice)
                state_store.log_transition(
                    run_id=run_id,
                    task_id=task_id,
                    step_index=idx,
                    agent_name="analyst",
                    from_state="analyst_reviewing",
                    to_state="analyst_proposed",
                    thought_process=proposal.model_dump(),
                    model_used=proposal.model_used,
                    model_tier="cheap" if proposal.used_llm else None,
                )

                decision = validator.validate(invoice, proposal)
                state_store.log_transition(
                    run_id=run_id,
                    task_id=task_id,
                    step_index=idx,
                    agent_name="validator",
                    from_state="analyst_proposed",
                    to_state="validator_approved" if decision.agrees else "validator_escalated",
                    thought_process=decision.model_dump(),
                    model_used=decision.model_used,
                    model_tier="mid" if decision.used_llm else None,
                )

                if decision.agrees:
                    state_store.log_transition(
                        run_id=run_id,
                        task_id=task_id,
                        step_index=idx,
                        agent_name="pipeline",
                        from_state="validator_approved",
                        to_state="closed",
                        thought_process={},
                    )
                    closed.append(invoice.invoice_id)
                    continue

                final_decision = validator.confirm_escalation(invoice, proposal, decision)
                state_store.log_transition(
                    run_id=run_id,
                    task_id=task_id,
                    step_index=idx,
                    agent_name="validator",
                    from_state="validator_escalated",
                    to_state="human_review",
                    thought_process=final_decision.model_dump(),
                    model_used=final_decision.model_used,
                    model_tier="expensive" if final_decision.used_llm else None,
                )
                human_review.append(
                    HumanReviewItem(
                        invoice_id=invoice.invoice_id,
                        analyst_proposal=proposal,
                        validator_decision=final_decision,
                    )
                )
            except IterationCapExceededError as exc:
                state_store.log_transition(
                    run_id=run_id,
                    task_id=task_id,
                    step_index=idx,
                    agent_name="pipeline",
                    from_state="analyst_reviewing",
                    to_state="human_review",
                    thought_process={"error": str(exc)},
                )
                human_review.append(_iteration_cap_fallback(invoice, exc))
        except BudgetExceededError:
            state_store.halt_run(run_id, resume_index=idx)
            return ReconciliationRunResult(
                run_id=run_id,
                workflow_name="invoice_reconciliation",
                status="halted",
                closed_invoice_ids=closed,
                human_review=human_review,
                resume_index=idx,
            )

    state_store.complete_run(run_id)
    return ReconciliationRunResult(
        run_id=run_id,
        workflow_name="invoice_reconciliation",
        status="completed",
        closed_invoice_ids=closed,
        human_review=human_review,
        resume_index=len(invoices),
    )


def resume_reconciliation(
    run_id: str,
    invoices: list[InvoiceLineItem],
    *,
    tool_server: KestrelToolServer,
    state_store: StateStore,
    guardrails: Guardrails,
    analyst_provider: LLMProvider | None = None,
    validator_provider: LLMProvider | None = None,
) -> ReconciliationRunResult:
    """Continue a halted run from its last recorded checkpoint."""
    run = state_store.get_run(run_id)
    return reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=state_store,
        guardrails=guardrails,
        run_id=run_id,
        analyst_provider=analyst_provider,
        validator_provider=validator_provider,
        start_index=run.resume_index,
    )
