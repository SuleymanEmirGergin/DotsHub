"""Push notification sender — Expo Push API.

Sends push notifications when EMERGENCY or HIGH-risk RESULT envelopes are produced.
Works alongside webhook notifications (notifier.py).

Also exposes ``send_followup_reminders`` for the admin-triggered
follow-up flow: find RESULT sessions from yesterday that haven't
received feedback and nudge the originating device to rate the
experience. See admin_v5.py route for the HTTP entry point.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

# Lazy proxy for app.db.supabase — importing the real client at module
# load time would break every CI test that imports app.main when
# SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are absent (app.db raises
# RuntimeError in that case). Same pattern as admin_v5.py and
# data_rights.py.
class _LazySupabase:
    def __getattr__(self, item):
        from app.db import supabase as _sb
        return getattr(_sb, item)


supabase = _LazySupabase()

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


# ── Public API ──────────────────────────────────────────────


def register_token(
    device_id: str,
    expo_token: str,
    platform: str = "unknown",
    locale: str = "tr-TR",
) -> Dict[str, Any]:
    """Register or update a push token for a device."""
    sb = supabase
    # Upsert by device_id
    resp = (
        sb.table("push_tokens")
        .upsert(
            {
                "device_id": device_id,
                "expo_token": expo_token,
                "platform": platform,
                "locale": locale,
                "active": True,
            },
            on_conflict="device_id",
        )
        .execute()
    )
    return {"ok": True, "data": resp.data}


def unregister_token(device_id: str) -> Dict[str, Any]:
    """Mark a device's push token as inactive."""
    sb = supabase
    resp = (
        sb.table("push_tokens")
        .update({"active": False})
        .eq("device_id", device_id)
        .execute()
    )
    return {"ok": True, "data": resp.data}


def send_push_alert(
    envelope_type: str,
    session_id: str,
    payload: Dict[str, Any],
    risk_level: Optional[str] = None,
) -> None:
    """Fire push notification in background thread. Never blocks triage flow."""
    # Only alert on EMERGENCY or HIGH risk RESULT
    should_alert = (
        envelope_type == "EMERGENCY"
        or (envelope_type == "RESULT" and risk_level == "HIGH")
    )
    if not should_alert:
        return

    thread = threading.Thread(
        target=_dispatch_push,
        args=(envelope_type, session_id, payload, risk_level),
        daemon=True,
    )
    thread.start()


# ── Internal ────────────────────────────────────────────────


def _get_active_tokens() -> List[str]:
    """Fetch all active Expo push tokens."""
    sb = supabase
    resp = (
        sb.table("push_tokens")
        .select("expo_token")
        .eq("active", True)
        .limit(500)
        .execute()
    )
    return [r["expo_token"] for r in (resp.data or []) if r.get("expo_token")]


def _dispatch_push(
    envelope_type: str,
    session_id: str,
    payload: Dict[str, Any],
    risk_level: Optional[str],
) -> None:
    """Send push to all registered devices."""
    try:
        tokens = _get_active_tokens()
        if not tokens:
            return

        # Build notification
        if envelope_type == "EMERGENCY":
            title = "🚨 Acil Durum Tespit Edildi"
            body = payload.get("reason_tr", "Acil durum — hemen kontrol edin")
        else:
            spec = payload.get("recommended_specialty", {})
            spec_name = spec.get("name_tr", "?") if isinstance(spec, dict) else str(spec)
            conf = payload.get("confidence_0_1")
            conf_str = f"{round(float(conf) * 100)}%" if conf is not None else "?"
            title = "⚠️ Yüksek Risk Sonucu"
            body = f"Branş: {spec_name} · Güven: {conf_str}"

        messages = [
            {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
                "data": {
                    "session_id": session_id,
                    "envelope_type": envelope_type,
                },
            }
            for token in tokens
        ]

        # Expo Push API supports batches of up to 100
        with httpx.Client(timeout=15) as client:
            for i in range(0, len(messages), 100):
                batch = messages[i : i + 100]
                resp = client.post(EXPO_PUSH_URL, json=batch)
                if resp.status_code >= 400:
                    logger.warning(
                        "Expo push failed (status=%s): %s",
                        resp.status_code,
                        resp.text[:200],
                    )

    except Exception as exc:
        logger.warning("Push notification dispatch failed: %s", exc)


# ── Follow-up reminders ─────────────────────────────────────
# Messaging copy, separated from logic so localization can be added
# later without touching the query path. locale from push_tokens row
# selects the variant; falls back to TR if locale is missing/unknown.
_FOLLOWUP_COPY: Dict[str, Dict[str, str]] = {
    "tr": {
        "title": "💬 Geri bildiriminizi alalım",
        "body": "Dünkü ön-triaj önerisi işinize yaradı mı? Kısa bir geri bildirim çok değerli.",
    },
    "en": {
        "title": "💬 How did it go?",
        "body": "Did yesterday's pre-triage recommendation help? A quick thumbs-up/down means a lot.",
    },
}


