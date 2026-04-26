"""Patient upload metadata service.

Bytes are deliberately NOT stored — see ``sql/20260427_patient_uploads.sql``
for the rationale (KVKK posture, ops simplicity, no Storage bucket to
misconfigure). This module owns:

  - Validation (MIME whitelist + per-kind size cap + consent enforce)
  - sha256 fingerprinting (dedup audit trail; 32-byte hash, no payload)
  - Insert / status-update / lookup against the ``patient_uploads`` table
  - Tombstone helper invoked by ``data_rights`` when a session is
    deleted; mirrors the triage_sessions tombstone shape.

Functions are kept narrowly single-purpose so the route handler and
the BG dispatcher can mix them without behaviour leaking between
layers — e.g. ``record_upload`` doesn't fire the AI task; the route
schedules a BackgroundTask that calls the dispatcher, which calls
``mark_processing`` / ``mark_succeeded`` / ``mark_failed`` here.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── MIME whitelist + size caps ──────────────────────────────────────


# Per-kind whitelist. The route 415s any content-type not in the set
# corresponding to its declared upload_kind; this prevents a patient
# from claiming "image" on a 100MB MP4 to bypass the video size cap,
# and prevents random binary blobs from reaching the dispatcher.
ALLOWED_MIME_BY_KIND: dict[str, frozenset[str]] = {
    "image": frozenset({"image/jpeg", "image/png", "image/webp"}),
    "audio": frozenset({"audio/wav", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/m4a"}),
    "video": frozenset({"video/mp4", "video/webm"}),
    # Documents: PDF + image scans (lab results photographed by phone).
    # JPEG/PNG with kind=document routes to dots_ocr instead of moondream.
    "document": frozenset({"application/pdf", "image/jpeg", "image/png"}),
}

VALID_KINDS = frozenset(ALLOWED_MIME_BY_KIND.keys())


def size_cap_for_kind(kind: str) -> int:
    """Return the byte cap for ``kind``. Raises KeyError on unknown
    kinds — the caller validates ``kind`` first."""
    return {
        "image": settings.PATIENT_UPLOAD_MAX_IMAGE_BYTES,
        "audio": settings.PATIENT_UPLOAD_MAX_AUDIO_BYTES,
        "video": settings.PATIENT_UPLOAD_MAX_VIDEO_BYTES,
        "document": settings.PATIENT_UPLOAD_MAX_DOCUMENT_BYTES,
    }[kind]


class UploadValidationError(Exception):
    """Raised by ``validate_upload`` with a structured detail dict that
    the route handler converts to a 4xx response. The exception carries
    a ``status_code`` attribute so the handler doesn't need a switch.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def validate_upload(
    *,
    kind: str,
    content_type: str,
    size_bytes: int,
    consent_to_process: bool,
) -> None:
    """Raise UploadValidationError if any boundary condition fails.

    Order matters: cheapest checks first so a 422 returns before we
    inspect 100MB of multipart bytes.
    """
    if not consent_to_process:
        raise UploadValidationError(
            422,
            (
                "consent_to_process must be true. KVKK requires explicit "
                "patient opt-in before AI processing."
            ),
        )
    if kind not in VALID_KINDS:
        raise UploadValidationError(
            422,
            f"unknown upload_kind={kind!r}; valid: {sorted(VALID_KINDS)}",
        )
    allowed = ALLOWED_MIME_BY_KIND[kind]
    if content_type not in allowed:
        raise UploadValidationError(
            415,
            (
                f"content_type={content_type!r} not allowed for kind={kind!r}. "
                f"Allowed: {sorted(allowed)}"
            ),
        )
    cap = size_cap_for_kind(kind)
    if size_bytes <= 0:
        raise UploadValidationError(422, "empty file rejected")
    if size_bytes > cap:
        raise UploadValidationError(
            413,
            f"file size {size_bytes}B exceeds cap {cap}B for kind={kind!r}",
        )


# ─── Hashing ─────────────────────────────────────────────────────────


def compute_sha256(content: bytes) -> str:
    """Hex-encoded SHA-256 of the upload bytes. Stored on the row for
    forensic audit ("did this exact blob arrive before?") and dedup —
    NOT used for security (no HMAC, no salt; bytes themselves never
    leave RAM)."""
    return hashlib.sha256(content).hexdigest()


# ─── Database access ─────────────────────────────────────────────────
#
# Lazy supabase import in each call — same pattern as data_rights /
# admin_*. Avoids forcing every test that imports this module to
# also wire an env stub for SUPABASE_*.


def record_upload(
    *,
    session_id: Optional[str],
    sha256_hex: str,
    content_type: str,
    size_bytes: int,
    upload_kind: str,
    consent_to_process: bool,
    consent_text: Optional[str] = None,
    retention_days: Optional[int] = None,
) -> str:
    """Insert a new ``patient_uploads`` row and return the asset_id.

    ``session_id`` is optional but strongly recommended — the data
    rights endpoint can only tombstone uploads that carry a session
    reference. The schema's ON DELETE SET NULL means an unreferenced
    upload won't get cleaned automatically when the session goes
    away; the retention sweep will handle it eventually.
    """
    from app.db import supabase

    days = retention_days if retention_days is not None else int(
        getattr(settings, "PATIENT_UPLOAD_RETENTION_DAYS", 30)
    )
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    row = {
        "session_id": session_id,
        "sha256_hex": sha256_hex,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "upload_kind": upload_kind,
        "consent_to_process": consent_to_process,
        "consent_text": consent_text,
        "expires_at": expires_at.isoformat(),
        "ai_status": "pending",
    }
    resp = supabase.table("patient_uploads").insert(row).execute()
    if not resp.data:
        # Insert with empty data is a Supabase-side oddity; surface as
        # a server error instead of returning a phantom asset_id.
        raise RuntimeError("patient_uploads insert returned no row")
    return resp.data[0]["asset_id"]


