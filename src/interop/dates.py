"""Lenient date parsing for comparing dates across Kestrel's inconsistent
source-system formats.

The PSA export alone uses three different date formats plus occasional
malformed data-entry errors (see data/kestrel/generator.py). Rather than
have every downstream consumer re-solve that mess, this module tries each
known format and returns None on total failure — an unparseable date is
itself a signal (genuinely ambiguous), not a crash.
"""

from datetime import date, datetime

_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"]


def parse_flexible_date(raw: str) -> date | None:
    """Try each known Kestrel date format in turn; None if none match."""
    for fmt in _FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def day_distance(a: str, b: str) -> int | None:
    """Absolute day distance between two flexibly-parsed date strings, or
    None if either side doesn't parse at all."""
    parsed_a = parse_flexible_date(a)
    parsed_b = parse_flexible_date(b)
    if parsed_a is None or parsed_b is None:
        return None
    return abs((parsed_a - parsed_b).days)
