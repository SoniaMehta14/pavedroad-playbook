"""FinOps guardrails: per-run token budgets, per-task iteration caps, cost
accounting per model tier, and the deterministic routing table.

Cost discipline is a design constraint here, not a feature bolted on
later — every LLM call in this package goes through Guardrails.route()
and Guardrails.record_usage(), so a budget breach halts the run
gracefully (a resumable checkpoint in the state store, see pipeline.py)
rather than failing loudly mid-invoice or, worse, running up an unbounded
bill silently.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

from adapters.base import Usage
from adapters.pricing import anthropic_cost_usd

from .routing import RoutingTable
from .state_store import StateStore

_BASELINE_MODEL = "claude-opus-4-8"


class BudgetExceededError(RuntimeError):
    """Raised the moment a recorded call would push a run over its token
    budget. The call itself already happened (and is already logged) —
    this signals the pipeline to halt gracefully, not to pretend the
    spend didn't occur."""

    def __init__(self, run_id: str, tokens_used: int, token_budget: int) -> None:
        super().__init__(
            f"run {run_id!r} exceeded its token budget ({tokens_used} used, budget {token_budget})"
        )
        self.run_id = run_id
        self.tokens_used = tokens_used
        self.token_budget = token_budget


class IterationCapExceededError(RuntimeError):
    """Raised when a single task needs more LLM-touching steps than the
    configured cap. Handled per-task (escalate that one task to human
    review), not as a whole-run halt — a runaway single task shouldn't
    stop everything else from reconciling."""

    def __init__(self, task_id: str, cap: int) -> None:
        super().__init__(f"task {task_id!r} exceeded its iteration cap of {cap}")
        self.task_id = task_id
        self.cap = cap


class TierSpend(BaseModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class CostReport(BaseModel):
    """The FinOps proof artifact: what the routing table actually spent,
    versus what the same calls would have cost on an all-expensive-tier
    baseline. Measured from real recorded token counts, not asserted."""

    by_tier: dict[str, TierSpend]
    actual_cost_usd: float
    all_opus_baseline_cost_usd: float
    total_calls: int

    @property
    def savings_usd(self) -> float:
        return self.all_opus_baseline_cost_usd - self.actual_cost_usd

    @property
    def savings_pct(self) -> float:
        if self.all_opus_baseline_cost_usd == 0:
            return 0.0
        return self.savings_usd / self.all_opus_baseline_cost_usd * 100


@dataclass
class _CallRecord:
    tier: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class Guardrails:
    state_store: StateStore
    routing: RoutingTable
    token_budget: int
    max_iterations_per_task: int = 5
    _task_iterations: dict[str, int] = field(default_factory=dict, repr=False, init=False)
    _calls: list[_CallRecord] = field(default_factory=list, repr=False, init=False)

    def route(self, route_name: str) -> tuple[str, str]:
        """Resolve a named route to (model_id, tier_name)."""
        return self.routing.model_for(route_name), self.routing.tier_for(route_name)

    def check_iteration(self, task_id: str) -> None:
        """Call once per LLM-touching step for a task; raises past the cap."""
        count = self._task_iterations.get(task_id, 0) + 1
        if count > self.max_iterations_per_task:
            raise IterationCapExceededError(task_id, self.max_iterations_per_task)
        self._task_iterations[task_id] = count

    def record_usage(self, run_id: str, *, tier: str, usage: Usage) -> None:
        """Log a completed LLM call's spend, then enforce the run's token
        budget. The call is always recorded first — a budget breach means
        the run stops going forward, not that the spend that already
        happened gets hidden from the report."""
        self._calls.append(
            _CallRecord(
                tier=tier,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
            )
        )
        self.state_store.record_usage(
            run_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )

        run = self.state_store.get_run(run_id)
        if run.tokens_used > self.token_budget:
            raise BudgetExceededError(run_id, run.tokens_used, self.token_budget)

    def cost_report(self) -> CostReport:
        by_tier: dict[str, TierSpend] = {}
        for call in self._calls:
            spend = by_tier.setdefault(call.tier, TierSpend())
            spend.calls += 1
            spend.input_tokens += call.input_tokens
            spend.output_tokens += call.output_tokens
            spend.cost_usd += call.cost_usd

        actual_cost = sum(c.cost_usd for c in self._calls)
        baseline_cost = sum(
            anthropic_cost_usd(_BASELINE_MODEL, c.input_tokens, c.output_tokens)
            for c in self._calls
        )

        return CostReport(
            by_tier=by_tier,
            actual_cost_usd=actual_cost,
            all_opus_baseline_cost_usd=baseline_cost,
            total_calls=len(self._calls),
        )
