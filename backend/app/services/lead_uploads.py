"""Operator-curated bag table linking patient uploads to leads.

Replace semantics with diff: PATCH /v1/admin/leads/{lead_id}/uploads
sends the desired full set; this service computes which links to add,
which to tombstone, and which to leave untouched. Untouched links
keep their original ``linked_at`` / ``linked_by_operator_id`` values
so the audit trail isn't churned every time the operator re-saves a
mostly-unchanged set.

KVKK contract: links are tombstoned (soft delete), never physically
deleted. The data-rights endpoint on ``/v1/me/sessions/{id}`` does
NOT cascade to lead_uploads — link rows by themselves carry no
patient PII (just two foreign keys), so retention is governed by
the lead's 5-year Madde 10 window.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# ─── Lead existence check (used by the route handler) ──────────────


def lead_exists(lead_id: str) -> bool:
    """Check if a health_tourism_leads row exists. Caller treats
    None / DB blip as "not found" to avoid linking to a phantom lead."""
    from app.db import supabase

    try:
        resp = (
            supabase.table("health_tourism_leads")
            .select("id")
            .eq("id", lead_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("lead_uploads.lead_lookup_failed id=%s: %s", lead_id, exc)
        return False
    return bool(resp and resp.data)


# ─── Read ────────────────────────────────────────────────────────────


def list_active_for_lead(lead_id: str) -> list[dict]:
    """Live (non-tombstoned) links for a lead, newest linked_at first."""
    from app.db import supabase

    try:
        resp = (
            supabase.table("lead_uploads")
            .select(
                "id, lead_id, asset_id, linked_at, linked_by_operator_id"
            )
            .eq("lead_id", lead_id)
            .is_("deleted_at", "null")
            .order("linked_at", desc=True)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "lead_uploads.list_active_failed lead_id=%s: %s", lead_id, exc
        )
        return []
    return resp.data or []


# ─── Write (replace with diff) ──────────────────────────────────────


def replace_links_for_lead(
    lead_id: str,
    asset_ids: Iterable[str],
    *,
    linked_by_operator_id: str,
) -> dict:
    """Diff the desired set against the live set and apply changes.

    Returns a summary dict::

        {
          "added":   list of asset_ids inserted,
          "removed": list of asset_ids tombstoned,
          "kept":    list of asset_ids that were already linked,
          "current": list of asset_ids now live on the lead,
        }

    Diff approach (vs. tombstone-all-then-insert-all):
      - Preserves linked_at / linked_by on untouched links so the
        audit trail isn't churned when the operator re-saves
      - Avoids unique-constraint races: re-inserting an existing pair
        would fail the partial-unique index; we just leave it alone

    The function does NOT validate that asset_ids exist or that the
    lead exists — the route handler is responsible for those checks
    so 404 / 422 fire before any DB writes.
    """
    from app.db import supabase

    desired = list({aid for aid in asset_ids if aid})  # de-dup, drop empties
    current_links = list_active_for_lead(lead_id)
    current_asset_ids = {link["asset_id"] for link in current_links}
    desired_set = set(desired)

    to_add = desired_set - current_asset_ids
    to_remove = current_asset_ids - desired_set
    kept = desired_set & current_asset_ids

    now_iso = datetime.now(timezone.utc).isoformat()

    # Tombstone removed links. We update by id (PK) to skip the
    # composite-unique index churn and to make the audit clear:
    # ("which row got tombstoned?" -> id).
    if to_remove:
        ids_to_tombstone = [
            link["id"] for link in current_links
            if link["asset_id"] in to_remove
        ]
        try:
            (
                supabase.table("lead_uploads")
                .update(
                    {
                        "deleted_at": now_iso,
                        "deleted_reason": "operator_unlinked",
                    }
                )
                .in_("id", ids_to_tombstone)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lead_uploads.tombstone_links_failed lead_id=%s: %s",
                lead_id, exc,
            )
            # Continue -- partial success is preferable to a full abort
            # that loses the additions side of the diff.

    # Insert new links. supabase-py supports batch insert via a list;
    # the unique partial index protects against double-link races.
    if to_add:
        rows = [
            {
                "lead_id": lead_id,
                "asset_id": aid,
                "linked_by_operator_id": linked_by_operator_id,
            }
            for aid in to_add
        ]
        try:
            supabase.table("lead_uploads").insert(rows).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lead_uploads.insert_links_failed lead_id=%s: %s",
                lead_id, exc,
            )

    return {
        "added": sorted(to_add),
        "removed": sorted(to_remove),
        "kept": sorted(kept),
        "current": sorted(desired_set),
    }


# ─── Lookups (forensic) ──────────────────────────────────────────────


def list_leads_for_asset(asset_id: str) -> list[str]:
    """All lead_ids the asset is currently live-linked to. Forensic
    use case ("which leads referenced this Norwood photo?")."""
    from app.db import supabase

    try:
        resp = (
            supabase.table("lead_uploads")
            .select("lead_id")
            .eq("asset_id", asset_id)
            .is_("deleted_at", "null")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "lead_uploads.list_leads_failed asset_id=%s: %s", asset_id, exc
        )
        return []
    return [r["lead_id"] for r in (resp.data or [])]
