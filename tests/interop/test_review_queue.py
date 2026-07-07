from interop.review_queue import ReviewQueue


def test_added_item_is_pending() -> None:
    queue = ReviewQueue()
    item_id = queue.add(
        system="psa",
        record_id="PSA-1",
        record_display="no name (PSA-1)",
        candidates=[],
        reason="no name",
    )
    pending = queue.pending()
    assert len(pending) == 1
    assert pending[0].item_id == item_id
    assert pending[0].status == "pending"


def test_resolve_with_canonical_id_marks_resolved() -> None:
    queue = ReviewQueue()
    item_id = queue.add(
        system="psa", record_id="PSA-1", record_display="x", candidates=[], reason="weak signal"
    )
    resolved = queue.resolve(item_id, canonical_id="UNIFIED-0001", note="confirmed by ops")

    assert resolved.status == "resolved"
    assert resolved.resolved_canonical_id == "UNIFIED-0001"
    assert resolved.reviewer_note == "confirmed by ops"
    assert queue.pending() == []


def test_resolve_with_no_canonical_id_marks_rejected() -> None:
    queue = ReviewQueue()
    item_id = queue.add(
        system="psa", record_id="PSA-1", record_display="x", candidates=[], reason="weak signal"
    )
    resolved = queue.resolve(item_id, canonical_id=None, note="genuinely a new customer")

    assert resolved.status == "rejected"
    assert resolved.resolved_canonical_id is None


def test_len_reflects_total_items_regardless_of_status() -> None:
    queue = ReviewQueue()
    item_id = queue.add(
        system="psa", record_id="PSA-1", record_display="x", candidates=[], reason="r"
    )
    queue.resolve(item_id, canonical_id="UNIFIED-0001")
    assert len(queue) == 1
