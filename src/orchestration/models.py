"""Pydantic models for the invoice-reconciliation workflow.

The reconciliation state machine, made explicit as a type rather than
left implicit in control flow:

    received -> analyst_reviewing -> analyst_proposed -> validator_reviewing
        -> validator_approved -> closed
        -> validator_escalated -> human_review

See docs/architecture/ for the Mermaid diagram of this state machine and
the agent communication topology.
"""

from typing import Literal

from pydantic import BaseModel

ReconciliationState = Literal[
    "received",
    "analyst_reviewing",
    "analyst_proposed",
    "validator_reviewing",
    "validator_approved",
    "validator_escalated",
    "closed",
    "human_review",
]

DiscrepancyKind = Literal[
    "none",
    "unknown_customer",
    "no_matching_job",
    "amount_mismatch",
    "date_drift",
    "unparseable_date",
]


class AnalystProposal(BaseModel):
    """The Analyst's proposed reconciliation for one invoice."""

    invoice_id: str
    matched_canonical_id: str | None
    matched_job_id: str | None
    discrepancy: DiscrepancyKind
    confidence: float
    rationale: str
    used_llm: bool
    model_used: str | None = None


class ValidatorDecision(BaseModel):
    """The Validator's independent verdict on an Analyst proposal.

    agrees=False always means the invoice is escalated — never a silent
    override of the Analyst's proposal.
    """

    invoice_id: str
    agrees: bool
    discrepancy: DiscrepancyKind
    rationale: str
    used_llm: bool
    model_used: str | None = None
