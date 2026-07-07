"""Kestrel Systems: the fictional equipment-rental vertical SaaS company used
throughout this repository's reference implementation and worked examples.

See playbook/AI_DILIGENCE_SCORECARD.md for the diligence narrative this
dataset is built to match, and data/kestrel/README.md for the dataset shape.
"""

from data.kestrel.generator import generate_kestrel_dataset
from data.kestrel.invoices import (
    EQUIPMENT_RATES,
    InvoiceLineItem,
    generate_invoices,
    generate_invoices_with_ground_truth,
)
from data.kestrel.models import (
    BillingCustomerRecord,
    CanonicalCustomer,
    CRMAccountRecord,
    GroundTruthLink,
    KestrelDataset,
    PSAJobRecord,
)

__all__ = [
    "EQUIPMENT_RATES",
    "BillingCustomerRecord",
    "CRMAccountRecord",
    "CanonicalCustomer",
    "GroundTruthLink",
    "InvoiceLineItem",
    "KestrelDataset",
    "PSAJobRecord",
    "generate_invoices",
    "generate_invoices_with_ground_truth",
    "generate_kestrel_dataset",
]
