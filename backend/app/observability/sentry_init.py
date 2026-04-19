"""Sentry initialization + PII scrubbing.

Called once from app/main.py at import time. A blank SENTRY_DSN makes
init() a no-op — the app runs unchanged without an external dep.

Why a separate module instead of inlining in main.py:
  - Test isolation: we can stub `init_sentry` without touching the
    import tree of app.main.
  - The before_send hook is non-trivial (PII scrub + breadcrumb
    filtering) and deserves its own unit tests.
  - If we ever swap Sentry for another aggregator (Datadog, Rollbar),
    the swap is one import-line change in main.

PII scrubbing reuses the same redact_pii() the Wiro client uses
before it transmits text to the LLM. Keeping a single canonical
implementation means a new PII pattern (new ID format, new phone
format) added for one path automatically protects the other.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import settings
from app.pii import redact_pii

logger = logging.getLogger(__name__)

# Request fields that should never leave the server. Sentry captures
# request.data + request.headers by default; we strip anything known
# to carry patient input or auth material.
_SCRUB_HEADERS = frozenset({
    "authorization", "cookie", "x-admin-key", "x-supabase-auth",
    "x-device-id",  # device IDs are not PII but they let us
                    # fingerprint a user across sessions, which is
                    # technically a privacy regression in aggregated
                    # error reports.
})

_SCRUB_BODY_KEYS = frozenset({
    "input_text", "user_message", "answers",
    "doctor_ready_summary_tr", "why_specialty_tr",
    "emergency_reason_tr", "meta",
})


def _scrub_mapping(obj: Any) -> Any:
    """Recursively redact PII from dict/list structures."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SCRUB_BODY_KEYS:
                out[k] = "[SCRUBBED]"
            else:
                out[k] = _scrub_mapping(v)
        return out
    if isinstance(obj, list):
        return [_scrub_mapping(x) for x in obj]
    if isinstance(obj, str):
        return redact_pii(obj)
    return obj


def before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Sentry before_send hook — runs synchronously on every event.

    Responsibilities:
      1. Drop events fired from tests / CI (SENTRY_ENVIRONMENT=test).
         Otherwise dev-env errors flood the prod project.
      2. Strip auth headers + device IDs from request context.
      3. Redact free-text PII via app.pii.redact_pii on request body
         and any string in event extras/breadcrumbs.

    Returning None drops the event entirely. Raising doesn't escape
    the SDK — Sentry wraps before_send in a try/except.
    """
    if settings.SENTRY_ENVIRONMENT in ("test", "ci"):
        return None

    # Scrub request context.
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        request["headers"] = {
            k: ("[SCRUBBED]" if k.lower() in _SCRUB_HEADERS else v)
            for k, v in headers.items()
        }
    # Request data is often a JSON body — recurse through it.
    if "data" in request:
        request["data"] = _scrub_mapping(request["data"])

    # Scrub extras + breadcrumbs.
    if "extra" in event:
        event["extra"] = _scrub_mapping(event["extra"])
    if "breadcrumbs" in event:
        crumbs = event["breadcrumbs"]
        values = crumbs.get("values") if isinstance(crumbs, dict) else None
        if isinstance(values, list):
            for c in values:
                if isinstance(c, dict):
                    if "message" in c and isinstance(c["message"], str):
                        c["message"] = redact_pii(c["message"])
                    if "data" in c:
                        c["data"] = _scrub_mapping(c["data"])

    return event


def init_sentry() -> bool:
    """Initialise Sentry if SENTRY_DSN is set.

    Returns True when the SDK was actually initialised, False when
    the DSN is blank or the sentry_sdk import failed. Logged either
    way so ops can confirm the state from startup logs.
    """
    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        logger.info("Sentry disabled: SENTRY_DSN is blank")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError as exc:
        logger.warning(
            "Sentry DSN is set but sentry-sdk is not installed (%s). "
            "Add `sentry-sdk[fastapi]>=2.0` to requirements.txt.", exc,
        )
        return False

    init_kwargs: Dict[str, Any] = {
        "dsn": dsn,
        "environment": settings.SENTRY_ENVIRONMENT,
        "traces_sample_rate": float(settings.SENTRY_TRACES_SAMPLE_RATE),
        "integrations": [
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        "before_send": before_send,
        # Drop IP from every event — GDPR + KVKK hygiene. Sentry
        # aggregation doesn't need IPs to cluster; clustering by
        # exception type + request path is enough.
        "send_default_pii": False,
    }
    if settings.SENTRY_RELEASE:
        init_kwargs["release"] = settings.SENTRY_RELEASE

    sentry_sdk.init(**init_kwargs)
    logger.info(
        "Sentry initialised: environment=%s traces_sample_rate=%.2f",
        settings.SENTRY_ENVIRONMENT, init_kwargs["traces_sample_rate"],
    )
    return True
