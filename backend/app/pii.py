"""PII redaction helper — strips emails, phone numbers, and TC IDs from text.

Used before storing input_text in the database to minimize personal data exposure.
"""

import re

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(
    r"\b(?:\+?90)?\s*(?:\(?\d{3}\)?\s*)\d{3}\s*\d{2}\s*\d{2}\b"
)
TC_RE = re.compile(r"\b\d{11}\b")


def redact_pii(text: str) -> str:
    """Remove email addresses, phone numbers, and 11-digit TC IDs from text."""
    t = text or ""
    t = EMAIL_RE.sub("[REDACTED_EMAIL]", t)
    t = PHONE_RE.sub("[REDACTED_PHONE]", t)
    t = TC_RE.sub("[REDACTED_ID]", t)
    return t
