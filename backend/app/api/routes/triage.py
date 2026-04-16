"""Unified Triage Turn endpoint — V5 with Supabase session management + deterministic pipeline.

POST /v1/triage/turn
Frontend sends TriageTurnIn, gets EnvelopeOut back.
type field determines what to render: QUESTION | RESULT | EMERGENCY | ERROR.

This version:
  - Creates/updates sessions in Supabase (triage_sessions)
  - Logs events to triage_events
  - Runs the full deterministic pipeline (no LLM)
  - Falls back to the legacy orchestrator if SUPABASE_URL is not set
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query

from app.models.schemas import (
    TriageTurnRequest,
    Envelope,
    Meta,
)
from app.services.facility_discovery import discover_facilities, DEFAULT_CITY
from app.core.config import settings
from app.core.i18n import get_text

from copy import deepcopy

logger = logging.getLogger(__name__)
router = APIRouter()

DISCLAIMER = "Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır."


def _make_meta(debug: dict = None, facility_discovery: Optional[dict] = None) -> Meta:
    return Meta(
        disclaimer_tr=DISCLAIMER,
        timestamp=datetime.now(timezone.utc),
        debug=debug,
        facility_discovery=facility_discovery,
    )


def _has_supabase() -> bool:
    return (
        bool(settings.SUPABASE_URL)
        and bool(settings.SUPABASE_SERVICE_ROLE_KEY)
        and "xxxx" not in settings.SUPABASE_URL
    )


def _is_missing_supabase_schema_error(exc: Exception) -> bool:
    text = str(exc)
    schema_markers = (
        "PGRST205",
        "42P01",
        'relation "triage_sessions" does not exist',
        'relation "triage_events" does not exist',
        "Could not find the table 'public.triage_sessions'",
        "Could not find the table 'public.triage_events'",
    )
    return any(marker in text for marker in schema_markers)


def _extract_specialty_key_from_payload(payload: dict) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    recommended = payload.get("recommended_specialty")
    if isinstance(recommended, dict) and recommended.get("id"):
        return str(recommended["id"])

    specialty_id = payload.get("recommended_specialty_id")
    if specialty_id is None:
        return None
    return str(specialty_id)


def _build_facility_discovery(
    envelope_type: str,
    payload: dict,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Optional[dict]:
    if envelope_type != "RESULT":
        return None

    specialty_key = _extract_specialty_key_from_payload(payload)
    if not specialty_key:
        return None

    try:
        return discover_facilities(
            city=DEFAULT_CITY,
            specialty_key=specialty_key,
            limit=5,
            lat=lat,
            lon=lon,
        )
    except Exception as e:
        logger.warning("Facility discovery failed in triage route: %s", e)
        return None


# ──────────────────────────────────────────────────────────
# New: Supabase-backed deterministic turn
# ──────────────────────────────────────────────────────────

def _handle_turn_supabase(request: TriageTurnRequest) -> Envelope:
    """Handle a turn using Supabase sessions + deterministic triage engine (Faz 1: single tenant)."""
    from app.triage_types import TriageTurnIn
    from app.session_repo import create_session, update_session, append_event, get_session
    from app.triage_engine import run_orchestrator_turn
    from app.runtime import get_runtime
    from app.tenant import get_tenant_id_for_triage
    from app.pii import redact_pii

    tenant_id = get_tenant_id_for_triage()
    runtime = get_runtime(tenant_id)

    # Convert legacy request model to new model
    session_id_str = request.session_id
    session_id_uuid = UUID(session_id_str) if session_id_str else None

    # Redact PII before storing
    user_msg_redacted = redact_pii(request.user_message or "")

    # 1) Session load/create (Faz 1: triage tenant = default)
    if session_id_uuid is None:
        sid = create_session(request.locale or "tr-TR", user_msg_redacted, tenant_id=tenant_id)
        session = get_session(sid, tenant_id=tenant_id)
        turn_index = 0
        answers: dict = {}
        asked: list = []
        input_text = user_msg_redacted
        append_event(sid, "SESSION_CREATED", {"input_text": input_text}, tenant_id=tenant_id)
    else:
        sid = session_id_uuid
        session = get_session(sid, tenant_id=tenant_id)
        if not session:
            raise HTTPException(status_code=404, detail="session_id not found")

        turn_index = int(session.get("turn_index") or 0)
        answers = session.get("answers") or {}
        asked = session.get("asked_canonicals") or []
        input_text = session.get("input_text") or ""

        # Append new user_message (redacted)
        if user_msg_redacted:
            input_text = (input_text + "\n" + user_msg_redacted).strip()

    # 2) Process answer if provided
    if request.answer is not None:
        answers[request.answer.canonical] = request.answer.value
        if request.answer.canonical not in asked:
            asked.append(request.answer.canonical)
        append_event(sid, "ANSWER_RECEIVED", {
            "canonical": request.answer.canonical,
            "value": request.answer.value,
        }, tenant_id=tenant_id)

    if user_msg_redacted:
        append_event(sid, "USER_MESSAGE", {"text": user_msg_redacted}, tenant_id=tenant_id)

    # 3) Run deterministic orchestrator
    envelope_type, payload, debug_patch = run_orchestrator_turn(
        runtime=runtime,
        input_text=input_text,
        answers=answers,
        asked_canonicals=asked,
        turn_index=turn_index + 1,
    )

    # 4) Patch session
    patch = {
        "input_text": input_text,
        "answers": answers,
        "asked_canonicals": asked,
        "turn_index": turn_index + 1,
        "envelope_type": envelope_type,
        **debug_patch,
    }

    # ─── Split payload: client vs event ───
    # Client gets clean response (no _meta)
    # Event keeps full debug data for analytics
    client_payload = deepcopy(payload or {})
    event_payload = deepcopy(payload or {})
    
    # Strip _meta from client response
    client_payload.pop("_meta", None)
    
    # Event payload keeps _meta and adds turn index
    event_payload["_turn_index"] = turn_index + 1
    append_event(sid, f"ENVELOPE_{envelope_type}", event_payload, tenant_id=tenant_id)

    session_meta = session.get("meta") if isinstance(session, dict) and isinstance(session.get("meta"), dict) else {}
    if envelope_type == "RESULT" and isinstance(client_payload.get("risk"), dict):
        patch["meta"] = {**session_meta, "risk": client_payload["risk"]}
    elif session_meta:
        patch["meta"] = session_meta

    update_session(sid, patch)
    facility_discovery = _build_facility_discovery(
        envelope_type, client_payload, lat=request.lat, lon=request.lon
    )

    # ── Webhook notification (fire-and-forget) ──
    try:
        from app.notifier import send_alert

        risk_obj = client_payload.get("risk") if isinstance(client_payload, dict) else None
        risk_level = risk_obj.get("level") if isinstance(risk_obj, dict) else None
        send_alert(
            envelope_type=envelope_type,
            session_id=str(sid),
            payload=client_payload,
            risk_level=risk_level,
        )
    except Exception as exc:
        logger.debug("Notifier call skipped: %s", exc)

    # ── Push notification (fire-and-forget) ──
    try:
        from app.push import send_push_alert

        risk_obj2 = client_payload.get("risk") if isinstance(client_payload, dict) else None
        risk_level2 = risk_obj2.get("level") if isinstance(risk_obj2, dict) else None
        send_push_alert(
            envelope_type=envelope_type,
            session_id=str(sid),
            payload=client_payload,
            risk_level=risk_level2,
        )
    except Exception as exc:
        logger.debug("Push notification skipped: %s", exc)

    return Envelope(
        type=envelope_type,
        session_id=str(sid),
        turn_index=turn_index + 1,
        payload=client_payload,
        meta=_make_meta(facility_discovery=facility_discovery),
    )


# ──────────────────────────────────────────────────────────
# Legacy: in-memory deterministic pipeline (no Supabase; tenant-aware runtime)
# ──────────────────────────────────────────────────────────

# In-memory session state for legacy path (keyed by session_id)
_legacy_sessions: dict[str, dict] = {}


def _handle_turn_legacy(request: TriageTurnRequest) -> Envelope:
    """Handle a turn using the same deterministic pipeline as Supabase path, with in-memory session (tenant-aware runtime)."""
    from app.triage_engine import run_orchestrator_turn
    from app.runtime import get_runtime
    from app.tenant import get_tenant_id_for_triage
    from app.pii import redact_pii

    tenant_id = get_tenant_id_for_triage()
    runtime = get_runtime(tenant_id)
    user_msg_redacted = redact_pii(request.user_message or "")

    session_id_str = request.session_id
    if not session_id_str:
        import uuid
        sid = str(uuid.uuid4())
        _legacy_sessions[sid] = {
            "answers": {},
            "asked_canonicals": [],
            "input_text": user_msg_redacted,
            "turn_index": 0,
        }
    else:
        sid = session_id_str
        if sid not in _legacy_sessions:
            raise HTTPException(status_code=404, detail="session_id not found")
        state = _legacy_sessions[sid]
        state["input_text"] = (state.get("input_text") or "").strip()
        if user_msg_redacted:
            state["input_text"] = (state["input_text"] + "\n" + user_msg_redacted).strip()
        state["answers"] = state.get("answers") or {}
        state["asked_canonicals"] = state.get("asked_canonicals") or []

    state = _legacy_sessions[sid]
    if request.answer is not None:
        state["answers"][request.answer.canonical] = request.answer.value
        if request.answer.canonical not in state["asked_canonicals"]:
            state["asked_canonicals"].append(request.answer.canonical)

    turn_index = state.get("turn_index", 0) + 1
    envelope_type, payload, debug_patch = run_orchestrator_turn(
        runtime=runtime,
        input_text=state.get("input_text") or "",
        answers=state.get("answers") or {},
        asked_canonicals=state.get("asked_canonicals") or [],
        turn_index=turn_index,
    )

    state["turn_index"] = turn_index
    state["input_text"] = state.get("input_text") or ""
    state["answers"] = state.get("answers") or {}
    state["asked_canonicals"] = state.get("asked_canonicals") or []

    client_payload = deepcopy(payload or {})
    client_payload.pop("_meta", None)
    facility_discovery = _build_facility_discovery(
        envelope_type, client_payload, lat=request.lat, lon=request.lon
    )
    return Envelope(
        type=envelope_type,
        session_id=sid,
        turn_index=turn_index,
        payload=client_payload,
        meta=_make_meta(facility_discovery=facility_discovery),
    )


# ──────────────────────────────────────────────────────────
# Route
# ──────────────────────────────────────────────────────────


@router.get("/triage/history")
def triage_history(
    limit: int = Query(default=50, ge=1),
    x_device_id: str | None = Header(default=None),
):
    """Return recent triage sessions for the device.

    Uses x-device-id to filter sessions when available.
    Returns basic session info for the history screen.
    """
    if not _has_supabase():
        return {"items": []}
    if not x_device_id:
        return {"items": []}

    from app.supabase_client import get_supabase as _get_sb
    from app.tenant import get_tenant_id_for_triage
    sb = _get_sb()
    tenant_id = get_tenant_id_for_triage()

    q = (
        sb.table("triage_sessions")
        .select("id,created_at,envelope_type,recommended_specialty_tr,confidence_label_tr,confidence_0_1,stop_reason")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .eq("device_id", x_device_id)
        .limit(min(limit, 100))
    )

    # Filter by envelope_type to only show completed sessions
    q = q.in_("envelope_type", ["RESULT", "EMERGENCY", "SAME_DAY"])

    try:
        rows = q.execute().data or []
    except Exception:
        # Fail closed if the storage layer cannot enforce device scoping.
        return {"items": []}

    return {"items": rows}


@router.post("/triage/turn", response_model=Envelope)
async def triage_turn(request: TriageTurnRequest):
    """Run one triage turn — unified single endpoint.

    - session_id=null → start new session
    - session_id + user_message → process free-text
    - session_id + answer → process structured answer

    Uses Supabase + deterministic pipeline when SUPABASE_URL is configured,
    falls back to legacy agentic orchestrator otherwise.
    """
    try:
        # Validate: need at least user_message or answer
        has_message = bool(request.user_message and request.user_message.strip())
        has_answer = request.answer is not None

        if not has_message and not has_answer:
            if request.session_id is not None:
                return Envelope(
                    type="ERROR",
                    session_id=request.session_id or "unknown",
                    turn_index=0,
                    payload={
                        "code": "EMPTY_INPUT",
                        "message_tr": get_text(request.locale, "EMPTY_INPUT"),
                    },
                    meta=_make_meta(),
                )

        # Route to Supabase pipeline or legacy
        if _has_supabase():
            try:
                return _handle_turn_supabase(request)
            except Exception as exc:
                if _is_missing_supabase_schema_error(exc):
                    logger.warning(
                        "Supabase schema missing (triage_sessions/triage_events). Falling back to legacy orchestrator: %s",
                        exc,
                    )
                    return _handle_turn_legacy(request)
                raise
        return _handle_turn_legacy(request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in triage turn: {e}", exc_info=True)
        return Envelope(
            type="ERROR",
            session_id=request.session_id or "unknown",
            turn_index=0,
            payload={
                "code": "TURN_FAILED",
                "message_tr": get_text(getattr(request, "locale", None), "TURN_FAILED") + ": " + str(e),
                "retryable": True,
            },
            meta=_make_meta(),
        )


# ──────────────────────────────────────────────────────────
# SSE streaming endpoint: POST /v1/triage/stream
# ──────────────────────────────────────────────────────────

import asyncio
import json as _json
from fastapi.responses import StreamingResponse


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE message."""
    payload = _json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/triage/stream")
