"""Session CRUD helpers — Supabase upsert + event log.

Every turn:
  - session yoksa → create
  - varsa → update (patch)
  - Her envelope → triage_events'e event yaz
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import UUID

from app.supabase_client import get_supabase


def create_session(locale: str, input_text: str) -> UUID:
    """Create a new triage session and return its UUID."""
    sb = get_supabase()
    ins = sb.table("triage_sessions").insert({
        "locale": locale,
        "input_text": input_text,
        "envelope_type": "QUESTION",
        "turn_index": 0,
    }).execute()

    if not ins.data:
        raise RuntimeError("Failed to create session")
    return UUID(ins.data[0]["id"])


def update_session(session_id: UUID, patch: Dict[str, Any]) -> None:
    """Patch an existing triage session."""
    sb = get_supabase()
    upd = (
        sb.table("triage_sessions")
        .update(patch)
        .eq("id", str(session_id))
        .execute()
    )
    if upd.data is None:
        raise RuntimeError("Failed to update session")


def append_event(
    session_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Write a row to triage_events (immutable log)."""
    sb = get_supabase()
    sb.table("triage_events").insert({
        "session_id": str(session_id),
        "event_type": event_type,
        "payload": payload,
    }).execute()


def get_session(session_id: UUID) -> Optional[Dict[str, Any]]:
    """Load a session by id. Returns None if not found."""
    sb = get_supabase()
    res = (
        sb.table("triage_sessions")
        .select("*")
        .eq("id", str(session_id))
        .single()
        .execute()
    )
    return res.data if res and res.data else None
