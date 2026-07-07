"""Pydantic models for the entity resolution pipeline's outputs.

These are the interoperability layer's own types — distinct from the raw,
messy source-system models in data/kestrel/models.py. Everything here
describes a *resolved* or *in-progress-toward-resolved* state.
"""

from typing import Literal

from pydantic import BaseModel, Field

MatchMethod = Literal["exact_key", "exact_name", "fuzzy_name", "llm", "new_entity", "unresolved"]


class UnifiedCustomer(BaseModel):
    """A single real-world customer, with every raw record resolved to it
    so far, across every source system."""

    canonical_id: str
    name: str
    source_record_ids: dict[str, list[str]] = Field(default_factory=dict)


class MatchCandidate(BaseModel):
    canonical_id: str
    score: float
    method: MatchMethod


class ResolutionOutcome(BaseModel):
    """What happened when the pipeline tried to resolve one raw record."""

    system: str
    record_id: str
    matched_canonical_id: str | None
    confidence: float
    method: MatchMethod


class LLMMatchDecision(BaseModel):
    chosen_canonical_id: str | None
    confidence: float
    rationale: str


class ReviewQueueItem(BaseModel):
    """A record that no automated step could confidently resolve.

    Never auto-applied. A human closes this out via ReviewQueue.resolve().
    """

    item_id: str
    system: str
    record_id: str
    record_display: str
    candidates: list[MatchCandidate]
    reason: str
    status: Literal["pending", "resolved", "rejected"] = "pending"
    resolved_canonical_id: str | None = None
    reviewer_note: str | None = None
