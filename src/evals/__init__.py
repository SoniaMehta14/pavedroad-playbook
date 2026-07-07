"""Evaluation harness.

An AI workflow that can't prove its accuracy is a liability on a board deck.
This package measures entity resolution and reconciliation quality against
golden datasets with known ground truth, gates merges on regression evals in
CI, and reports the cost-versus-accuracy frontier across routing
configurations so the tradeoff is a decision, not a surprise.
"""

from .cost_frontier import (
    FrontierPoint,
    render_frontier_table,
    run_cost_accuracy_frontier,
    single_tier_routing,
)
from .entity_resolution import EntityResolutionScore, score_entity_resolution
from .golden import (
    ReconciliationGolden,
    build_entity_resolution_golden,
    build_reconciliation_golden,
)
from .reconciliation import ReconciliationScore, score_reconciliation

__all__ = [
    "EntityResolutionScore",
    "FrontierPoint",
    "ReconciliationGolden",
    "ReconciliationScore",
    "build_entity_resolution_golden",
    "build_reconciliation_golden",
    "render_frontier_table",
    "run_cost_accuracy_frontier",
    "score_entity_resolution",
    "score_reconciliation",
    "single_tier_routing",
]