async def triage_stream(request: TriageTurnRequest):
    """Streaming variant of /v1/triage/turn using Server-Sent Events.

    Emits three events in sequence:
      1. ``thinking``  — immediate acknowledgement so the client can show a spinner
      2. ``envelope``  — the full triage result (same structure as /triage/turn response)
      3. ``done``      — signals end of stream

    On error emits an ``error`` event then ``done``.

    Client usage (JavaScript):
        const es = await fetch('/v1/triage/stream', {method:'POST', body: JSON.stringify(body)});
        const reader = es.body.getReader();
        // parse SSE lines
    """

    async def _generate():
        # 1) Immediate thinking event — lets the UI show a spinner without waiting
        yield _sse_event("thinking", {"message_tr": "Analiz ediliyor…", "turn_index": 0})

        try:
            # 2) Run the triage engine (blocking) in a thread pool so we don't block the event loop
            loop = asyncio.get_event_loop()

            if _has_supabase():
                envelope = await loop.run_in_executor(
                    None, lambda: _handle_turn_supabase(request)
                )
            else:
                envelope = await _handle_turn_legacy(request)

            # 3) Emit the full envelope as an SSE event
            envelope_dict = envelope.model_dump(mode="json")
            yield _sse_event("envelope", envelope_dict)

        except Exception as exc:
            logger.error("SSE triage_stream error: %s", exc, exc_info=True)
            yield _sse_event(
                "error",
                {
                    "code": "STREAM_FAILED",
                    "message_tr": "Bir hata oluştu, lütfen tekrar deneyin.",
                    "detail": str(exc),
                },
            )

        finally:
            # 4) Always close the stream
            yield _sse_event("done", {})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
