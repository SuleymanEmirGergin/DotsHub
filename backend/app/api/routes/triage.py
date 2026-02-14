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

from fastapi import APIRouter, HTTPException

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
    """Handle a turn using Supabase sessions + deterministic triage engine."""
    from app.triage_types import TriageTurnIn
    from app.session_repo import create_session, update_session, append_event, get_session
    from app.triage_engine import run_orchestrator_turn
    from app.runtime import load_runtime
    from app.pii import redact_pii

    # Load runtime (cached at module level after first call)
    global _RUNTIME
    if "_RUNTIME" not in globals() or _RUNTIME is None:
        _RUNTIME = load_runtime()
    runtime = _RUNTIME

    # Convert legacy request model to new model
    session_id_str = request.session_id
    session_id_uuid = UUID(session_id_str) if session_id_str else None

    # Redact PII before storing
    user_msg_redacted = redact_pii(request.user_message or "")

    # 1) Session load/create
    if session_id_uuid is None:
        sid = create_session(request.locale or "tr-TR", user_msg_redacted)
        session = get_session(sid)
        turn_index = 0
        answers: dict = {}
        asked: list = []
        input_text = user_msg_redacted
        append_event(sid, "SESSION_CREATED", {"input_text": input_text})
    else:
        sid = session_id_uuid
        session = get_session(sid)
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
        })

    if user_msg_redacted:
        append_event(sid, "USER_MESSAGE", {"text": user_msg_redacted})

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
    append_event(sid, f"ENVELOPE_{envelope_type}", event_payload)

    session_meta = session.get("meta") if isinstance(session, dict) and isinstance(session.get("meta"), dict) else {}
    if envelope_type == "RESULT" and isinstance(client_payload.get("risk"), dict):
        patch["meta"] = {**session_meta, "risk": client_payload["risk"]}
    elif session_meta:
        patch["meta"] = session_meta

    update_session(sid, patch)
    facility_discovery = _build_facility_discovery(
        envelope_type, client_payload, lat=request.lat, lon=request.lon
    )

    return Envelope(
        type=envelope_type,
        session_id=str(sid),
        turn_index=turn_index + 1,
        payload=client_payload,
        meta=_make_meta(facility_discovery=facility_discovery),
    )


# ──────────────────────────────────────────────────────────
# Legacy: in-memory orchestrator (agents-based)
# ──────────────────────────────────────────────────────────

async def _handle_turn_legacy(request: TriageTurnRequest) -> Envelope:
    """Handle a turn using the legacy agentic orchestrator."""
    from app.agents.orchestrator import orchestrator

    result = await orchestrator.handle_turn(
        session_id=request.session_id,
        user_message=request.user_message or "",
        answer_canonical=request.answer.canonical if request.answer else None,
        answer_value=request.answer.value if request.answer else None,
        locale=request.locale or "tr-TR",
    )
    facility_discovery = _build_facility_discovery(
        result["type"], result["payload"], lat=request.lat, lon=request.lon
    )
    return Envelope(
        type=result["type"],
        session_id=result["session_id"],
        turn_index=result.get("turn_index", 0),
        payload=result["payload"],
        meta=_make_meta(facility_discovery=facility_discovery),
    )


# ──────────────────────────────────────────────────────────
# Route
# ──────────────────────────────────────────────────────────

_RUNTIME = None  # module-level cache


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
                    return await _handle_turn_legacy(request)
                raise
        return await _handle_turn_legacy(request)

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
