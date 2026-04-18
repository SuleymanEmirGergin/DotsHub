"""Webhook notifier — fire-and-forget alerts to Slack / Discord.

Sends rich notifications when:
  - EMERGENCY envelope is produced
  - RESULT envelope with HIGH risk level

Non-blocking: dispatches in a background thread.
Never raises — triage must never fail due to notifications.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Public API ──────────────────────────────────────────────


def send_llm_health_alert(
    success_rate_pct: float,
    window_size: int,
    top_error: Optional[str],
    threshold_pct: float,
) -> None:
    """Fire a Slack/Discord alert when LLM NLU success rate drops.

    Called from llm_nlu._check_health_and_maybe_alert() after a
    rolling window reports success_rate below
    settings.LLM_HEALTH_ALERT_THRESHOLD_PCT. This surface is the
    paging sibling of the B2 dashboard LLM Health card — the
    dashboard is passive (requires someone to look), the webhook is
    active (pushes). Same data source (llm_calls via the in-memory
    ring buffer in llm_nlu.py).

    Cool-down is owned by the caller to keep this function stateless.
    Never raises.
    """
    if not settings.WEBHOOK_ENABLED:
        return
    if not settings.WEBHOOK_SLACK_URL and not settings.WEBHOOK_DISCORD_URL:
        return

    thread = threading.Thread(
        target=_dispatch_llm_health,
        args=(success_rate_pct, window_size, top_error, threshold_pct),
        daemon=True,
    )
    thread.start()


def send_alert(
    envelope_type: str,
    session_id: str,
    payload: Dict[str, Any],
    risk_level: Optional[str] = None,
) -> None:
    """Fire webhook alert in background thread. Never blocks triage flow."""
    if not settings.WEBHOOK_ENABLED:
        return

    has_slack = bool(settings.WEBHOOK_SLACK_URL)
    has_discord = bool(settings.WEBHOOK_DISCORD_URL)

    if not has_slack and not has_discord:
        return

    # Only alert on EMERGENCY or HIGH risk RESULT
    should_alert = (
        envelope_type == "EMERGENCY"
        or (envelope_type == "RESULT" and risk_level == "HIGH")
    )
    if not should_alert:
        return

    thread = threading.Thread(
        target=_dispatch,
        args=(envelope_type, session_id, payload, risk_level),
        daemon=True,
    )
    thread.start()


# ── Internal ────────────────────────────────────────────────


def _dispatch(
    envelope_type: str,
    session_id: str,
    payload: Dict[str, Any],
    risk_level: Optional[str],
) -> None:
    """Send to all configured channels (runs in background thread)."""
    try:
        if settings.WEBHOOK_SLACK_URL:
            _send_slack(envelope_type, session_id, payload, risk_level)
    except Exception as exc:
        logger.warning("Slack webhook failed: %s", exc)

    try:
        if settings.WEBHOOK_DISCORD_URL:
            _send_discord(envelope_type, session_id, payload, risk_level)
    except Exception as exc:
        logger.warning("Discord webhook failed: %s", exc)


def _extract_info(
    envelope_type: str,
    payload: Dict[str, Any],
    risk_level: Optional[str],
) -> Dict[str, str]:
    """Extract display info from envelope payload."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if envelope_type == "EMERGENCY":
        reason = payload.get("reason_tr", "Bilinmeyen acil durum")
        instructions = payload.get("instructions_tr", [])
        return {
            "title": "🚨 ACİL DURUM TESPİT EDİLDİ",
            "color": "#C62828",
            "reason": reason,
            "instructions": " | ".join(instructions) if instructions else "-",
            "specialty": "-",
            "confidence": "-",
            "risk": "EMERGENCY",
            "timestamp": now,
        }

    # RESULT with HIGH risk
    spec = payload.get("recommended_specialty", {})
    spec_name = spec.get("name_tr", "?") if isinstance(spec, dict) else str(spec)
    conf = payload.get("confidence_0_1")
    conf_str = f"{round(float(conf) * 100)}%" if conf is not None else "?"
    stop = payload.get("stop_reason", "?")

    return {
        "title": "⚠️ YÜKSEK RİSK — Sonuç Üretildi",
        "color": "#F57F17",
        "reason": f"Risk seviyesi: {risk_level}",
        "instructions": f"Stop: {stop}",
        "specialty": spec_name,
        "confidence": conf_str,
        "risk": risk_level or "HIGH",
        "timestamp": now,
    }


# ── Slack (Block Kit) ───────────────────────────────────────


def _send_slack(
    envelope_type: str,
    session_id: str,
    payload: Dict[str, Any],
    risk_level: Optional[str],
) -> None:
    info = _extract_info(envelope_type, payload, risk_level)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": info["title"], "emoji": True},
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Oturum:*\n`{session_id[:8]}…`"},
                {"type": "mrkdwn", "text": f"*Risk:*\n{info['risk']}"},
                {"type": "mrkdwn", "text": f"*Uzmanlık:*\n{info['specialty']}"},
                {"type": "mrkdwn", "text": f"*Güven:*\n{info['confidence']}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"📝 *Sebep:* {info['reason']}"},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"🕐 {info['timestamp']} | DotsHub Triage Alert"},
            ],
        },
    ]

    body = {"blocks": blocks, "text": info["title"]}

    with httpx.Client(timeout=10) as client:
        resp = client.post(settings.WEBHOOK_SLACK_URL, json=body)
        if resp.status_code >= 400:
            logger.warning("Slack returned %s: %s", resp.status_code, resp.text[:200])