def mark_processing(asset_id: str, ai_provider: str) -> None:
    """Set ai_status='processing' + record which provider is working
    the row. Best-effort: log + swallow on DB error so the BG task
    keeps going to actually call the AI service."""
    _update_status(
        asset_id,
        {"ai_status": "processing", "ai_provider": ai_provider},
    )


def mark_succeeded(
    asset_id: str, *, ai_result_text: str, ai_latency_ms: int
) -> None:
    """Mark the row succeeded and store the AI output."""
    _update_status(
        asset_id,
        {
            "ai_status": "succeeded",
            "ai_result_text": ai_result_text,
            "ai_latency_ms": ai_latency_ms,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def mark_failed(
    asset_id: str, *, ai_error: str, ai_latency_ms: int
) -> None:
    """Mark the row failed with a short, redaction-aware error string.
    The dispatcher truncates ``ai_error`` to ~500 chars before calling
    so we never persist a multi-line traceback (PII risk)."""
    _update_status(
        asset_id,
        {
            "ai_status": "failed",
            "ai_error": ai_error,
            "ai_latency_ms": ai_latency_ms,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _update_status(asset_id: str, patch: dict) -> None:
    from app.db import supabase

    try:
        supabase.table("patient_uploads").update(patch).eq(
            "asset_id", asset_id
        ).execute()
    except Exception as exc:  # noqa: BLE001 — never crash the BG task
        logger.warning(
            "patient_uploads.update_failed asset_id=%s patch=%s: %s",
            asset_id, list(patch.keys()), exc,
        )


def get_upload(asset_id: str) -> Optional[dict]:
    """Fetch a single row for the polling endpoint. Returns None on
    not-found OR tombstoned (callers treat both the same — the row is
    no longer accessible)."""
    from app.db import supabase

    resp = (
        supabase.table("patient_uploads")
        .select(
            "asset_id, session_id, ai_status, ai_provider, ai_result_text, "
            "ai_error, ai_latency_ms, upload_kind, content_type, size_bytes, "
            "consent_to_process, consent_text, expires_at, created_at, "
            "processed_at, deleted_at"
        )
        .eq("asset_id", asset_id)
        .maybe_single()
        .execute()
    )
    if not resp or not resp.data:
        return None
    if resp.data.get("deleted_at"):
        return None  # tombstoned == not found
    return resp.data


# ─── Tombstone (KVKK) ────────────────────────────────────────────────


def tombstone_expired_uploads(*, reason: str = "scheduled_retention") -> int:
    """Tombstone every live row whose ``expires_at`` is in the past.

    Called by the nightly retention cron via
    ``POST /v1/admin/retention/patient-uploads/sweep``. Same NULLing
    shape as ``tombstone_uploads_for_session`` so downstream consumers
    see a uniform tombstone contract regardless of how the row got
    swept.

    Idempotency: the ``.is_("deleted_at", "null")`` filter excludes
    already-tombstoned rows, so re-running the sweep is a no-op.

    Returns the number of rows tombstoned. -1 on DB error so the
    caller can surface a non-200 to the cron without crashing the
    workflow run.
    """
    from app.db import supabase

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        resp = (
            supabase.table("patient_uploads")
            .update(
                {
                    "sha256_hex": None,
                    "ai_result_text": None,
                    "ai_error": None,
                    "consent_text": None,
                    "deleted_at": now_iso,
                    "deleted_reason": reason,
                }
            )
            .lt("expires_at", now_iso)
            .is_("deleted_at", "null")
            .execute()
        )
        count = len(resp.data or [])
        if count:
            logger.info(
                "patient_uploads.retention_sweep tombstoned=%d reason=%s",
                count, reason,
            )
        return count
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "patient_uploads.retention_sweep_failed: %s", exc
        )
        return -1


def tombstone_uploads_for_session(
    session_id: str, *, reason: str = "user_request"
) -> int:
    """Tombstone every upload row tied to ``session_id``. Mirrors the
    triage_sessions tombstone shape: row stays for cross-reference,
    content columns NULLed, deleted_at + deleted_reason set.

    Returns the number of rows tombstoned. -1 on DB error (caller
    decides whether to abort the data-rights operation; we don't
    want a transient Supabase blip to block the user from deleting
    their session).
    """
    from app.db import supabase

    try:
        resp = (
            supabase.table("patient_uploads")
            .update(
                {
                    "sha256_hex": None,
                    "ai_result_text": None,
                    "ai_error": None,
                    "consent_text": None,
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "deleted_reason": reason,
                }
            )
            .eq("session_id", session_id)
            .is_("deleted_at", "null")  # idempotent: skip already-tombstoned
            .execute()
        )
        return len(resp.data or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "patient_uploads.tombstone_failed session_id=%s: %s",
            session_id, exc,
        )
        return -1
