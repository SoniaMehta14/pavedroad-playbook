"""Name normalization and similarity for deterministic entity matching.

Kept dependency-free (difflib is stdlib) on purpose: the deterministic
matcher's whole value proposition is that it's fast, free, and auditable,
and pulling in a fuzzy-matching library for a few extra points of accuracy
would trade that away for a use case this repository doesn't need.
"""

import re
from difflib import SequenceMatcher

_LEGAL_SUFFIXES = {"llc", "inc", "co", "corp", "ltd", "company"}
_ABBREVIATIONS = {
    "eqpt": "equipment",
    "equip": "equipment",
    "constr": "construction",
    "mach": "machinery",
}


def normalize_name(name: str) -> str:
    """Reduce a company name to a comparable canonical form.

    Lowercases, strips punctuation, expands known abbreviations, and drops
    legal suffixes — "Blue Ridge Eqpt LLC" and "Blue Ridge Equipment"
    normalize to the same string. Deliberately does not attempt to expand
    acronyms ("BRER") or repair truncation ("Blue Ridge") — those variants
    are exactly the ambiguous residual this module hands off rather than
    guesses at.
    """
    lowered = name.lower()
    stripped = re.sub(r"[^\w\s]", " ", lowered)
    words = [w for w in stripped.split() if w not in _LEGAL_SUFFIXES]
    expanded = [_ABBREVIATIONS.get(w, w) for w in words]
    return " ".join(expanded)


def name_similarity(a: str, b: str) -> float:
    """Similarity in [0, 1] between two normalized names."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()
