"""
Oturum özeti e-posta isteği.
POST /v1/triage/send-summary: session_id + email ile özet gönderir.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, constr

from app.services.email_summary import send_session_summary_email
from app.services.email_sender_resend import send_via_resend
from app.services.export_summary import build_export_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["Triage"])


class SendSummaryRequest(BaseModel):
    session_id: str
    email: constr(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    locale: str = "tr"  # tr | en | de | ru | ar (de/ru/ar use Turkish content for now)
    device_id: Optional[str] = None  # Session ownership verification (optional for backward compat)


class ExportSummaryRequest(BaseModel):
    """Result payload from triage RESULT envelope (payload field)."""
    payload: dict[str, Any]
    locale: str = "tr-TR"  # tr-TR | en | de | ru | ar (de/ru/ar use Turkish content for now)


def _get_session_by_id(session_id: str) -> dict[str, Any] | None:
    """Session'ı DB'den döndürür. Önce triage_sessions_v5, yoksa triage_sessions dener."""
    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        if sb is None:
            return None
        for table in ("triage_sessions_v5", "triage_sessions"):
            try:
                r = sb.table(table).select("*").eq("id", session_id).limit(1).execute()
                if r.data and len(r.data) > 0:
                    return dict(r.data[0])
            except Exception:
                continue
    except Exception as e:
        logger.warning("summary_email.get_session_error", extra={"session_id": session_id, "error": str(e)})
    return None


def _get_sender():
    """SEND_SUMMARY_EMAIL=1 ve RESEND_API_KEY varsa Resend kullanır."""
    if os.environ.get("SEND_SUMMARY_EMAIL", "").strip() != "1":
        return None
    if os.environ.get("RESEND_API_KEY", "").strip():
        return lambda to, subj, text, html: send_via_resend(to, subj, text, html)
    return None


def _content_locale(locale: str) -> str:
    """Normalize locale for email/export content: en -> en, else (tr, de, ru, ar) -> tr."""
    if (locale or "").strip().lower() == "en":
        return "en"
    return "tr"


@router.post("/send-summary")
async def send_summary(body: SendSummaryRequest) -> dict[str, str]:
    """
    Oturum özetini verilen e-posta adresine gönderir.
    session_id: triage_sessions_v5 tablosundaki oturum ID'si.
    email: Gönderilecek adres.
    locale: tr | en | de | ru | ar (de/ru/ar için e-posta içeriği Türkçe).
    """
    if not body.session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    session = _get_session_by_id(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Device ownership check: if both request and session have device_id,
    # they must match. Missing device_id on either side → allow (backward compat).
    stored_device_id = session.get("device_id")
    if stored_device_id and body.device_id and stored_device_id != body.device_id:
        raise HTTPException(status_code=403, detail="session_id does not belong to this device")

    sender = _get_sender()
    content_locale = _content_locale(body.locale)
    try:
        send_session_summary_email(
            body.email,
            session,
            locale=content_locale,
            sender=sender,
        )
    except Exception as exc:
        logger.error("send_summary.email_failed session=%s err=%s", body.session_id, exc)
        raise HTTPException(status_code=500, detail="email_send_failed")

    return {"status": "ok", "message": "Summary email sent or queued"}


@router.post("/export-summary", response_class=PlainTextResponse)
def export_summary_text(body: ExportSummaryRequest) -> str:
    """
    Oturum sonucunu yapılandırılmış metin olarak döndürür.
    İstek gövdesi: triage turn RESULT cevabındaki payload + locale.
    locale: tr-TR | en | de | ru | ar (de/ru/ar için metin Türkçe).
    İndirilebilir .txt veya e-posta ile uyumludur.
    """
    content_locale = "en" if (body.locale or "").strip().lower().startswith("en") else "tr-TR"
    return build_export_text(body.payload, locale=content_locale)
