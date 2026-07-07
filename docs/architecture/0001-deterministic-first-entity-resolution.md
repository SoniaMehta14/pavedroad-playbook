# ADR 0001: Deterministic-first, LLM-second entity resolution

## Status

Accepted. Implemented in `src/interop/`.

## Context

Kestrel Systems' customer identity lives in three places that were never designed to
agree: a CRM, a billing system, and a PSA scheduling tool (see the
[AI Diligence Scorecard](../../playbook/AI_DILIGENCE_SCORECARD.md)'s worked example,
section A1). The interoperability layer's job is to resolve every raw record in all
three systems to a single canonical customer, so that an orchestration layer or a
tool-calling agent can ask "who is this customer" and get one trustworthy answer instead
of three disagreeing ones.

The tempting shortcut is to hand every record to an LLM and ask it to match them. That
approach is real code with a real demo, but it is also expensive at volume, slow, harder
to audit than a rule, and — critically — nondeterministic in exactly the way the AI
adoption playbook warns against building trust on. A CFO or a compliance officer asking
"why did record X get merged into customer Y" deserves an answer better than "the model
decided."

## Decision

Resolution runs as a three-stage cascade, in this order, and a record only proceeds to
the next stage if the previous one could not confidently place it:

1. **Deterministic key matching.** If a billing record carries a `crm_account_id`
   foreign key (only true for customers onboarded 2021 or later — the same finding as
   the scorecard's A1 item), that is a 1.0-confidence match. No fuzzy logic, no LLM, no
   cost. This is free and it is right whenever it fires.

2. **Deterministic name matching.** Every raw name is normalized (lowercased,
   punctuation stripped, legal suffixes dropped, known abbreviations expanded) and scored
   against the canonical registry with a plain string-similarity function
   (`difflib.SequenceMatcher`, standard library — see `normalize.py`). Two thresholds
   govern the outcome:
   - **≥ 0.95** — treated as an exact match; auto-accepted.
   - **0.85–0.95** — a confident fuzzy match; auto-accepted.
   - **0.55–0.85** — an *ambiguous residual*. Not confident enough to accept, but not
     so weak that asking for help is pointless.
   - **< 0.55** — too weak a signal to bother an LLM with. Straight to human review.

3. **LLM-assisted resolution, only for the ambiguous residual.** Records in the
   0.55–0.85 band go to an LLM (via the vendor-neutral adapter layer, defaulting to the
   cheapest tier — `claude-haiku-4-5` — because this is a narrow, low-difficulty
   classification task, not a reasoning task) with the candidate names it's choosing
   between. The LLM's own stated confidence is checked too: below 0.75, its answer is
   *still* not auto-applied.

4. **Human review queue, for everything the first three stages couldn't place.** No
   silent override, ever. A record with no confident deterministic match, no LLM
   resolver configured, or an LLM answer below the acceptance threshold lands in
   `ReviewQueue` with the candidates and the reason attached, and stays there until a
   human closes it out.

## Why this order, specifically

**Cost.** Deterministic matching is free and runs on every record. In the Kestrel
corpus, the exact-key path alone resolves every post-2021 billing record without a
single model call. Reserving the LLM for the residual — typically a minority of records
— is the same discipline as the orchestration layer's routing table in Phase 4: cheap
first, expensive only on documented escalation criteria.

**Auditability.** A deterministic match has a reproducible reason: this key matched
that key, or this name scored 0.91 against that name. That reason survives a CFO asking
about it, the same way the diligence scorecard insists every score cite evidence rather
than an impression. An LLM's "I think these are the same company" is a real signal, but
it is not the same kind of evidence, and it should not be treated as one.

**Latency and reproducibility.** Deterministic matching is synchronous, has no
provider dependency, and produces the same output on every run — which is why the
synthetic dataset generator is seeded (`data/kestrel/generator.py`) and why this
pipeline's deterministic stage has no hidden nondeterminism of its own. Tests can assert
exact outcomes for the deterministic stages without mocking anything.

**Trust, in the adoption sense.** The playbook's adoption thesis is that the trust
problem is solved by keeping humans as the architects of the system — visible gates,
not a black box. A resolution pipeline that only ever asks an LLM when deterministic
signal genuinely runs out, and that never lets even an LLM's answer skip human review
below a confidence floor, is that thesis in code.

## Threshold choices, and their honest limits

The specific numbers (0.55, 0.85, 0.95, 0.75) were chosen by reasoning about what each
band should mean, not fit against a large labeled dataset — this reference
implementation doesn't have one at the scale a production tuning pass would use. They
are deliberately conservative: it is worse to auto-merge two different customers than
to send an extra record to review. If this pipeline were adapted for a real portco, the
right next step is exactly what Phase 5's evaluation harness measures: score these
thresholds against a growing golden dataset and move them based on precision/recall, not
intuition.

`DeterministicMatcher._best_registry_match` and `candidates_for_name` are O(n) scans
against the whole registry for every incoming record. At Kestrel's ~40-customer scale
this is instant. A real deployment at thousands of customers would need blocking (for
example, grouping candidates by state or a name prefix before scoring) so the matcher
isn't comparing every record against every other record — out of scope here, but worth
flagging before anyone lifts this code onto a larger corpus.

## What is explicitly out of scope for this pipeline

- **Equipment/product catalog normalization.** The PSA `equipment_description` field
  (free text mixing make, model, and category) is not resolved by this module. It's
  exposed as-is through the tool-calling interface, sanitized against prompt injection
  but not semantically normalized — the scorecard's worked example calls this out as a
  distinct second-wave opportunity, not part of customer identity resolution.
- **Cross-system schema-agnostic design.** `resolve.py`'s entry point takes Kestrel's
  specific raw record types (`data.kestrel.models`) directly, not a generic adapter
  interface. The reusable parts of this design are `normalize.py`, `sanitize.py`,
  `review_queue.py`, and the threshold cascade itself in `deterministic.py`; the
  system-specific "raw record → name to compare" glue is what would change per
  deployment. A production version would define that glue per target system rather
  than importing a synthetic-data package.

## Consequences

- Every merge decision the pipeline makes is traceable to a `ResolutionOutcome` with a
  `method` (`exact_key`, `exact_name`, `fuzzy_name`, `llm`, `new_entity`, or
  `unresolved`) and a `confidence`, which is what makes the pipeline's output auditable
  rather than asserted.
- The LLM adapter dependency is optional (`llm_resolver=None` is a valid, fully
  supported configuration) — the deterministic stages and the review queue work
  standalone, which matters for a regulated deployment that cannot send customer data
  to a third-party model at all.
- Tests for the deterministic stages require no network access and no API key; tests
  for the LLM stage inject a fake provider. Nothing in this pipeline's test suite
  depends on live model behavior.
