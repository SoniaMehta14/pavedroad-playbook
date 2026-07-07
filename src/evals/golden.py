"""Golden dataset builders.

Every golden dataset in this package is generated alongside the synthetic
data it's paired with, from the same seeded generators used elsewhere in
the reference implementation — there is no hand-labeled fixture file to
keep in sync by hand. Ground truth is known because the generator itself
decided what to inject (a name variant, a discrepancy type), not because
a human annotated it after the fact.
"""

from dataclasses import dataclass

from data.kestrel import (
    InvoiceLineItem,
    KestrelDataset,
    generate_invoices_with_ground_truth,
    generate_kestrel_dataset,
)


@dataclass
class ReconciliationGolden:
    dataset: KestrelDataset
    invoices: list[InvoiceLineItem]
    true_discrepancy: dict[str, str]


def build_entity_resolution_golden(seed: int = 42) -> KestrelDataset:
    """A Kestrel corpus with its ground_truth field intact — the golden
    dataset src/evals/entity_resolution.py scores DeterministicMatcher
    and the LLM-assisted residual against."""
    return generate_kestrel_dataset(seed=seed)


def build_reconciliation_golden(seed: int = 42, invoice_seed: int = 100) -> ReconciliationGolden:
    """A Kestrel corpus plus a matching invoice batch with true
    discrepancy labels — the golden dataset
    src/evals/reconciliation.py scores the Analyst/Validator pipeline
    against."""
    dataset = generate_kestrel_dataset(seed=seed)
    invoices, true_discrepancy = generate_invoices_with_ground_truth(dataset, seed=invoice_seed)
    return ReconciliationGolden(
        dataset=dataset, invoices=invoices, true_discrepancy=true_discrepancy
    )