# ── Discord (Embed) ─────────────────────────────────────────


def _send_discord(
    envelope_type: str,
    session_id: str,
    payload: Dict[str, Any],
    risk_level: Optional[str],
) -> None:
    info = _extract_info(envelope_type, payload, risk_level)

    # Discord color as int
    color_hex = info["color"].lstrip("#")
    color_int = int(color_hex, 16)

    embed = {
        "title": info["title"],
        "color": color_int,
        "fields": [
            {"name": "Oturum", "value": f"`{session_id[:8]}…`", "inline": True},
            {"name": "Risk", "value": info["risk"], "inline": True},
            {"name": "Uzmanlık", "value": info["specialty"], "inline": True},
            {"name": "Güven", "value": info["confidence"], "inline": True},
            {"name": "Sebep", "value": info["reason"], "inline": False},
        ],
        "footer": {"text": f"DotsHub Triage Alert • {info['timestamp']}"},
    }

    body = {"embeds": [embed], "content": info["title"]}

    with httpx.Client(timeout=10) as client:
        resp = client.post(settings.WEBHOOK_DISCORD_URL, json=body)
        if resp.status_code >= 400:
            logger.warning("Discord returned %s: %s", resp.status_code, resp.text[:200])


# ── LLM health dispatcher ──────────────────────────────────


def _dispatch_llm_health(
    success_rate_pct: float,
    window_size: int,
    top_error: Optional[str],
    threshold_pct: float,
) -> None:
    """Background thread target for send_llm_health_alert."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = f"⚠️ LLM NLU başarı oranı düştü: %{success_rate_pct:.0f}"
    error_line = f"En sık hata: `{top_error}`" if top_error else "Hata türü: (N/A)"

    if settings.WEBHOOK_SLACK_URL:
        try:
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "divider"},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Son {window_size} çağrı*"},
                        {"type": "mrkdwn", "text": f"*Eşik:* %{threshold_pct:.0f}"},
                        {"type": "mrkdwn", "text": f"*Gerçekleşen:* %{success_rate_pct:.1f}"},
                        {"type": "mrkdwn", "text": f"*Zaman:* {now}"},
                    ],
                },
                {"type": "section", "text": {"type": "mrkdwn", "text": error_line}},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "💡 Admin → Analytics → LLM NLU Health kartında detay.",
                        }
                    ],
                },
            ]
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    settings.WEBHOOK_SLACK_URL, json={"blocks": blocks, "text": title}
                )
                if resp.status_code >= 400:
                    logger.warning(
                        "Slack LLM health webhook: %s — %s",
                        resp.status_code,
                        resp.text[:200],
                    )
        except Exception as exc:
            logger.warning("Slack LLM health webhook failed: %s", exc)

    if settings.WEBHOOK_DISCORD_URL:
        try:
            embed = {
                "title": title,
                "color": 0xF57F17,
                "fields": [
                    {"name": "Son", "value": f"{window_size} çağrı", "inline": True},
                    {"name": "Eşik", "value": f"%{threshold_pct:.0f}", "inline": True},
                    {"name": "Gerçekleşen", "value": f"%{success_rate_pct:.1f}", "inline": True},
                    {"name": "En sık hata", "value": (top_error or "-"), "inline": False},
                ],
                "footer": {"text": f"DotsHub LLM Health • {now}"},
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    settings.WEBHOOK_DISCORD_URL,
                    json={"embeds": [embed], "content": title},
                )
                if resp.status_code >= 400:
                    logger.warning(
                        "Discord LLM health webhook: %s — %s",
                        resp.status_code,
                        resp.text[:200],
                    )
        except Exception as exc:
            logger.warning("Discord LLM health webhook failed: %s", exc)


# ── Test helper (synchronous) ──────────────────────────────


def send_test() -> Dict[str, Any]:
    """Send a test message to all configured channels. Returns results dict."""
    results: Dict[str, Any] = {"slack": None, "discord": None}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if settings.WEBHOOK_SLACK_URL:
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "✅ DotsHub Test Mesajı", "emoji": True},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"Webhook bağlantısı başarılı!\n🕐 {now}"},
                },
            ]
            with httpx.Client(timeout=10) as client:
                resp = client.post(settings.WEBHOOK_SLACK_URL, json={"blocks": blocks, "text": "DotsHub test"})
                results["slack"] = {"ok": resp.status_code < 400, "status": resp.status_code}
        except Exception as exc:
            results["slack"] = {"ok": False, "error": str(exc)}

    if settings.WEBHOOK_DISCORD_URL:
        try:
            embed = {
                "title": "✅ DotsHub Test Mesajı",
                "color": 0x10B981,
                "description": "Webhook bağlantısı başarılı!",
                "footer": {"text": f"DotsHub Test • {now}"},
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(settings.WEBHOOK_DISCORD_URL, json={"embeds": [embed], "content": "DotsHub test"})
                results["discord"] = {"ok": resp.status_code < 400, "status": resp.status_code}
        except Exception as exc:
            results["discord"] = {"ok": False, "error": str(exc)}

    return results
