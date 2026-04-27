"""Forensic audit log writer — append-only WORM.

Compliance lineage: docs/DPIA_2026.md:R-10. Schema in
backend/sql/20260427_audit_log.sql.

This module is the only sanctioned writer to `public.audit_log`. The
table has triggers that block UPDATE / DELETE, so a misbehaving
caller can't damage the trail; but they can still over-share PII in
the payload field. The PII guard below makes that explicit and
documented.

Usage:

    from app.audit import record_event

    record_event(
        event_type="data_rights.session_tombstoned",
        actor_type="user",
        actor_id=device_id,
        target_id=session_id,
        severity="info",
        payload={"derived_deleted": {"events": 5, "feedback": 1}},
        ip_hash=hash_ip(client_ip),
    )

Failure semantics: best-effort. If supabase fails, the function
LOGS a warning and returns — it does NOT raise. Audit is
defense-in-depth, not an availability gate. The pattern matches
admin_tenants_api._write_audit_row, which handles the same trade-
off (commit 90c7411-era convention).

Why we never raise:
    A failed audit insert during a successful business operation
    (e.g. a successful session deletion) would otherwise force the
    caller to either (a) roll back the business operation —
    catastrophic for a user-facing erasure that already partially
    completed, or (b) propagate a 500 — the user sees an error for
    work that actually succeeded. Both are worse than a missed
    audit row, which is recoverable forensically through the other
    surfaces (consent_records, triage_events, Sentry breadcrumbs).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

logger = logging.getLogger(__name__)

ActorType = Literal["user", "admin", "system", "cron"]
Severity = Literal["info", "warning", "critical"]

# Defensive PII denylist for payload keys. The schema docstring says
# "no free text", but a future maintainer wiring up a new event type
# might forget. This list catches obvious mistakes and logs a
# warning before scrubbing the offending key. Add new known-PII
# names here as they surface in incident review.
_PII_KEY_DENYLIST = frozenset(
    {
        "input_text",
        "user_message",
        "answers",
        "email",
        "comment",
        "doctor_ready_summary_tr",
        "free_text",
        "raw_text",
        "name",
        "full_name",
    }
)


def _scrub_payload(
    payload: Optional[Dict[str, Any]], event_type: str
) -> Dict[str, Any]:
    """Remove keys that look like PII from the audit payload.

    Logs a warning per scrubbed key so the leak path is visible in
    Sentry — a future PR adding a new event type that accidentally
    passes user_message will get caught in code review or in logs
    on the very first run.
    """
    if not payload:
        return {}
    scrubbed: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in _PII_KEY_DENYLIST:
            logger.warning(
                "audit.payload_pii_scrubbed",
                extra={
                    "event_type": event_type,
                    "scrubbed_key": key,
                },
            )
            continue
        scrubbed[key] = value
    return scrubbed


def record_event(
    event_type: str,
    actor_type: ActorType,
    *,
    actor_id: Optional[str] = None,
    target_id: Optional[str] = None,
    severity: Severity = "info",
    payload: Optional[Dict[str, Any]] = None,
    ip_hash: Optional[str] = None,
) -> None:
    """Insert one audit row. Never raises.

    Args:
        event_type: Dotted namespace string (e.g.
            "data_rights.session_tombstoned"). Schema doesn't constrain
            the value; convention is enforced by code review.
        actor_type: Who acted. "user" for end-user actions,
            "admin" for admin API, "system" for backend-internal,
            "cron" for scheduled jobs.
        actor_id: Anonymised UUID (device_id, admin user_id). Never
            raw PII.
        target_id: Resource the event applied to (session_id,
            tenant_id, etc). Never raw PII.
        severity: "info" (default) | "warning" | "critical".
        payload: JSONB metadata. PII keys are scrubbed and logged.
        ip_hash: SHA-256 + salt hash from `app.db.hash_ip`.
    """
    safe_payload = _scrub_payload(payload, event_type)

    row = {
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "target_id": target_id,
        "severity": severity,
        "payload": safe_payload,
        "ip_hash": ip_hash,
    }

    try:
        # Lazy import — keeps app.db side effects (Supabase client
        # init at module load time) out of test environments that
        # don't need DB.
        from app.db import supabase

        supabase.table("audit_log").insert(row).execute()
    except Exception as exc:
        # Best-effort: log and swallow. The breadcrumb is enough
        # forensic surface to reconstruct a missing audit row from
        # cross-referencing Sentry + triage_events.
        logger.warning(
            "audit.persist_failed",
            extra={
                "event_type": event_type,
                "actor_type": actor_type,
                "severity": severity,
                "error": str(exc),
            },
        )
