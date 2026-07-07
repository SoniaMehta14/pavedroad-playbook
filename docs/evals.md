# The evaluation harness, and how it generalizes

`src/evals` answers the question every AI workflow eventually gets asked in a board
meeting: how do we know it's right? This document explains what the harness does for
Kestrel's two workflows, and — more importantly — the repeatable method underneath it
that applies to any workflow a portco FDE pod would build under the
[Enterprise AI Playbook](../playbook/ENTERPRISE_AI_PLAYBOOK.md).

## What's actually in it

Four pieces, each with its own tests:

- **Golden datasets** (`golden.py`) — built from the same seeded generators as
  everything else in this repo. Ground truth is known because the generator decided
  what to inject, not because a human labeled it after the fact. No fixture file to
  keep in sync by hand.
- **Entity resolution scoring** (`entity_resolution.py`) — pairwise precision, recall,
  and F1 against `data/kestrel`'s ground truth. Pairwise, not direct ID comparison,
  because the resolver's canonical IDs and the golden IDs live in different namespaces
  by design.
- **Reconciliation scoring** (`reconciliation.py`) — two views of the same
  Analyst/Validator run: exact-label accuracy, and a binary "did we catch that
  something was wrong at all" precision/recall. The second view is usually the more
  operationally important one — a business cares more about catching the bad invoice
  than filing it under the exactly correct reason code.
- **Cost-vs-accuracy frontier** (`cost_frontier.py`) — runs the same golden corpus
  through several routing configurations (all-cheap, all-mid, all-expensive, the
  production mixed table) and reports cost against accuracy for each, so the tradeoff
  is a decision made with numbers, not a guess.

All of it is gated in CI (`tests/evals/test_regression_gates.py`, the
`eval_gate` marker, its own named step in `.github/workflows/ci.yml`): a change that
degrades matching or reconciliation quality below a measured floor fails the build.

## The numbers, reported honestly

Two findings came out of actually running this harness against the real corpus, and
both are left in the codebase and this document rather than smoothed over, because an
eval harness that only reports good news isn't one you can trust:

**A naive "always agree" LLM-assist fixture trades precision for recall.** Entity
resolution deterministic-only scores precision=0.632, recall=0.259, resolving 60% of
records for free with zero model calls. Adding an LLM resolver that blindly accepts its
top candidate raises recall and resolution rate but drops precision to 0.415 — an
honest artifact of the test fixture's crude judgment, not a claim that LLM assistance
makes resolution worse in general. A competent resolver should reject implausible
candidates; this fixture doesn't, and the numbers say so plainly.

**The Validator's independent check dominates reconciliation accuracy, regardless of
model tier.** On the measured corpus, all four routing configurations — including
all-cheap and all-expensive — land on identical reconciliation accuracy while cost
scales with tier. Tracing why: none of the corpus's date-drift invoices happen to fall
inside the Validator's stricter tolerance band, so the Validator's own deterministic
re-check overrides the Analyst's proposal every time, independent of which model
proposed it. That is the two-agent design working as intended — see
[the topology diagram](architecture/orchestration-topology.md) — not a flaw in the
frontier report. The practical reading for a portco: independent verification can let
you route the boring case to the cheap tier with no accuracy cost, because a second,
deterministic check is what's actually guarding correctness.

## How this generalizes to any portco workflow

None of the four pieces above are Kestrel-specific machinery. They are a method, and
the method is the same one the playbook already prescribes for the Day-30 baseline and
the Day-90 attribution deck — applied here to model quality instead of business KPIs.

**1. Generate or capture a golden dataset before you trust any number.** For a new
workflow with no production history yet, synthesize one the way `data/kestrel` does:
build a small set of canonical "true" answers, then generate realistic noisy inputs
around them, keeping the mapping back to ground truth. Once the workflow is live,
graduate to sampling and hand-labeling real cases — the scoring code doesn't change,
only where the golden set comes from. This is the same discipline as the playbook's
Day-30 gate: measure before you intervene, or there's nothing to compare the
intervention against later.

**2. Pick a scorer that matches the workflow's actual decision shape, not a generic
one.** A matching/deduplication workflow (entity resolution, vendor dedup, contract
clause matching) wants pairwise precision/recall. A classification-with-consequences
workflow (invoice reconciliation, claims triage, support-ticket routing) wants both an
exact-label view and a binary "did we catch the risk" view, because those two
questions have different stakeholders — an ops lead wants exact accuracy, a controller
wants to know nothing costly slipped through. Building the wrong scorer (say, accuracy
alone) hides exactly the failure mode a business cares most about.

**3. Gate on a measured floor, never an invented one.** Every threshold in
`test_regression_gates.py` came from running the eval once and reading the actual
number, then setting the floor below it with margin. A floor picked without measuring
first is either so loose it never fires or so tight it's flaky from day one — both
failure modes teach the team to ignore the gate, which defeats the purpose.

**4. Build the cost-vs-accuracy frontier before committing to a model tier in
production.** `cost_frontier.py`'s pattern — same golden corpus, same task, varying
only the routing table — is exactly the exercise a portco should run before locking in
"we always use the expensive model here." Sometimes, like Kestrel's reconciliation
workflow, the honest result is that a cheaper tier costs less with no accuracy loss,
because a downstream check is already doing the real work of guarding correctness.
Sometimes it isn't, and the frontier is what tells you which case you're in — the same
"measure it, don't assert it" standard applied to the Day-90 ROI deck's counterfactual,
applied here one layer down at the model-routing decision.

The pod that builds the first workflow's harness this way leaves the second workflow's
team something to extend, not something to reinvent — the same paved-road principle as
the rest of this repository, one layer deeper.
