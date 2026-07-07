"""Reconciliation evaluation: accuracy against golden discrepancy labels.

Two views of the same result, because they answer different questions a
CFO and an ops lead ask differently:

- Multi-class accuracy: did the pipeline get the *exact* discrepancy type
  right (amount mismatch vs. unknown customer vs. ...)?
- Binary discrepancy detection (precision/recall/F1): did the pipeline
  correctly flag that *something* was wrong at all, regardless of which
  specific type? This is the risk-control question, and it is usually the
  more operationally important one — a business cares more about "did we
  catch the bad invoice" than "did we file it under exactly the right
  reason code."
"""

from pydantic import BaseModel

from orchestration.pipeline import ReconciliationRunResult


class ReconciliationScore(BaseModel):
    accuracy: float
    detection_precision: float
    detection_recall: float
    detection_f1: float
    total_invoices: int
    correct_exact_label: int
    true_discrepancies: int
    detected_discrepancies: int
    correctly_detected_discrepancies: int


def _predicted_labels(result: ReconciliationRunResult) -> dict[str, str]:
    predicted: dict[str, str] = dict.fromkeys(result.closed_invoice_ids, "none")
    for item in result.human_review:
        predicted[item.invoice_id] = item.validator_decision.discrepancy
    return predicted


def score_reconciliation(
    result: ReconciliationRunResult, true_discrepancy: dict[str, str]
) -> ReconciliationScore:
    """Score a completed reconciliation run against golden discrepancy
    labels (see src/evals/golden.py). Requires the run to have covered
    exactly the invoices the golden labels describe — a partial (halted)
    run should be scored against a matching subset, not the full golden
    set, or this raises rather than silently under-counting.
    """
    predicted = _predicted_labels(result)
    if set(predicted.keys()) != set(true_discrepancy.keys()):
        raise ValueError(
            "golden labels and run result must cover exactly the same invoices — "
            f"{len(predicted)} predicted vs {len(true_discrepancy)} golden "
            "(a halted run should be scored against a matching subset)"
        )

    total = len(true_discrepancy)
    correct = sum(1 for inv_id, true in true_discrepancy.items() if predicted[inv_id] == true)

    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_discrepancy_count = 0
    detected_count = 0

    for inv_id, true_label in true_discrepancy.items():
        true_is_discrepancy = true_label != "none"
        predicted_is_discrepancy = predicted[inv_id] != "none"
        if true_is_discrepancy:
            true_discrepancy_count += 1
        if predicted_is_discrepancy:
            detected_count += 1
        if true_is_discrepancy and predicted_is_discrepancy:
            true_positive += 1
        elif not true_is_discrepancy and predicted_is_discrepancy:
            false_positive += 1
        elif true_is_discrepancy and not predicted_is_discrepancy:
            false_negative += 1

    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 0.0
    )
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return ReconciliationScore(
        accuracy=correct / total if total else 0.0,
        detection_precision=precision,
        detection_recall=recall,
        detection_f1=f1,
        total_invoices=total,
        correct_exact_label=correct,
        true_discrepancies=true_discrepancy_count,
        detected_discrepancies=detected_count,
        correctly_detected_discrepancies=true_positive,
    )
