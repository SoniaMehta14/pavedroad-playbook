"""Prompt-injection defenses for free text pulled from untrusted source
systems (CRM/billing/PSA exports, and anything a customer or technician
typed into a text field).

Three defenses, applied to any free-text field before it's embedded in a
prompt or returned as tool output: delimiting (mark the boundary between
data and instructions unambiguously), content flagging (detect known
injection markers so callers can choose to reject rather than silently
pass through), and length caps (bound the blast radius of any single
field, and prevent a text field from becoming an exfiltration or DoS
channel for arbitrarily large content).

Flagging is a signal, not a guarantee — a determined injection can still
evade these specific patterns. It exists so obviously malicious content
gets caught before it ever reaches a model, not to be the only layer of
defense. See docs/architecture/0001-deterministic-first-entity-resolution.md
for where this sits in the pipeline, and
tests/interop/test_sanitize.py for the neutralization test against the
synthetic dataset's deliberately-injected PSA records.
"""

import re

from pydantic import BaseModel

DEFAULT_MAX_LENGTH = 500

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |the )?(prior|previous|above) instructions", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"\byou are now\b", re.IGNORECASE),
    re.compile(r"disregard (the )?(above|prior|previous)", re.IGNORECASE),
    re.compile(r"</?\w+>"),  # embedded pseudo-XML tags attempting to close a delimiter early
]


class SanitizedText(BaseModel):
    text: str
    flagged: bool
    flags: list[str]
    truncated: bool


def sanitize_free_text(raw: str, *, max_length: int = DEFAULT_MAX_LENGTH) -> SanitizedText:
    """Clean and flag a single free-text field for safe downstream use."""
    truncated = len(raw) > max_length
    text = raw[:max_length]

    flags = [pattern.pattern for pattern in _INJECTION_PATTERNS if pattern.search(text)]

    return SanitizedText(text=text, flagged=bool(flags), flags=flags, truncated=truncated)


def delimit_untrusted(text: str, label: str) -> str:
    """Wrap untrusted content in an explicit, labeled boundary for safe
    prompt embedding.

    This makes the boundary visible to the model; it does not itself
    defend against delimiter-escape attempts — sanitize_free_text's
    flagging (including its check for embedded pseudo-XML tags) is what
    catches those. Use both together, not either alone.
    """
    return f"<{label}>\n{text}\n</{label}>"
