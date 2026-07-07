"""Pydantic models for Kestrel Systems' three overlapping source systems.

Kestrel is the fictional equipment-rental vertical SaaS company from the AI
Diligence Scorecard's worked example (Tier 2, "ready with paving"). Its
customer truth lives in three places that were never designed to agree: a
Salesforce-style CRM, a QuickBooks-style billing system, and a PSA
scheduling tool. Raw records are messy by construction — fields are
optional, free text hides structured facts, and identifiers don't line up
across systems — because that is what a real mid-market data estate looks
like, not what a clean seed script would produce.
"""

from pydantic import BaseModel


class CRMAccountRecord(BaseModel):
    """A raw Salesforce-style CRM account export row."""

    account_id: str
    account_name: str
    primary_contact_email: str | None = None
    phone: str | None = None
    created_date: str  # ISO 8601 — the one system that's date-consistent
    billing_state: str | None = None


class BillingCustomerRecord(BaseModel):
    """A raw QuickBooks-style billing export row.

    crm_account_id is populated only for customers onboarded after the 2021
    system cutover — matching the scorecard finding that ~900 legacy
    accounts have no shared key with the CRM at all.
    """

    customer_id: str
    customer_name: str
    crm_account_id: str | None = None
    billing_email: str | None = None
    billing_address: str | None = None
    signup_date: str  # MM/DD/YYYY
    payment_terms: str | None = None


class PSAJobRecord(BaseModel):
    """A raw scheduling/PSA tool export row.

    The messiest of the three: customer identity is frequently entered as
    free text with no foreign key at all, and the equipment field mixes
    make, model, and category into one string a technician typed in a
    hurry.
    """

    job_id: str
    customer_name_raw: str | None = None
    equipment_description: str
    scheduled_date: str  # inconsistent formats, occasionally malformed
    technician: str | None = None


class CanonicalCustomer(BaseModel):
    """Ground truth: the real-world entity behind the noisy records.

    Only the generator and the eval harness construct these directly.
    Resolution code must never special-case a canonical_id — that would
    make the eval it's supposed to be checked against meaningless.
    """

    canonical_id: str
    canonical_name: str
    industry_segment: str
    onboarded_year: int


class GroundTruthLink(BaseModel):
    """One raw record's true canonical identity, for eval scoring."""

    canonical_id: str
    system: str  # "crm" | "billing" | "psa"
    record_id: str


class KestrelDataset(BaseModel):
    """A complete generated corpus: three messy exports plus ground truth."""

    seed: int
    canonical_customers: list[CanonicalCustomer]
    crm_records: list[CRMAccountRecord]
    billing_records: list[BillingCustomerRecord]
    psa_records: list[PSAJobRecord]
    ground_truth: list[GroundTruthLink]
