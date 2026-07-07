"""Multi-agent orchestration engine with FinOps guardrails.

Enterprise leaders don't fear agents because agents are new; they fear unbounded
spend and unauditable decisions. This package runs agent workflows as logged,
replayable state transitions in a durable store — every step budgeted, every
model call routed through a deterministic cost table, every disagreement between
agents escalated to a human rather than silently overridden.
"""

from .guardrails import (
    BudgetExceededError,
    CostReport,
    Guardrails,
    IterationCapExceededError,
    TierSpend,
)
from .routing import RoutingTable
from .state_store import RunRecord, RunStatus, StateStore, StateTransition

__all__ = [
    "BudgetExceededError",
    "CostReport",
    "Guardrails",
    "IterationCapExceededError",
    "RoutingTable",
    "RunRecord",
    "RunStatus",
    "StateStore",
    "StateTransition",
    "TierSpend",
]
