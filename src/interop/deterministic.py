"""Deterministic-first entity resolution: exact keys, then exact normalized
names, then fuzzy name similarity. No LLM calls in this module — see
docs/architecture/0001-deterministic-first-entity-resolution.md for why
that boundary is deliberate.

CRM is treated as the system of record: resolve_crm_self() first collapses
CRM's own duplicate rows into a canonical registry, then billing and PSA
records are matched onto that registry via resolve_billing_record() /
resolve_psa_record(). This mirrors the target end-state the AI Diligence
Scorecard's data-readiness rubric scores toward — "clear system of record
per domain, other systems sync from it."
"""

from data.kestrel.models import BillingCustomerRecord, CRMAccountRecord, PSAJobRecord

from .models import MatchCandidate, MatchMethod, ResolutionOutcome, UnifiedCustomer
from .normalize import name_similarity

EXACT_KEY_CONFIDENCE = 1.0
EXACT_NAME_CONFIDENCE = 0.95
FUZZY_AUTO_ACCEPT = 0.85  # at or above this, accept the fuzzy match outright
FUZZY_LLM_FLOOR = 0.55  # below this, the signal is too weak to bother asking an LLM


class DeterministicMatcher:
    """Builds a canonical customer registry from CRM records, then matches
    billing and PSA records onto it using exact keys and name similarity.
    """

    def __init__(self) -> None:
        self._registry: dict[str, UnifiedCustomer] = {}
        self._crm_account_id_to_canonical: dict[str, str] = {}
        self._next_id = 1

    @property
    def registry(self) -> list[UnifiedCustomer]:
        return list(self._registry.values())

    def name_for(self, canonical_id: str) -> str:
        return self._registry[canonical_id].name

    def attach(self, canonical_id: str, system: str, record_id: str) -> None:
        """Record that a raw record belongs to an already-known entity.

        Public because the pipeline (resolve.py) calls this after an
        LLM-assisted or human review decision, not just after a
        deterministic match.
        """
        self._registry[canonical_id].source_record_ids.setdefault(system, []).append(record_id)

    def candidates_for_name(self, name: str, *, top_k: int = 3) -> list[MatchCandidate]:
        """Score a free-text name against every registry entity, best first."""
        scored = [
            (entity.canonical_id, name_similarity(name, entity.name))
            for entity in self._registry.values()
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [
            MatchCandidate(canonical_id=cid, score=score, method="fuzzy_name")
            for cid, score in scored[:top_k]
            if score > 0.0
        ]

    def resolve_crm_self(self, crm_records: list[CRMAccountRecord]) -> list[ResolutionOutcome]:
        """Dedup CRM's own duplicate rows into the canonical registry."""
        outcomes: list[ResolutionOutcome] = []
        for record in crm_records:
            best_id, best_score = self._best_registry_match(record.account_name)

            if best_id is not None and best_score >= FUZZY_AUTO_ACCEPT:
                canonical_id = best_id
                method: MatchMethod = (
                    "exact_name" if best_score >= EXACT_NAME_CONFIDENCE else "fuzzy_name"
                )
                confidence = best_score
            else:
                canonical_id = self._new_canonical_id()
                self._registry[canonical_id] = UnifiedCustomer(
                    canonical_id=canonical_id, name=record.account_name
                )
                method = "new_entity"
                confidence = 1.0  # certain this is *a* real entity; not claiming it's unique

            self.attach(canonical_id, "crm", record.account_id)
            self._crm_account_id_to_canonical[record.account_id] = canonical_id

            outcomes.append(
                ResolutionOutcome(
                    system="crm",
                    record_id=record.account_id,
                    matched_canonical_id=canonical_id,
                    confidence=confidence,
                    method=method,
                )
            )
        return outcomes

    def resolve_billing_record(
        self, record: BillingCustomerRecord
    ) -> tuple[ResolutionOutcome, list[MatchCandidate]]:
        if record.crm_account_id and record.crm_account_id in self._crm_account_id_to_canonical:
            canonical_id = self._crm_account_id_to_canonical[record.crm_account_id]
            self.attach(canonical_id, "billing", record.customer_id)
            return (
                ResolutionOutcome(
                    system="billing",
                    record_id=record.customer_id,
                    matched_canonical_id=canonical_id,
                    confidence=EXACT_KEY_CONFIDENCE,
                    method="exact_key",
                ),
                [],
            )

        candidates = self.candidates_for_name(record.customer_name)
        return self._resolve_by_name(
            system="billing", record_id=record.customer_id, candidates=candidates
        )

    def resolve_psa_record(
        self, record: PSAJobRecord
    ) -> tuple[ResolutionOutcome, list[MatchCandidate]]:
        if not record.customer_name_raw:
            return (
                ResolutionOutcome(
                    system="psa",
                    record_id=record.job_id,
                    matched_canonical_id=None,
                    confidence=0.0,
                    method="unresolved",
                ),
                [],
            )
        candidates = self.candidates_for_name(record.customer_name_raw)
        return self._resolve_by_name(system="psa", record_id=record.job_id, candidates=candidates)

    def _resolve_by_name(
        self, *, system: str, record_id: str, candidates: list[MatchCandidate]
    ) -> tuple[ResolutionOutcome, list[MatchCandidate]]:
        if not candidates:
            return (
                ResolutionOutcome(
                    system=system,
                    record_id=record_id,
                    matched_canonical_id=None,
                    confidence=0.0,
                    method="unresolved",
                ),
                [],
            )

        top = candidates[0]
        if top.score >= EXACT_NAME_CONFIDENCE:
            self.attach(top.canonical_id, system, record_id)
            method: MatchMethod = "exact_name"
        elif top.score >= FUZZY_AUTO_ACCEPT:
            self.attach(top.canonical_id, system, record_id)
            method = "fuzzy_name"
        else:
            # Ambiguous or weak residual — the caller (resolve.py) decides
            # whether to escalate to the LLM resolver or the review queue
            # based on candidates[0].score.
            return (
                ResolutionOutcome(
                    system=system,
                    record_id=record_id,
                    matched_canonical_id=None,
                    confidence=top.score,
                    method="unresolved",
                ),
                candidates,
            )

        return (
            ResolutionOutcome(
                system=system,
                record_id=record_id,
                matched_canonical_id=top.canonical_id,
                confidence=top.score,
                method=method,
            ),
            candidates,
        )

    def _best_registry_match(self, name: str) -> tuple[str | None, float]:
        if not self._registry:
            return None, 0.0
        best_id: str | None = None
        best_score = 0.0
        for candidate_id, entity in self._registry.items():
            score = name_similarity(name, entity.name)
            if score > best_score:
                best_score = score
                best_id = candidate_id
        return best_id, best_score

    def _new_canonical_id(self) -> str:
        canonical_id = f"UNIFIED-{self._next_id:04d}"
        self._next_id += 1
        return canonical_id
