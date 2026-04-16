"""Push notification sender — Expo Push API.

Sends push notifications when EMERGENCY or HIGH-risk RESULT envelopes are produced.
Works alongside webhook notifications (notifier.py).
"""

import logging
import threading
from typing import Any, Dict, List, Optional

import httpx

from app.db import supabase

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
