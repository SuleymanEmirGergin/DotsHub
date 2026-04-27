"""POST /v1/quote/lead — patient accepts a quote, lead routed to CRM."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Request

from app.idempotency import IDEMPOTENCY_QUOTE_TTL_SEC, IdempotencyHelper
from app.models.schemas import Envelope, LeadRequest
from app.services import (
    clinic_registry,
    lead_dispatcher,
    lead_repository,
    procedure_catalog,
)

from ._shared import (
    LEAD_DISCLAIMER_NO_CONSENT_TR,
    LEAD_DISCLAIMER_TR,
    bump_lead_metric,
    dispatch_and_record,
    make_meta,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _meta_factory():
    return make_meta(LEAD_DISCLAIMER_TR)


@router.post("/quote/lead", response_model=Envelope)
async def quote_lead(
    http_request: Request,
    request: LeadRequest,
    background_tasks: BackgroundTasks,
):
    """Accept a quote, schedule the webhook in the background.

    Returns a RESULT envelope with code ``LEAD_ACCEPTED`` immediately
    after persisting the lead row. The actual webhook dispatch runs
    via FastAPI's BackgroundTasks AFTER the response is sent — a slow
    CRM no longer adds seconds to user-facing latency. The eventual
    delivery outcome lands on the DB row's ``webhook_status`` column,
    queryable by the operator.

    Response payload's ``webhook_status`` is one of:
      - "scheduled" — webhook configured, dispatch deferred
      - "not_configured" — no webhook URL, nothing to dispatch

    Idempotency: a retry with the same key returns the cached
    "scheduled" envelope. Critical here — without it, two retries
    would write two DB rows AND fire two webhooks, producing
    duplicate leads in the operator's CRM.
    """
    session_id = http_request.headers.get("x-session-id") or str(uuid.uuid4())
    lead_id = str(uuid.uuid4())

    idem = IdempotencyHelper(
        http_request, request, _meta_factory, session_id,
        ttl_sec=IDEMPOTENCY_QUOTE_TTL_SEC,
    )
    early = await idem.check()
    if early is not None:
        return early

    procedure = procedure_catalog.get_procedure(request.procedure_id)
    clinic = clinic_registry.get_clinic(request.clinic_id)
    if procedure is None or clinic is None or request.procedure_id not in clinic.get(
        "procedures_offered", []
    ):
        bump_lead_metric("rejected_mismatch", request.consent_to_share)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "CLINIC_PROCEDURE_MISMATCH",
                "message_tr": "Seçtiğiniz klinik bu prosedürü sunmuyor.",
                "procedure_id": request.procedure_id,
                "clinic_id": request.clinic_id,
                "retryable": True,
            },
            meta=_meta_factory(),
        )

    quoted_price = None
    base = (procedure.get("price_band_eur") or {}).get("mid")
    if base is not None:
        quoted_price = int(round(base * float(clinic.get("price_modifier", 1.0))))

    # ─── Persist BEFORE dispatching ───────────────────────────────────
    persisted = lead_repository.insert(
        lead_id=lead_id,
        session_id=session_id,
        quote_id=request.quote_id,
        procedure_id=request.procedure_id,
        clinic_id=request.clinic_id,
        consent_to_share=request.consent_to_share,
        contact=request.contact.model_dump(),
        notes=request.notes,
        locale=request.locale,
        quoted_price_eur=quoted_price,
    )

    payload = lead_dispatcher.build_payload(
        lead_id=lead_id,
        session_id=session_id,
        procedure=procedure,
        clinic=clinic,
        contact=request.contact.model_dump(),
        consent_to_share=request.consent_to_share,
        locale=request.locale,
        notes=request.notes,
        quoted_price_eur=quoted_price,
    )
    if request.quote_id:
        payload["quote_id"] = request.quote_id

    # ─── Schedule webhook (async, after response) ────────────────────
    if lead_dispatcher.is_configured():
        background_tasks.add_task(
            dispatch_and_record,
            lead_id=lead_id,
            payload=payload,
            persisted=persisted,
            consent_to_share=request.consent_to_share,
        )
        webhook_status = "scheduled"
    else:
        webhook_status = "not_configured"
        if persisted:
            lead_repository.record_outcome(lead_id, "not_configured")
        bump_lead_metric("not_configured", request.consent_to_share)

    envelope = Envelope(
        type="RESULT",
        session_id=session_id,
        turn_index=0,
        payload={
            "code": "LEAD_ACCEPTED",
            "lead_id": lead_id,
            "quote_id": request.quote_id,
            "consent_to_share": bool(request.consent_to_share),
            "webhook_status": webhook_status,
            "webhook_configured": lead_dispatcher.is_configured(),
            "persisted": persisted,
            "next_steps_tr": (
                "Klinik temsilcisi 24 saat içinde sizinle iletişime geçecektir."
                if request.consent_to_share
                else LEAD_DISCLAIMER_NO_CONSENT_TR
            ),
            "procedure_id": request.procedure_id,
            "procedure_name_tr": procedure_catalog.name(
                request.procedure_id, request.locale
            ),
            "clinic_id": request.clinic_id,
            "clinic_name": clinic["name"],
            "quoted_price_eur": quoted_price,
        },
        meta=_meta_factory(),
    )
    await idem.store(envelope)
    return envelope
