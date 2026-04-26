"""AI dispatcher for patient uploads.

Wires the upload route to the right Wiro AI wrapper based on
``upload_kind``. The route schedules a BackgroundTask that calls
``dispatch_to_ai``; this module owns:

  - kind-to-service routing (image -> moondream, audio -> whisper,
    video -> cogvlm, document -> dots_ocr)
  - Prometheus / Sentry observability per attempt
  - Status updates on the patient_uploads row via
    ``patient_uploads.mark_*``

This file lands as a **placeholder** in B2 (the route commit). Every
kind currently routes to ``mark_failed`` with reason
"dispatcher_not_implemented" — the route + polling layer is fully
wired against this, so when B3 fills in the real Wiro dispatch logic
no route or schema change is needed.

Why split B2 / B3 this way:
  - B2 commit lands the public HTTP surface so the dashboard /
    mobile client teams can integrate against the contract.
  - B3 commit lands the actual AI work. PATIENT_UPLOAD_ENABLED stays
    off across both commits, so a half-wired prod is impossible.
"""
from __future__ import annotations

import logging
import time

from app.services import patient_uploads

logger = logging.getLogger(__name__)


def dispatch_to_ai(
    asset_id: str,
    content_bytes: bytes,
    *,
    upload_kind: str,
    content_type: str,
    filename: str = "",
) -> None:
    """Run the kind-appropriate AI service against ``content_bytes``
    and write the result back to the patient_uploads row.

    Called from a FastAPI BackgroundTask so it inherits no request
    scope and must NEVER raise — observability hooks log the failure
    instead and ``mark_failed`` records it on the row.
    """
    t_start = time.perf_counter()
    # Placeholder: B3 replaces this with the real kind -> AI service
    # routing. Until then, every dispatch immediately marks failed so
    # a misconfiguration that flips PATIENT_UPLOAD_ENABLED on without
    # the B3 commit doesn't silently swallow uploads.
    elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    logger.warning(
        "patient_upload_dispatcher.placeholder asset_id=%s kind=%s "
        "(B3 not yet landed)",
        asset_id, upload_kind,
    )
    patient_uploads.mark_failed(
        asset_id,
        ai_error="dispatcher_not_implemented (B3 commit not yet landed)",
        ai_latency_ms=elapsed_ms,
    )
