"""Per-clause consent audit endpoint — POST /v1/consent/event.

Records a single user-driven consent acknowledgment (or revocation)
to the `consent_events` table. The mobile onboarding screen calls
this on every checkbox toggle for the three required clauses
(terms / KVKK / age) so a KVKK Art. 6 audit can reconstruct the
sequence of intent leading up to "Başla."

Why a fire-and-forget POST per toggle (rather than batching at
"Başla" time):
  - A user who ticks KVKK, then unticks it 5 minutes later, then
    re-ticks before pressing Başla has a meaningful audit trail —
    they considered it. Batching loses that signal.
  - "Başla" can be pressed offline; per-toggle posts let us retain
    the events client-side and replay when connectivity returns
    (mobile follow-up — out of scope for this commit).
  - One row per event keeps the schema flat. Latest-state queries
    walk the (device_id, clause_id, created_at desc) index.

PII / privacy:
  - device_id is anonymous (random UUID, no cross-device join).
  - user_agent + ip_hash columns exist but the route does NOT
    populate them by default. Privacy team flips a feature flag
    when they want them on; this keeps the default behaviour
    minimum-necessary.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


ClauseId = Literal["terms", "kvkk", "age"]


class ConsentEventIn(BaseModel):
    clause_id: ClauseId = Field(
        ...,
        description=(
            "Which consent slot the user toggled. One of: "
            "'terms' (Kullanım koşulları), 'kvkk' (Anonim sağlık verileri "
            "açık rıza), 'age' (13+ yaş beyanı). Constrained server-side "
            "via the consent_events.clause_id CHECK constraint."
        ),
    )
    accepted: bool = Field(
        ...,
        description=(
            "True when the user ticked the box, false when they unticked "
            "it. Both values are recorded — auditing the sequence (not "
            "just the latest state) is the whole point of this log."
        ),
    )
    notice_version: str = Field(
        ...,
        max_length=64,
        description=(
            "Snapshot of EXPO_PUBLIC_NOTICE_VERSION at the time of the "
            "toggle. If we change the privacy notice, we want to know "
            "which copy the user actually saw."
        ),
    )
    consent_version: str = Field(
        ...,
        max_length=32,
        description=(
            "Snapshot of EXPO_PUBLIC_CONSENT_VERSION. Bumping this "
            "invalidates stored consents on the client side; the audit "
            "trail keeps the prior version so we can prove the user did "
            "consent under the previous text."
        ),
    )


class ConsentEventOut(BaseModel):
    ok: bool = True
    # The bigserial id is informational — clients don't need to track
    # individual events, but having it in the response makes it trivial
    # to grep for a specific row in logs / tickets.
    id: Optional[int] = None


@router.post("/consent/event", response_model=ConsentEventOut, status_code=201)
def record_consent_event(
    payload: ConsentEventIn,
    x_device_id: Optional[str] = Header(default=None, alias="X-Device-Id"),
) -> ConsentEventOut:
    """Persist a single consent toggle.

    The mobile client posts this once per checkbox tap. The route is
    write-only and per-device; there's no read endpoint here — KVKK
    auditors query Supabase directly with the appropriate role.

    Failure modes:
      - 400 missing X-Device-Id header (anonymous tracking key).
      - 422 invalid clause_id (handled by Pydantic + the CHECK
        constraint as a belt-and-braces).
      - 503 when Supabase is unavailable. We deliberately fail loud
        rather than queue locally; the mobile client should retry
        with backoff. Losing audit events silently is worse than
        dropping the user back to a clean form.
    """
    if not x_device_id:
        # We don't fall back to "anonymous" because we can't audit a
        # consent event without a stable subject — even an anonymous
        # device id is what the KVKK process pairs the row with.
        raise HTTPException(
            status_code=400,
            detail={
                "code": "missing_device_id",
                "message_tr": (
                    "Onay olayı kaydedilemedi: cihaz kimliği eksik."
                ),
            },
        )

    # Lazy-import to keep test imports cheap and let the route module
    # load even when Supabase env vars aren't set in some CI lanes.
    from app.supabase_client import get_supabase

    try:
        sb = get_supabase()
        resp = (
            sb.table("consent_events")
            .insert(
                {
                    "device_id": x_device_id,
                    "clause_id": payload.clause_id,
                    "accepted": payload.accepted,
                    "notice_version": payload.notice_version,
                    "consent_version": payload.consent_version,
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "consent.event_insert_failed device=%s clause=%s accepted=%s: %s",
            x_device_id,
            payload.clause_id,
            payload.accepted,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "audit_log_unavailable",
                "message_tr": (
                    "Onay kaydı şu an alınamadı. Lütfen birazdan tekrar "
                    "deneyin."
                ),
            },
        )

    inserted_id: Optional[int] = None
    rows = getattr(resp, "data", None)
    if isinstance(rows, list) and rows:
        first = rows[0]
        if isinstance(first, dict):
            raw = first.get("id")
            if isinstance(raw, int):
                inserted_id = raw

    logger.info(
        "consent.event_recorded device=%s clause=%s accepted=%s id=%s",
        x_device_id,
        payload.clause_id,
        payload.accepted,
        inserted_id,
    )
    return ConsentEventOut(ok=True, id=inserted_id)
