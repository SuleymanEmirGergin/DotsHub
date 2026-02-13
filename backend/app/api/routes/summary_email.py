"""
Oturum özeti e-posta isteği.
POST /v1/triage/send-summary: session_id + email ile özet gönderir.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.services.email_summary import send_session_summary_email
from app.services.email_sender_resend import send_via_resend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["Triage"])


class SendSummaryRequest(BaseModel):
    session_id: str
    email: EmailStr
    locale: str = "tr"


def _get_session_by_id(session_id: str) -> dict[str, Any] | None:
    """Session'ı DB'den veya cache'den döndürür. Bu projede Supabase kullanılıyor."""
    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        if sb is None:
            return None
        r = sb.table("triage_sessions_v5").select("*").eq("id", session_id).limit(1).execute()
        if r.data and len(r.data) > 0:
            return dict(r.data[0])
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


@router.post("/send-summary")
async def send_summary(body: SendSummaryRequest) -> dict[str, str]:
    """
    Oturum özetini verilen e-posta adresine gönderir.
    session_id: triage_sessions_v5 tablosundaki oturum ID'si.
    email: Gönderilecek adres.
    locale: tr | en
    """
    if not body.session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    session = _get_session_by_id(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sender = _get_sender()
    send_session_summary_email(
        body.email,
        session,
        locale=body.locale,
        sender=sender,
    )

    return {"status": "ok", "message": "Summary email sent or queued"}
