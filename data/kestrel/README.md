# Kestrel Systems synthetic dataset

Kestrel Systems is the fictional equipment-rental vertical SaaS company from the
[AI Diligence Scorecard](../../playbook/AI_DILIGENCE_SCORECARD.md)'s worked example. This
package regenerates its messy customer data on demand — nothing here is a static fixture
file, because static fixtures go stale and stop testing anything.

## Shape

Three overlapping, deliberately inconsistent exports, all describing the same ~40
canonical customers:

- **CRM** (`CRMAccountRecord`) — Salesforce-style, dates are ISO 8601 (the one clean
  system), ~5-10% missing contact fields, ~10% of customers have a duplicate row.
- **Billing** (`BillingCustomerRecord`) — QuickBooks-style, US date format, a
  `crm_account_id` join key that exists *only* for customers onboarded 2021 or later
  (matching the scorecard's finding that ~900 legacy accounts have no shared key at all).
- **PSA** (`PSAJobRecord`) — the messiest: free-text customer names (~20% missing
  entirely), free-text equipment descriptions mixing make/model/category, and dates in
  three different formats including occasional malformed entries.

`generate_kestrel_dataset(seed=...)` also returns `ground_truth`: the real canonical
identity behind every raw record, across all three systems. This is what
`src/interop`'s resolution engine is graded against, and what Phase 5's eval harness
uses for golden-dataset scoring. Resolution code must never read `ground_truth` or
special-case a `canonical_id` — that would make the score it produces meaningless.

Two PSA records carry a deliberate prompt-injection payload in
`equipment_description`, so the tool-calling layer's sanitization
(`src/interop/sanitize.py`) has something real to neutralize instead of a
hypothetical.

## Usage

```python
from data.kestrel import generate_kestrel_dataset

dataset = generate_kestrel_dataset(seed=42)
len(dataset.canonical_customers)  # 40
len(dataset.crm_records)          # ~44 (includes ~10% duplicate rows)
```

Same seed, same corpus, every time — tests and evals aren't chasing a moving target.
