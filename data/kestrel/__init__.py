"""Kestrel Systems: the fictional equipment-rental vertical SaaS company used
throughout this repository's reference implementation and worked examples.

See playbook/AI_DILIGENCE_SCORECARD.md for the diligence narrative this
dataset is built to match, and data/kestrel/README.md for the dataset shape.
"""

from data.kestrel.generator import generate_kestrel_dataset
from data.kestrel.models import (
    BillingCustomerRecord,
    CanonicalCustomer,
    CRMAccountRecord,
    GroundTruthLink,
    KestrelDataset,
    PSAJobRecord,
)

__all__ = [
    "BillingCustomerRecord",
    "CRMAccountRecord",
    "CanonicalCustomer",
    "GroundTruthLink",
    "KestrelDataset",
    "PSAJobRecord",
    "generate_kestrel_dataset",
]
