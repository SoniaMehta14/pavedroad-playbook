"""Quickstart: the whole reference implementation, one runnable script.

Generates Kestrel Systems' messy synthetic data (CRM, billing, PSA),
resolves customer identity across all three systems, generates AR
invoices, reconciles them with the Analyst/Validator pipeline, and
prints a cost report.

No API key required — it runs entirely in deterministic mode by
default, which is a fully supported configuration (ambiguous cases go
straight to human review rather than being guessed at). Set
ANTHROPIC_API_KEY to see the LLM-assisted paths light up with real
routing and cost tracking instead.

Run from the repo root:

    uv run python examples/quickstart.py
"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from data.kestrel import generate_invoices, generate_kestrel_dataset  # noqa: E402

from adapters.base import LLMProvider  # noqa: E402
from interop.llm_resolution import LLMResolver  # noqa: E402
from interop.resolve import resolve_dataset  # noqa: E402
from interop.tools import KestrelToolServer  # noqa: E402
from orchestration.guardrails import Guardrails  # noqa: E402
from orchestration.pipeline import reconcile_invoices  # noqa: E402
from orchestration.routing import RoutingTable  # noqa: E402
from orchestration.state_store import StateStore  # noqa: E402


def main() -> None:
    print("Generating Kestrel Systems' messy synthetic data (CRM, billing, PSA)...")
    dataset = generate_kestrel_dataset(seed=42)
    print(
        f"  {len(dataset.canonical_customers)} real customers behind "
        f"{len(dataset.crm_records)} CRM records, {len(dataset.billing_records)} billing "
        f"records, {len(dataset.psa_records)} PSA jobs — with duplicate names, mismatched "
        f"IDs, and inconsistent date formats deliberately mixed in"
    )

    llm_resolver: LLMResolver | None = None
    analyst_provider: LLMProvider | None = None
    validator_provider: LLMProvider | None = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\nANTHROPIC_API_KEY found — using real Claude calls for the LLM-assisted steps.")
        from adapters.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        llm_resolver = LLMResolver(provider, model="claude-haiku-4-5")
        analyst_provider = provider
        validator_provider = provider
    else:
        print(
            "\nNo ANTHROPIC_API_KEY set — running deterministic-only. This is a fully "
            "supported mode: ambiguous cases go straight to human review instead of "
            "being guessed at. Set the key to see the LLM-assisted residual path."
        )

    print("\nResolving customer identity across all three systems...")
    report = resolve_dataset(
        dataset.crm_records,
        dataset.billing_records,
        dataset.psa_records,
        llm_resolver=llm_resolver,
    )
    print(
        f"  {len(report.unified_customers)} unified customers identified; "
        f"{len(report.review_queue.pending())} raw records sent to human review"
    )

    print("\nGenerating AR invoices against the resolved customer/job data...")
    invoices = generate_invoices(dataset, seed=100)
    print(f"  {len(invoices)} invoices generated (clean matches plus deliberate discrepancies)")

    print("\nReconciling invoices with the Analyst/Validator pipeline...")
    tool_server = KestrelToolServer(report, dataset.psa_records)
    store = StateStore(":memory:")
    guardrails = Guardrails(state_store=store, routing=RoutingTable.load(), token_budget=1_000_000)

    result = reconcile_invoices(
        invoices,
        tool_server=tool_server,
        state_store=store,
        guardrails=guardrails,
        analyst_provider=analyst_provider,
        validator_provider=validator_provider,
    )
    print(f"  {len(result.closed_invoice_ids)} invoices closed automatically")
    print(f"  {len(result.human_review)} invoices escalated to human review")

    cost_report = guardrails.cost_report()
    print("\nCost report:")
    print(f"  {cost_report.total_calls} LLM calls")
    print(f"  ${cost_report.actual_cost_usd:.4f} actual cost")
    if cost_report.total_calls > 0:
        print(
            f"  ${cost_report.all_opus_baseline_cost_usd:.4f} would have cost on an "
            f"all-Opus baseline"
        )
        print(f"  {cost_report.savings_pct:.1f}% saved by the routing table")

    store.close()
    print("\nDone. See docs/evals.md for how to measure accuracy against golden ground truth.")


if __name__ == "__main__":
    main()