def _pick_copy(locale_raw: Optional[str]) -> Dict[str, str]:
    """Return follow-up copy for a locale, defaulting to TR.

    Accepts ``tr``, ``tr-TR``, ``en``, ``en-US`` etc. — normalizes by
    splitting on ``-``. Unknown locales fall back to TR.
    """
    if not locale_raw:
        return _FOLLOWUP_COPY["tr"]
    base = locale_raw.split("-")[0].lower()
    return _FOLLOWUP_COPY.get(base, _FOLLOWUP_COPY["tr"])


def send_followup_reminders(
    hours_min: int = 20,
    hours_max: int = 48,
) -> Dict[str, Any]:
    """Send follow-up push to RESULT sessions that never got feedback.

    Target window: sessions created between ``hours_max`` and ``hours_min``
    hours ago (default 20–48h). Lower bound of 20h avoids nudging users
    who just finished; upper bound of 48h avoids re-pinging stale sessions
    on repeated calls from a daily cron.

    Filters applied:
      * envelope_type in (RESULT, SAME_DAY) — skip EMERGENCY (already
        pushed via ``send_push_alert``) and QUESTION/ERROR (incomplete)
      * device_id is not null — can't notify unknown devices
      * session has no feedback row (checked via anti-join below)

    Join strategy: we don't have a true SQL JOIN via the PostgREST
    client, so the function does a two-step fetch (sessions → tokens by
    device_id) in Python. Expected cardinality is small (most days < 500
    eligible sessions) so this stays fast.

    Returns a summary dict with counters so the admin endpoint can show
    "Sent N follow-ups" feedback. Does not raise on per-token send
    failures; logs them so one bad token doesn't stop the batch.
    """
    now = datetime.now(timezone.utc)
    lower = (now - timedelta(hours=hours_max)).isoformat()
    upper = (now - timedelta(hours=hours_min)).isoformat()

    sb = supabase

    candidate_sessions = (
        sb.table("triage_sessions")
        .select("id,device_id,locale,envelope_type,recommended_specialty_tr")
        .gte("created_at", lower)
        .lte("created_at", upper)
        .in_("envelope_type", ["RESULT", "SAME_DAY"])
        .not_.is_("device_id", "null")
        .limit(2000)
        .execute()
        .data
        or []
    )

    if not candidate_sessions:
        return {"sent": 0, "skipped_feedback": 0, "skipped_no_token": 0, "candidates": 0}

    session_ids = [s["id"] for s in candidate_sessions if s.get("id")]

    # Anti-join: find session_ids that DO have feedback; exclude them.
    # Chunked in_ filter for Supabase URL-length safety (~500/chunk).
    feedback_session_ids: set[str] = set()
    for i in range(0, len(session_ids), 500):
        chunk = session_ids[i : i + 500]
        fb = (
            sb.table("triage_feedback")
            .select("session_id")
            .in_("session_id", chunk)
            .execute()
            .data
            or []
        )
        for row in fb:
            sid = row.get("session_id")
            if isinstance(sid, str):
                feedback_session_ids.add(sid)

    eligible = [s for s in candidate_sessions if s["id"] not in feedback_session_ids]
    skipped_feedback = len(candidate_sessions) - len(eligible)

    # Resolve device_id → expo_token in a single in_ fetch.
    device_ids = list({s["device_id"] for s in eligible if s.get("device_id")})
    if not device_ids:
        return {
            "sent": 0,
            "skipped_feedback": skipped_feedback,
            "skipped_no_token": len(eligible),
            "candidates": len(candidate_sessions),
        }

    token_map: Dict[str, str] = {}
    for i in range(0, len(device_ids), 500):
        chunk = device_ids[i : i + 500]
        tk = (
            sb.table("push_tokens")
            .select("device_id,expo_token,active")
            .in_("device_id", chunk)
            .execute()
            .data
            or []
        )
        for row in tk:
            if row.get("active") is False:
                continue
            did = row.get("device_id")
            et = row.get("expo_token")
            if isinstance(did, str) and isinstance(et, str):
                token_map[did] = et

    messages: List[Dict[str, Any]] = []
    skipped_no_token = 0
    for s in eligible:
        did = s.get("device_id") or ""
        token = token_map.get(did)
        if not token:
            skipped_no_token += 1
            continue
        copy = _pick_copy(s.get("locale"))
        messages.append(
            {
                "to": token,
                "sound": "default",
                "title": copy["title"],
                "body": copy["body"],
                "data": {
                    "session_id": s.get("id"),
                    "action": "feedback_prompt",
                },
            }
        )

    sent = 0
    if messages:
        try:
            with httpx.Client(timeout=15) as client:
                for i in range(0, len(messages), 100):
                    batch = messages[i : i + 100]
                    resp = client.post(EXPO_PUSH_URL, json=batch)
                    if resp.status_code < 400:
                        sent += len(batch)
                    else:
                        logger.warning(
                            "Follow-up push batch failed (status=%s): %s",
                            resp.status_code,
                            resp.text[:200],
                        )
        except Exception as exc:
            logger.warning("Follow-up push dispatch failed: %s", exc)

    return {
        "sent": sent,
        "skipped_feedback": skipped_feedback,
        "skipped_no_token": skipped_no_token,
        "candidates": len(candidate_sessions),
    }
