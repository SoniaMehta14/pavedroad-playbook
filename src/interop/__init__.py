"""Semantic interoperability layer.

Mid-market companies run their business across systems that were never designed to
agree with each other: the CRM, the billing system, and the PSA tool each hold a
partial, inconsistent view of the same customers. This package normalizes that
fragmented data into a single typed tool-calling surface that an orchestration
layer can trust — deterministic entity resolution first, LLM assistance only for
the ambiguous residual, and a human review queue for anything below the
confidence bar.
"""

from .deterministic import DeterministicMatcher
from .llm_resolution import LLMResolver
from .models import (
    LLMMatchDecision,
    MatchCandidate,
    ResolutionOutcome,
    ReviewQueueItem,
    UnifiedCustomer,
)
from .resolve import ResolutionReport, resolve_dataset
from .review_queue import ReviewQueue
from .sanitize import SanitizedText, delimit_untrusted, sanitize_free_text

__all__ = [
    "DeterministicMatcher",
    "LLMMatchDecision",
    "LLMResolver",
    "MatchCandidate",
    "ResolutionOutcome",
    "ResolutionReport",
    "ReviewQueue",
    "ReviewQueueItem",
    "SanitizedText",
    "UnifiedCustomer",
    "delimit_untrusted",
    "resolve_dataset",
    "sanitize_free_text",
]
