"""Entity resolution evaluation: pairwise precision, recall, and F1.

Comparing resolver-assigned canonical IDs directly against ground-truth
canonical IDs doesn't work — the resolver's IDs ("UNIFIED-0001") and the
generator's golden IDs ("KEST-0001") live in different namespaces by
design (the resolver never sees ground truth, and shouldn't). Pairwise
evaluation sidesteps this entirely: for every pair of raw records, do the
resolver and the ground truth agree on whether they're the same
customer? This is the standard evaluation method for record linkage, and
it needs no ID-namespace alignment at all.

Known limitation: pairwise F1 is blind to singleton clusters (a record
correctly placed alone contributes zero pairs either way). This is an
accepted tradeoff of the method, not a bug — a full solution (e.g.
B-cubed) is more complex than this reference implementation needs.
"""

from itertools import combinations

from data.kestrel.models import GroundTruthLink
from pydantic import BaseModel

from interop.resolve import ResolutionReport

_RecordKey = tuple[str, str]


class EntityResolutionScore(BaseModel):
    precision: float
    recall: float
    f1: float
    predicted_pairs: int
    actual_pairs: int
    true_positive_pairs: int
    resolved_record_count: int
    total_record_count: int

    @property
    def resolution_rate(self) -> float:
        """Fraction of raw records placed into some cluster at all
        (deterministically or via the LLM-assisted residual), as opposed
        to landing in the human review queue unresolved."""
        if self.total_record_count == 0:
            return 0.0
        return self.resolved_record_count / self.total_record_count


def _clusters_to_pairs(
    clusters: dict[str, set[_RecordKey]],
) -> set[frozenset[_RecordKey]]:
    """All unordered pairs of records that share a cluster."""
    pairs: set[frozenset[_RecordKey]] = set()
    for members in clusters.values():
        for a, b in combinations(sorted(members), 2):
            pairs.add(frozenset((a, b)))
    return pairs


def score_entity_resolution(
    report: ResolutionReport, ground_truth: list[GroundTruthLink]
) -> EntityResolutionScore:
    """Score a resolution run's outcomes against golden ground truth.

    `report` is the pipeline's own output; `ground_truth` is the
    generator's known canonical mapping. Neither the resolver nor its
    input ever sees `ground_truth` — it exists only for this scoring
    step, exactly like a held-out test set.
    """
    predicted_clusters: dict[str, set[_RecordKey]] = {}
    for outcome in report.outcomes:
        if outcome.matched_canonical_id is not None:
            predicted_clusters.setdefault(outcome.matched_canonical_id, set()).add(
                (outcome.system, outcome.record_id)
            )

    actual_clusters: dict[str, set[_RecordKey]] = {}
    for link in ground_truth:
        actual_clusters.setdefault(link.canonical_id, set()).add((link.system, link.record_id))

    predicted_pairs = _clusters_to_pairs(predicted_clusters)
    actual_pairs = _clusters_to_pairs(actual_clusters)
    true_positives = predicted_pairs & actual_pairs

    precision = len(true_positives) / len(predicted_pairs) if predicted_pairs else 0.0
    recall = len(true_positives) / len(actual_pairs) if actual_pairs else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    resolved_count = sum(len(members) for members in predicted_clusters.values())

    return EntityResolutionScore(
        precision=precision,
        recall=recall,
        f1=f1,
        predicted_pairs=len(predicted_pairs),
        actual_pairs=len(actual_pairs),
        true_positive_pairs=len(true_positives),
        resolved_record_count=resolved_count,
        total_record_count=len(ground_truth),
    )
