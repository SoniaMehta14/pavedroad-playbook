"""Human review queue for low-confidence entity matches.

Nothing below the deterministic and LLM confidence floors gets silently
auto-applied. A record either resolves with a confidence a human would
sign off on, or it waits here — this is the human-in-the-loop pattern from
the operating playbook made concrete in code.

In-memory for this reference implementation; Phase 4's state-first
orchestration store is the natural home for a persistent version once
review decisions need to survive a process restart.
"""

import uuid

from .models import MatchCandidate, ReviewQueueItem


class ReviewQueue:
    def __init__(self) -> None:
        self._items: dict[str, ReviewQueueItem] = {}

    def add(
        self,
        *,
        system: str,
        record_id: str,
        record_display: str,
        candidates: list[MatchCandidate],
        reason: str,
    ) -> str:
        item_id = str(uuid.uuid4())
        self._items[item_id] = ReviewQueueItem(
            item_id=item_id,
            system=system,
            record_id=record_id,
            record_display=record_display,
            candidates=candidates,
            reason=reason,
        )
        return item_id

    def pending(self) -> list[ReviewQueueItem]:
        return [item for item in self._items.values() if item.status == "pending"]

    def by_status(self, status: str) -> list[ReviewQueueItem]:
        """List every item in a given status — the general form of
        pending(), needed by the tool-calling surface so a reviewer can
        also see what's already been resolved or rejected."""
        return [item for item in self._items.values() if item.status == status]

    def get(self, item_id: str) -> ReviewQueueItem:
        return self._items[item_id]

    def resolve(self, item_id: str, *, canonical_id: str | None, note: str = "") -> ReviewQueueItem:
        """Close out a review item.

        canonical_id=None records an explicit human decision that this
        really is an unmatched or new entity — distinct from an item that
        was simply never reviewed.
        """
        item = self._items[item_id]
        item.status = "resolved" if canonical_id is not None else "rejected"
        item.resolved_canonical_id = canonical_id
        item.reviewer_note = note
        return item

    def __len__(self) -> int:
        return len(self._items)
