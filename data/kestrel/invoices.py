"""Synthetic AR invoice line items for the invoice-reconciliation workflow
(src/orchestration).

Built on top of an already-generated KestrelDataset rather than folding
into data/kestrel/generator.py directly, so Phase 3's committed corpus is
untouched — this module layers a new fixture on top of it, keyed off the
same PSA jobs and equipment catalog.

Most invoices reflect a real PSA job cleanly; a deliberate fraction carry
each discrepancy type the reconciliation pipeline needs to exercise:
amount mismatches, phantom jobs, unknown customers, and service-date
drift (the genuinely ambiguous case — is this sloppy paperwork on a real
job, or a different job entirely?).
"""

import random
from datetime import date, timedelta

from pydantic import BaseModel

from interop.dates import parse_flexible_date

from .generator import _EQUIPMENT_CATALOG
from .models import KestrelDataset, PSAJobRecord

# One rate per catalog entry, applied to every name-variant of that
# equipment so a rate lookup works regardless of which variant the
# invoice or the PSA job happens to use.
_CATALOG_DAILY_RATES = [450.0, 600.0, 150.0, 275.0, 900.0]

EQUIPMENT_RATES: dict[str, float] = {
    variant: rate
    for catalog_entry, rate in zip(_EQUIPMENT_CATALOG, _CATALOG_DAILY_RATES, strict=True)
    for variant in catalog_entry
}

_FALLBACK_DATE = date(2026, 1, 15)
_UNKNOWN_CUSTOMER_NAME = "Zzyzx Industrial Holdings ###"


class InvoiceLineItem(BaseModel):
    """One AR invoice line, as it would arrive from the billing system —
    a customer name (possibly a variant, like every other Kestrel
    export), an equipment reference, an amount, and a service date."""

    invoice_id: str
    customer_name_billed: str
    equipment_billed: str
    service_date: str  # always clean ISO — the billing system, unlike PSA, is consistent
    days_billed: int
    amount_usd: float


def _anchor_date(job: PSAJobRecord) -> date:
    return parse_flexible_date(job.scheduled_date) or _FALLBACK_DATE


def generate_invoices(dataset: KestrelDataset, *, seed: int = 100) -> list[InvoiceLineItem]:
    """Generate one invoice per named PSA job in `dataset`, with a
    deliberate mix of clean matches and discrepancies:

    - ~60% clean: amount and date match the underlying job exactly.
    - ~15% amount mismatch: a real job, billed 20-50% over the rate.
    - ~10% phantom job: equipment/amount invented, no corresponding PSA
      job exists at all.
    - ~10% unknown customer: a name that won't resolve to any canonical
      customer, even fuzzily.
    - ~5% date drift: a real job, correct amount, but the service date is
      3-10 days off from the job's actual scheduled_date.

    PSA records with no customer_name_raw at all are skipped — there is
    nothing for an AR system to bill against without a customer name, so
    they wouldn't produce an invoice in the first place.
    """
    invoices, _ = _generate_invoices_with_labels(dataset, seed=seed)
    return invoices


def generate_invoices_with_ground_truth(
    dataset: KestrelDataset, *, seed: int = 100
) -> tuple[list[InvoiceLineItem], dict[str, str]]:
    """Same corpus as generate_invoices(), plus the true discrepancy label
    per invoice_id — known because the generator itself decided which
    discrepancy type (if any) to inject.

    Labels use the same vocabulary as
    orchestration.models.DiscrepancyKind ("none", "unknown_customer",
    "no_matching_job", "amount_mismatch", "date_drift") as plain strings
    rather than importing that type directly — data/ fixtures should not
    depend on src/orchestration, since the dependency runs the other way.
    This is the golden dataset src/evals scores the reconciliation
    pipeline against.
    """
    return _generate_invoices_with_labels(dataset, seed=seed)


def _generate_invoices_with_labels(
    dataset: KestrelDataset, *, seed: int
) -> tuple[list[InvoiceLineItem], dict[str, str]]:
    rng = random.Random(seed)
    named_jobs = [r for r in dataset.psa_records if r.customer_name_raw]

    invoices: list[InvoiceLineItem] = []
    labels: dict[str, str] = {}
    for i, job in enumerate(named_jobs):
        invoice_id = f"INV-{i + 1:05d}"
        days = rng.randint(1, 5)
        base_rate = EQUIPMENT_RATES.get(job.equipment_description, 300.0)
        roll = rng.random()

        if roll < 0.60:
            labels[invoice_id] = "none"
            invoices.append(
                InvoiceLineItem(
                    invoice_id=invoice_id,
                    customer_name_billed=job.customer_name_raw or "",
                    equipment_billed=job.equipment_description,
                    service_date=_anchor_date(job).isoformat(),
                    days_billed=days,
                    amount_usd=round(base_rate * days, 2),
                )
            )
        elif roll < 0.75:
            labels[invoice_id] = "amount_mismatch"
            overbill_factor = rng.uniform(1.2, 1.5)
            invoices.append(
                InvoiceLineItem(
                    invoice_id=invoice_id,
                    customer_name_billed=job.customer_name_raw or "",
                    equipment_billed=job.equipment_description,
                    service_date=_anchor_date(job).isoformat(),
                    days_billed=days,
                    amount_usd=round(base_rate * days * overbill_factor, 2),
                )
            )
        elif roll < 0.85:
            labels[invoice_id] = "no_matching_job"
            phantom_equipment = rng.choice(_EQUIPMENT_CATALOG)[0]
            phantom_date = _anchor_date(job) + timedelta(days=rng.randint(30, 90))
            invoices.append(
                InvoiceLineItem(
                    invoice_id=invoice_id,
                    customer_name_billed=job.customer_name_raw or "",
                    equipment_billed=phantom_equipment,
                    service_date=phantom_date.isoformat(),
                    days_billed=days,
                    amount_usd=round(rng.uniform(200, 900) * days, 2),
                )
            )
        elif roll < 0.95:
            labels[invoice_id] = "unknown_customer"
            invoices.append(
                InvoiceLineItem(
                    invoice_id=invoice_id,
                    customer_name_billed=_UNKNOWN_CUSTOMER_NAME,
                    equipment_billed=job.equipment_description,
                    service_date=_anchor_date(job).isoformat(),
                    days_billed=days,
                    amount_usd=round(base_rate * days, 2),
                )
            )
        else:
            labels[invoice_id] = "date_drift"
            drift_days = rng.randint(3, 10)
            invoices.append(
                InvoiceLineItem(
                    invoice_id=invoice_id,
                    customer_name_billed=job.customer_name_raw or "",
                    equipment_billed=job.equipment_description,
                    service_date=(_anchor_date(job) + timedelta(days=drift_days)).isoformat(),
                    days_billed=days,
                    amount_usd=round(base_rate * days, 2),
                )
            )

    return invoices, labels
