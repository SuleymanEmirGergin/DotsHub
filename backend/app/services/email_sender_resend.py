"""
Resend API ile e-posta gönderimi (opsiyonel).
RESEND_API_KEY ve RESEND_FROM ayarlanırsa kullanılır.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def send_via_resend(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    """Resend API ile tek e-posta gönderir. API key yoksa log atıp çıkar."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_addr = os.environ.get("RESEND_FROM", "").strip() or "onboarding@resend.dev"

    if not api_key:
        logger.warning("RESEND_API_KEY not set; skipping send")
        return

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; cannot send via Resend")
        return

    payload = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "text": body_text,
    }
    if body_html:
        payload["html"] = body_html

    with httpx.Client() as client:
        r = client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
    if r.is_success:
        logger.info("email_summary.sent", extra={"to": to[:3] + "***"})
    else:
        logger.warning("email_summary.send_failed", extra={"status": r.status_code, "body": r.text[:200]})
