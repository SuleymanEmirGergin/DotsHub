"""POST /v1/patient/upload + GET /v1/patient/upload/{asset_id}.

Multipart upload route for patient-submitted assets (selfie / voice
memo / lab scan / video clip). Bytes are NOT persisted — the route
hashes them, inserts a metadata row in ``patient_uploads``, and
schedules a BackgroundTask that pipes the bytes to the appropriate
Wiro AI service. Bytes leave the process when the BG task returns.

UX contract:
    POST returns 201 with ``{asset_id, status: "pending", poll_url}``
    almost immediately (the AI work happens in the background).
    Client then polls GET /v1/patient/upload/{asset_id} until
    status flips to ``succeeded`` or ``failed``. The GET response
    includes a ``Retry-After`` header keyed to
    ``PATIENT_UPLOAD_POLL_INTERVAL_SECONDS`` so naive clients can
    just honour it.

KVKK contract:
    ``consent_to_process`` form field must be ``true`` — the route
    422s otherwise. ``consent_text`` is the operator-visible string
    describing what the patient agreed the bytes would be used for
    ("hair-loss estimate", "voice transcription for clinical notes",
    ...). Stored on the row; cleared at tombstone time.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
)

from app.core.config import settings
from app.services import patient_upload_dispatcher, patient_uploads

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── POST /v1/patient/upload ────────────────────────────────────────


@router.post("/patient/upload", status_code=201)
async def upload_asset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    kind: str = Form(...),
    consent_to_process: bool = Form(...),
    consent_text: Optional[str] = Form(default=None),
    prompt_preset: Optional[str] = Form(default=None),
    x_session_id: Optional[str] = Header(default=None),
):
    """Accept a single asset, validate, hash, and schedule AI dispatch.

    Returns 201 immediately with the asset_id; AI processing happens
    in a BackgroundTask. Failure modes surface synchronously:

    Status codes:
      - 201: accepted; pending dispatch.
      - 400: missing X-Session-Id header.
      - 413: file size exceeds the kind's cap.
      - 415: content-type not allowed for the declared kind.
      - 422: consent_to_process=false OR unknown kind OR empty file.
      - 503: PATIENT_UPLOAD_ENABLED is off.
    """
    if not getattr(settings, "PATIENT_UPLOAD_ENABLED", False):
        raise HTTPException(
            status_code=503,
            detail="PATIENT_UPLOAD_ENABLED is off",
        )
    if not x_session_id:
        # We don't auto-mint a session here -- a triage session is
        # the canonical container, and creating one off-flow would
        # produce orphan uploads that the data-rights endpoint can't
        # tombstone.
        raise HTTPException(
            status_code=400,
            detail="X-Session-Id header is required",
        )

    # Read bytes once; UploadFile is a SpooledTemporaryFile, so a
    # second .read() returns empty. We hold the bytes in memory for
    # the dispatcher.
    content = await file.read()
    size_bytes = len(content)
    content_type = (file.content_type or "").strip()

    try:
        patient_uploads.validate_upload(
            kind=kind,
            content_type=content_type,
            size_bytes=size_bytes,
            consent_to_process=consent_to_process,
        )
        patient_uploads.validate_prompt_preset(kind, prompt_preset)
    except patient_uploads.UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail
        ) from exc

    sha256_hex = patient_uploads.compute_sha256(content)
    try:
        asset_id = patient_uploads.record_upload(
            session_id=x_session_id,
            sha256_hex=sha256_hex,
            content_type=content_type,
            size_bytes=size_bytes,
            upload_kind=kind,
            consent_to_process=consent_to_process,
            consent_text=consent_text,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("patient_upload.record_failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="upload registration failed"
        ) from exc

    # Schedule the dispatcher. BackgroundTasks runs after the response
    # is sent; bytes stay alive for the closure's lifetime, then GC.
    background_tasks.add_task(
        patient_upload_dispatcher.dispatch_to_ai,
        asset_id,
        content,
        upload_kind=kind,
        content_type=content_type,
        filename=file.filename or "",
        prompt_preset=prompt_preset,
    )

    return {
        "asset_id": asset_id,
        "status": "pending",
        "poll_url": f"/v1/patient/upload/{asset_id}",
    }


# ─── GET /v1/patient/upload/{asset_id} ──────────────────────────────


@router.get("/patient/upload/{asset_id}")
def get_asset_status(asset_id: str, response: Response):
    """Polling endpoint. Returns the current ai_status + result.

    Adds ``Retry-After`` to point the client at a sensible polling
    interval when the row is still pending/processing; absent on
    terminal states (succeeded / failed) so a client that respects
    the header naturally stops polling.

    404 on:
      - asset_id not found
      - row has been tombstoned (KVKK delete)
    """
    if not getattr(settings, "PATIENT_UPLOAD_ENABLED", False):
        raise HTTPException(
            status_code=503, detail="PATIENT_UPLOAD_ENABLED is off"
        )

    row = patient_uploads.get_upload(asset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="asset not found")

    status = row.get("ai_status", "pending")
    if status in ("pending", "processing"):
        response.headers["Retry-After"] = str(
            getattr(settings, "PATIENT_UPLOAD_POLL_INTERVAL_SECONDS", 5)
        )

    # Surface a curated subset; we don't echo session_id (operator
    # data) or sha256_hex (internal forensic) to the client.
    return {
        "asset_id": row["asset_id"],
        "status": status,
        "ai_provider": row.get("ai_provider"),
        "ai_result_text": row.get("ai_result_text"),
        "ai_error": row.get("ai_error"),
        "ai_latency_ms": row.get("ai_latency_ms"),
        "upload_kind": row.get("upload_kind"),
        "content_type": row.get("content_type"),
        "size_bytes": row.get("size_bytes"),
        "expires_at": row.get("expires_at"),
        "created_at": row.get("created_at"),
        "processed_at": row.get("processed_at"),
    }
