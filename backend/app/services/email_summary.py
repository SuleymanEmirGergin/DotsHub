"""
Oturum özeti e-posta servisi.
Session verisinden metin/HTML üretir ve yapılandırılmış gönderici ile e-posta atar.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    """E-posta göndermek için kullanılan arayüz."""

    def send(self, to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
        ...


def _default_sender(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    """Varsayılan: sadece loglar. Gerçek gönderim için SMTP/Resend vb. bağlanmalı."""
    logger.info(
        "email_summary.skip",
        extra={"to": to[:3] + "***", "subject": subject, "reason": "no sender configured"},
    )


def build_summary_body(session: dict[str, Any], locale: str = "tr") -> tuple[str, str]:
    """
    Session sözlüğünden düz metin ve HTML özet üretir.
    session: en az recommended_specialty_tr, confidence_label_tr, stop_reason, id, created_at vb. içerebilir.
    Returns: (body_text, body_html)
    """
    sid = session.get("id", "")
    specialty = session.get("recommended_specialty_tr") or session.get("recommended_specialty") or "-"
    confidence = session.get("confidence_label_tr") or session.get("confidence") or "-"
    stop_reason = session.get("stop_reason") or "-"
    created = session.get("created_at", "")

    if locale == "en":
        title = "Pre-Triage session summary"
        lines = [
            f"Session ID: {sid}",
            f"Created: {created}",
            f"Recommended specialty: {specialty}",
            f"Confidence: {confidence}",
            f"Stop reason: {stop_reason}",
        ]
    else:
        title = "Ön Triage oturum özeti"
        lines = [
            f"Oturum ID: {sid}",
            f"Oluşturulma: {created}",
            f"Önerilen branş: {specialty}",
            f"Güven: {confidence}",
            f"Durdurma nedeni: {stop_reason}",
        ]

    body_text = title + "\n\n" + "\n".join(lines)
    body_html = f"<h2>{title}</h2><pre>{body_text}</pre>"
    return body_text, body_html


def send_session_summary_email(
    to: str,
    session: dict[str, Any],
    *,
    locale: str = "tr",
    sender: EmailSender | Callable[..., None] | None = None,
) -> None:
    """
    Oturum özetini verilen adrese gönderir.
    sender None ise veya SEND_SUMMARY_EMAIL != 1 ise sadece log atar.
    """
    if os.environ.get("SEND_SUMMARY_EMAIL", "").strip() != "1":
        _default_sender(to, "(summary skipped)", "", None)
        return

    body_text, body_html = build_summary_body(session, locale=locale)
    subject = "Ön Triage – Oturum özeti" if locale == "tr" else "Pre-Triage – Session summary"

    if sender is None:
        sender = _default_sender
    if callable(sender) and not hasattr(sender, "send"):
        sender(to, subject, body_text, body_html)
    else:
        (sender.send)(to, subject, body_text, body_html)
