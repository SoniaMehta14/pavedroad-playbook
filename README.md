# Paved Road: AI Enablement for PE Portfolio Companies

## The problem

Most AI pilots inside mid-market portfolio companies die the same way. Someone stands up
a demo, a steering committee claps, and six months later nothing in the P&L has moved.
The failure is rarely the model. It's that the pilot was never wired into a real business
workflow, nobody measured a baseline before starting, and nobody was named to own the
thing once the consultants left. Ask a CFO to defend a 30% productivity claim and watch
how fast "we think it's helping" falls apart.

This repository is both sides of the fix: an operating playbook that tells a fund or an
operating partner how to run a 90-day AI engagement that survives that scrutiny, and a
reference implementation that proves the underlying architecture actually works —
against messy synthetic data, with real cost accounting, with accuracy numbers measured
and reported honestly, including the unflattering ones.

## What's in this repo

**The playbook** ([`playbook/`](playbook/)) is the part written for deal teams and
operating partners, not engineers:

- [`ENTERPRISE_AI_PLAYBOOK.md`](playbook/ENTERPRISE_AI_PLAYBOOK.md) — the 30/60/90-day
  model for embedding a forward-deployed engineering pod in a portco. Day 30 is a measured
  baseline instrumented from systems the company already trusts. Day 60 is one production
  workflow with a named internal owner who can demo it without the pod in the room. Day 90
  is a board-deck-ready ROI attribution with a stated counterfactual method, not a vibe.
  The pod exits on a self-sufficiency test, not a date.
- [`AI_DILIGENCE_SCORECARD.md`](playbook/AI_DILIGENCE_SCORECARD.md) — a pre-acquisition
  assessment a deal team can actually run in two to three weeks: data readiness, an AI
  leverage map scored by ROI against implementation risk, a tech-debt-versus-leverage
  test, team readiness, and a weighted rubric producing a maturity tier and sized
  opportunities. Includes a fully worked example against a fictional $20M ARR company.

**The reference implementation** ([`src/`](src/), [`data/`](data/)) is the part written
for a portco CTO who wants to see the patterns before trusting them, built around one
fictional company — Kestrel Systems, a $20M ARR equipment-rental vertical SaaS company,
the same company the diligence scorecard's worked example scores. Its data is
deliberately messy: duplicate customer records, mismatched IDs across systems,
inconsistent date formats, free text hiding structured facts — because that's what
mid-market data actually looks like, not what a clean seed script would produce.

| Layer | What it does |
|---|---|
| [`src/adapters/`](src/adapters/) | Vendor-neutral LLM provider layer — Anthropic by default, any OpenAI-compatible endpoint as a fallback, Ollama for local models. One protocol, real cost accounting on every call. |
| [`src/interop/`](src/interop/) | Semantic interoperability: entity resolution across three overlapping messy systems. Deterministic matching first (free, auditable), an LLM only for the genuinely ambiguous residual, a human review queue for anything neither can confidently place — never a silent auto-merge. |
| [`src/orchestration/`](src/orchestration/) | A two-agent invoice reconciliation pipeline (Analyst proposes, Validator independently re-checks — never rubber-stamps) with a state-first SQLite execution log, a deterministic cost-tier routing table, and FinOps guardrails (token budgets, iteration caps, graceful resumable halts). |
| [`src/evals/`](src/evals/) | The harness that answers "how do we know it's right": golden datasets with known ground truth, precision/recall scoring, a cost-vs-accuracy frontier across routing configurations, and a CI regression gate. |

Architecture rationale is written down, not just implemented: see
[ADR 0001](docs/architecture/0001-deterministic-first-entity-resolution.md) for why
deterministic matching comes before any LLM call, and
[the orchestration topology doc](docs/architecture/orchestration-topology.md) for the
agent communication diagram and the reconciliation state machine — both actually
rendered and visually verified, not just written and hoped.

## Quickstart (under 5 minutes)

```sh
git clone https://github.com/SoniaMehta14/pavedroad-playbook.git
cd pavedroad-playbook
uv sync --group dev
uv run python examples/quickstart.py
```

No API key required. That last command generates Kestrel's messy synthetic data,
resolves customer identity across all three systems, generates AR invoices, reconciles
them through the Analyst/Validator pipeline, and prints a cost report — the whole
reference implementation, end to end, in about a second. Set `ANTHROPIC_API_KEY` first
to see the LLM-assisted paths light up with real routing and cost tracking instead of
the (fully supported) deterministic-only mode.

To run the test suite and see the evaluation numbers below reproduced yourself:

```sh
uv run pytest                    # 146 tests
uv run pytest tests/evals/ -s    # prints the accuracy and cost numbers below
```

## Measured results

These are real numbers from this repo's own test runs against the synthetic Kestrel
corpus — reproduce them with the commands above. Nothing here is asserted without having
been measured first; see [`docs/evals.md`](docs/evals.md) for the full methodology and
two findings that didn't flatter the system, reported anyway.

**Cost savings from the routing table.** Running the reconciliation pipeline end to end:
45 LLM calls, $0.0675 actual cost versus $0.1125 an all-Opus baseline would have cost for
the same token counts — **40% saved**, split cleanly across the cheap/mid/expensive tiers
(15/15/15 calls). On this specific corpus, all-cheap and all-expensive routing
configurations land on *identical* reconciliation accuracy, because the Validator's
independent deterministic re-check not the Analyst's model tier is what actually
guards correctness. That's the two-agent design working as intended, not a coincidence.

**Entity resolution quality.** Deterministic-only matching (no LLM, no API cost) resolves
60% of records correctly for free: precision 0.632, recall 0.259, F1 0.367. Adding a
naive LLM-assist test fixture raises recall and resolution rate (0.845 vs 0.598) but
*drops* precision (0.415) — an honest artifact of a fixture that agrees with its top
candidate too easily, reported because an eval harness that only shows good news isn't
one you can trust.

**Reconciliation accuracy.** Multi-class exact-label accuracy of 0.471; binary
discrepancy-detection recall of 0.143 (5 of 35 true discrepancies caught) with the
current fixtures. These are first-pass baseline numbers, not a finished product — the
point of the harness in `src/evals/` is that these numbers are visible, gated in CI
against regression, and improvable the same data-driven way a real portco engagement
would improve them.

**Test suite:** 146 tests, ruff and mypy in strict mode clean, a CI regression gate that
fails the build if entity resolution or reconciliation quality drops below the measured
floor.

## About me

I've spent the last several years operating at the intersection of enterprise
architecture and engineering leadership — most substantially running IBM API Connect, a
$280M API management product line I grew past $350M while scaling the team from 35 to
70+ engineers across four countries. That work included replacing a Cassandra data layer
that couldn't maintain transaction integrity (engineers were spending multi-hour customer
calls hand-fixing corrupted databases) with Postgres, and running a customer-experience
transformation task force that cut escalations 60% using the same discipline this
repository is built on: instrument the baseline before you intervene, measure everything
against systems the business already trusts, and never ship a fix you can't explain. This
repository and the name "Paved Road" comes from that same instinct applied to AI
enablement: build the rails once, well, so the second workflow travels them instead of
mounting a fresh expedition.
