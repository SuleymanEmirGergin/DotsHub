"""Canonical PII redaction — single source of truth.

Strips Turkish national IDs (11-digit TC kimlik), phone numbers, and
email addresses from free text before it hits any surface that could
leak them: database rows, external LLM APIs, logs, notifier webhooks,
email summaries, PDF exports.

Every entry point that handles user-typed text MUST call redact_pii()
before the text leaves the orchestrator boundary. A second
"local" redaction was living in services/llm_nlu_client.py; that has
been removed and re-imported from here so the regexes can't drift.

Replacement tokens are distinct (`[REDACTED_EMAIL]` / `[REDACTED_PHONE]`
/ `[REDACTED_ID]`) so downstream tools can still see the _kind_ of
information that was present — useful for debugging without
compromising privacy.
"""

import re

# Turkish TC Kimlik: exactly 11 digits, first digit non-zero.
# Stricter than a generic \d{11} so generic ID-like numbers don't
# get eaten (order refs, appointment numbers).
TC_RE = re.compile(r"\b[1-9]\d{10}\b")

# TR phone numbers — tolerates international prefix, domestic leading
# zero, and common separators (space / dash / paren). Not exhaustive
# but matches the shapes patients actually type.
PHONE_RE = re.compile(
    r"(?:\+?90[\s\-]?)?"                          # optional +90 / 90
    r"(?:\(?0?5\d{2}\)?|\b0\d{3}\b)"              # 5xx mobile or 0xxx landline block
    r"[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"     # 3-2-2 tail
)

# Email — ASCII + common punctuation in local part; case-insensitive.
EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)


def redact_pii(text: str) -> str:
    """Remove TC IDs, phone numbers, and email addresses from text.

    Idempotent (running twice does not double-replace). Returns an
    empty string for None/empty input instead of raising.
    """
    t = text or ""
    t = EMAIL_RE.sub("[REDACTED_EMAIL]", t)
    t = PHONE_RE.sub("[REDACTED_PHONE]", t)
    t = TC_RE.sub("[REDACTED_ID]", t)
    return t
