#!/usr/bin/env python3
"""Local PII scanner for Sentry event JSON.

Pipe a Sentry event (the full JSON blob from
"View as JSON" in the Sentry UI, or from the REST API) into this
script on stdin. It walks every string value in the event and flags
matches against five patterns we expect `beforeSend` to have
scrubbed. Exit code 0 = clean; 1 = flagged (treat as P1 privacy
bug — see docs/SENTRY_REPLAY_POLICY.md §6).

Why this is a quarterly-audit tool and NOT a CI gate:
    The scanner runs on REAL production event data, which means it
    requires production Sentry access + manual sampling. Wiring it
    into CI would need a service-account Sentry token + rate-limit
    handling + a decision about what to do when the audit fails
    during a blameless release cycle. For now, on-call runs it by
    hand every quarter (see MOBILE_SENTRY_OUTAGE.md §"Quarterly PII
    audit"), and the results are filed as zero-finding "incidents"
    in docs/incidents/.

What each pattern catches:

  TCKN (11-digit TR ID, first digit 1-9)
    Any match is load-bearing. TCKN leakage is the #1 privacy
    violation risk on a Turkish medical app — flag + investigate
    immediately.

  Phone (international + TR local shapes)
    Phone numbers in free-text patient descriptions. The
    `beforeSend` scrubber's `redactPII` should have caught these
    before transport.

  Email
    Same logic as phone — mid-text email leak implies an unscrubbed
    user description path.

  UUID (8-4-4-4-12 hex)
    Session UUIDs should collapse to `/v1/session/[id]/...` via
    `redactUrlPath`. A raw UUID in any field means the scrubber
    missed a code path (likely a new breadcrumb category, or a
    route that doesn't go through the shared api client).

  Turkish medical free-text markers ("ağrı", "nefes", "hasta",
    "ateş", "kanama")
    Weaker signal — these are common words. But combined with any
    of the above, they localize WHERE patient text is leaking
    (exception message? breadcrumb? extra context?). The scanner
    reports which top-level JSON key contained the match so the
    fix can target the right source.

Output:
    Prints one section per pattern that matched, with the
    containing JSON path + a redacted preview of the surrounding
    text. Never prints the raw TCKN/phone/email/UUID — preview is
    patched through the same redaction used by the production
    scrubber, so running this against a real production event
    doesn't create another copy of the PII in your terminal history.

Usage:
    # Paste event JSON:
    python scripts/sentry_event_pii_scan.py < event.json

    # Or pipe from Sentry API:
    curl -s -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \\
      "https://sentry.io/api/0/.../events/<id>/" \\
      | python scripts/sentry_event_pii_scan.py

Exit codes:
    0  — clean (no patterns flagged)
    1  — one or more patterns flagged
    2  — input is not valid JSON
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

# ── Patterns ──────────────────────────────────────────────────────
#
# Intentionally kept inline here rather than imported from a
# shared module because this script is meant to be audit-ready:
# a privacy reviewer should be able to read this file end-to-end
# and verify the scan logic without following cross-file imports.

# Turkish national ID — 11 digits, first digit 1-9.
TCKN_RE = re.compile(r"\b[1-9][0-9]{10}\b")

# Phone numbers — international + TR local shapes. Permissive
# because the goal is "flag suspicious digit runs" not "extract a
# perfect phone record". Requires >=10 consecutive digits allowing
# spaces/parens/dashes/dots.
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")

# Email — common shapes; same pattern as the `beforeSend` scrubber.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# UUID — 8-4-4-4-12 hex. Matches session UUIDs if they slipped
# through `redactUrlPath`.
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

# Turkish medical free-text markers. Not a sufficient signal on
# their own — too common — but combined with another pattern
# localize the leak.
TR_MEDICAL_RE = re.compile(
    r"\b(ağrı|ağrım|nefes|nefesim|hasta|ateş|kanama|ishal|"
    r"kusma|bulantı|baş dönmesi|migren|panik|depresyon|"
    r"tansiyon|çarpıntı|titriyor|üşüyorum|belirtisi|şikayet)\b",
    re.IGNORECASE | re.UNICODE,
)

PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("TCKN", TCKN_RE),
    ("PHONE", PHONE_RE),
    ("EMAIL", EMAIL_RE),
    ("UUID", UUID_RE),
    ("TR_MEDICAL", TR_MEDICAL_RE),
)


@dataclass
class Finding:
    pattern: str
    json_path: str
    preview: str


@dataclass
class ScanResult:
    findings: List[Finding] = field(default_factory=list)
    strings_scanned: int = 0


def _redact(text: str) -> str:
    """Redact the same patterns we're flagging, so the preview
    we print doesn't itself carry raw PII. Order mirrors
    mobile/src/observability/redact.ts: narrowest first.
    """
    out = text
    out = UUID_RE.sub("[UUID]", out)
    out = EMAIL_RE.sub("[EMAIL]", out)
    out = TCKN_RE.sub("[TCKN]", out)
    out = PHONE_RE.sub("[PHONE]", out)
    # TR_MEDICAL we leave visible in the preview — it's the
    # "context" signal, not PII in itself, and seeing which
    # medical word appeared helps the reviewer localize the leak.
    return out


def _preview(text: str, match_start: int, match_end: int, window: int = 40) -> str:
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    clipped = text[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    # Collapse whitespace for one-line output.
    compact = re.sub(r"\s+", " ", clipped).strip()
    return f"{prefix}{_redact(compact)}{suffix}"


def _walk(node: Any, path: str, result: ScanResult) -> None:
    if isinstance(node, str):
        result.strings_scanned += 1
        for label, rx in PATTERNS:
            for m in rx.finditer(node):
                result.findings.append(
                    Finding(
                        pattern=label,
                        json_path=path or "<root>",
                        preview=_preview(node, m.start(), m.end()),
                    )
                )
        return
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", result)
        return
    if isinstance(node, dict):
        for key, value in node.items():
            next_path = f"{path}.{key}" if path else key
            _walk(value, next_path, result)
        return
    # ints, floats, bools, None — nothing to match.


def _format_report(result: ScanResult) -> str:
    if not result.findings:
        return (
            f"PII scan: CLEAN — scanned {result.strings_scanned} strings, "
            f"no patterns flagged.\n"
        )
    lines: List[str] = [
        f"PII scan: FAIL — {len(result.findings)} finding(s) across "
        f"{result.strings_scanned} strings scanned.",
        "",
    ]
    by_pattern: Dict[str, List[Finding]] = {}
    for f in result.findings:
        by_pattern.setdefault(f.pattern, []).append(f)
    for label, _rx in PATTERNS:
        group = by_pattern.get(label, [])
        if not group:
            continue
        lines.append(f"== {label} ({len(group)}) ==")
        # Cap output — full list can be noisy for a popular
        # pattern like TR_MEDICAL. First 10 is enough to localize.
        for f in group[:10]:
            lines.append(f"  {f.json_path}")
            lines.append(f"    {f.preview}")
        if len(group) > 10:
            lines.append(f"  ...and {len(group) - 10} more {label} match(es)")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: List[str]) -> int:
    # Force UTF-8 stdout so Turkish chars + Δ / … render on all
    # platforms, including Windows CP1254 default.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass

    raw = sys.stdin.read()
    if not raw.strip():
        sys.stderr.write("ERROR: stdin is empty; pipe Sentry event JSON in.\n")
        return 2
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"ERROR: stdin is not valid JSON: {exc}\n")
        return 2

    result = ScanResult()
    _walk(event, "", result)
    sys.stdout.write(_format_report(result))
    return 1 if result.findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
