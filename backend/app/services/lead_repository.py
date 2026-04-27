"""Lead persistence layer for /v1/quote/lead.

Why a separate module from lead_dispatcher
    The dispatcher does transport (webhook out). The repository does
    durability (DB row before / after). Splitting them means a Supabase
    outage doesn't stop webhooks from firing, and a CRM outage doesn't
    stop the row from being written. Each layer's failure-mode is
    isolated.

Lifecycle covered
    insert()          → write a 'pending' row before the webhook attempt
    record_outcome()  → flip status + delivered_at after the webhook returns
    soft_delete()     → KVKK silme: null out contact + notes, keep row
                        (5-yr retention per Sağlık Turizmi Yönetmeliği)
    get()             → read a single lead (used by DELETE handler to
                        verify ownership before deleting)

Failure-mode contract
    Every public function is fail-soft: a Supabase outage logs WARN
    and returns the equivalent of "no DB" (None / False / no-op).
    The route handler can still respond 200 to the patient — the
    webhook may have delivered even if persistence failed; that
    discrepancy surfaces in monitoring, not in user-facing 5xx.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


_TABLE_NAME = "health_tourism_leads"


def _supabase_configured() -> bool:
    return bool(
        os.environ.get("SUPABASE_URL")
        and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── insert ──────────────────────────────────────────────────────────


def insert(
    *,
    lead_id: str,
    session_id: str,
    quote_id: Optional[str],
    procedure_id: str,
    clinic_id: str,
    consent_to_share: bool,
    contact: dict[str, Any],
    notes: str,
    locale: str,
    quoted_price_eur: Optional[int],
) -> bool:
    """Write a fresh lead row with webhook_status='pending'. Returns
    True on success, False on Supabase outage / unconfigured.

    Caller pattern:
        repo.insert(...)           # before dispatch
        outcome = await dispatcher.dispatch(...)
        repo.record_outcome(lead_id, outcome)

    Even if insert returns False, the dispatcher proceeds — the lead
    is captured by webhook delivery alone, just without our durable
    record. Operators see the gap in metrics.
    """
    if not _supabase_configured():
        return False

    row = {
        "id": lead_id,
        "session_id": session_id,
        "quote_id": quote_id,
        "procedure_id": procedure_id,
        "clinic_id": clinic_id,
        "consent_to_share": bool(consent_to_share),
        # Without consent we MUST NOT store contact PII even
        # transiently — the table column allows NULL for this case.
        "contact": contact if consent_to_share else None,
        "notes": notes or "",
        "locale": locale,
        "quoted_price_eur": quoted_price_eur,
        "webhook_status": "pending",
    }
    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        sb.table(_TABLE_NAME).insert(row).execute()
        return True
    except Exception as exc:
        logger.warning(
            "lead_repository.insert_failed lead_id=%s: %s", lead_id, exc
        )
        return False


# ─── record_outcome ──────────────────────────────────────────────────


_VALID_OUTCOMES = frozenset(
    {"delivered", "failed_4xx", "failed_exhausted", "not_configured", "errored"}
)


def record_outcome(
    lead_id: str,
    outcome: str,
    *,
    response_snippet: Optional[str] = None,
) -> bool:
    """Update the lead row after the webhook attempt.

    ``outcome`` must be one of the values in the SQL CHECK constraint;
    we validate locally so a typo fails fast instead of round-tripping
    to Postgres for a constraint error.
    """
    if not _supabase_configured():
        return False
    if outcome not in _VALID_OUTCOMES:
        logger.error(
            "lead_repository.record_outcome rejected invalid outcome=%r",
            outcome,
        )
        return False

    update = {
        "webhook_status": outcome,
        "webhook_attempted_at": _now_iso(),
    }
    if outcome == "delivered":
        update["webhook_delivered_at"] = _now_iso()
    if response_snippet:
        update["webhook_response_snippet"] = response_snippet[:200]

    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        sb.table(_TABLE_NAME).update(update).eq("id", lead_id).execute()
        return True
    except Exception as exc:
        logger.warning(
            "lead_repository.record_outcome_failed lead_id=%s: %s",
            lead_id, exc,
        )
        return False


# ─── soft_delete (KVKK silme hakkı) ──────────────────────────────────


def soft_delete(lead_id: str) -> bool:
    """Erase contact + notes, mark is_deleted=true. Row is kept for
    the 5-year retention window per the regulation. Returns False if
    the lead does not exist or Supabase is unreachable."""
    if not _supabase_configured():
        return False

    update = {
        "is_deleted": True,
        "deleted_at": _now_iso(),
        "contact": None,
        "notes": "",
    }
    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        result = (
            sb.table(_TABLE_NAME)
            .update(update)
            .eq("id", lead_id)
            .execute()
        )
        # Supabase returns the updated rows in result.data; an empty
        # list means "id matched zero rows" — i.e. the lead doesn't
        # exist. Treat as not-deleted so the route can respond 404.
        rows = getattr(result, "data", None) or []
        return len(rows) > 0
    except Exception as exc:
        logger.warning(
            "lead_repository.soft_delete_failed lead_id=%s: %s",
            lead_id, exc,
        )
        return False


# ─── get ─────────────────────────────────────────────────────────────


def get(lead_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single lead row. None on not-found or Supabase outage."""
    if not _supabase_configured():
        return None
    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        result = (
            sb.table(_TABLE_NAME)
            .select("*")
            .eq("id", lead_id)
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.info(
            "lead_repository.get_failed lead_id=%s: %s", lead_id, exc
        )
        return None
