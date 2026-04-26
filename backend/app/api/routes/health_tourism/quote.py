"""POST /v1/quote — health-tourism quote generation."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request

from app.idempotency import IDEMPOTENCY_QUOTE_TTL_SEC, IdempotencyHelper
from app.models.schemas import Envelope, QuoteRequest
from app.services import (
    fit_to_travel,
    procedure_catalog,
    quote_engine,
)

from ._shared import (
    QUOTE_DISCLAIMER_TR,
    bump_quote_metric,
    make_meta,
    resolve_procedure_id,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _meta_factory():
    return make_meta(QUOTE_DISCLAIMER_TR)


@router.post("/quote", response_model=Envelope)
async def quote(http_request: Request, request: QuoteRequest):
    """Generate a non-binding quote for a health-tourism procedure.

    Pipeline:
        1. Resolve procedure_id (explicit, deterministic, or LLM-fallback).
        2. Run fit-to-travel rules; ``block`` → EMERGENCY envelope.
        3. Rank clinics; empty → NO_PARTNER_CLINIC error.
        4. Build QUOTE envelope with quote_id (UUID — operator audit handle).

    Idempotency: same retry-safety contract as /v1/triage/turn — caller
    sends `Idempotency-Key`, retry returns the cached envelope.
    """
    session_id = http_request.headers.get("x-session-id") or str(uuid.uuid4())

    # 15-min TTL — users read a quote, deliberate, then accept; the
    # 5-min default would expire under them. Engine is cheap to re-run,
    # but the longer cache prevents accidental double-quotes.
    idem = IdempotencyHelper(
        http_request, request, _meta_factory, session_id,
        ttl_sec=IDEMPOTENCY_QUOTE_TTL_SEC,
    )
    early = await idem.check()
    if early is not None:
        return early

    # ─── 1. Resolve procedure_id ─────────────────────────────────────
    resolved = resolve_procedure_id(request)
    if resolved is None:
        bump_quote_metric("ERROR", None)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "PROCEDURE_UNRESOLVED",
                "message_tr": (
                    "Hangi işlem için teklif istediğinizi anlayamadık. "
                    "Lütfen procedure_id alanını belirtin veya işlemi daha "
                    "açık tarif edin."
                ),
                "retryable": True,
            },
            meta=_meta_factory(),
        )
    procedure_id, intent_debug = resolved
    procedure = procedure_catalog.get_procedure(procedure_id)
    assert procedure is not None  # resolve_procedure_id guarantees existence

    # ─── 2. Fit-to-travel evaluation ─────────────────────────────────
    warnings = fit_to_travel.evaluate(
        request.profile, procedure_id, request.locale
    )
    if fit_to_travel.has_block(warnings):
        first_block = next(w for w in warnings if w.severity == "block")
        bump_quote_metric("EMERGENCY", procedure)
        return Envelope(
            type="EMERGENCY",
            session_id=session_id,
            turn_index=0,
            payload={
                "urgency": "ROUTINE_BUT_NOT_TRAVEL_FIT",
                "reason_tr": first_block.reason_tr,
                "instructions_tr": [first_block.recommendation_tr],
                "fit_to_travel_warnings": [w.model_dump() for w in warnings],
                "procedure_id": procedure_id,
                "procedure_name_tr": procedure_catalog.name(
                    procedure_id, request.locale
                ),
            },
            meta=_meta_factory(),
        )

    # ─── 3. Rank clinics ─────────────────────────────────────────────
    clinics = quote_engine.rank_clinics(
        procedure_id=procedure_id,
        locale=request.locale,
        target_city=request.target_city,
        top_n=request.top_n,
    )
    if not clinics:
        bump_quote_metric("ERROR", procedure)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "NO_PARTNER_CLINIC",
                "message_tr": (
                    "Bu işlem için şu an anlaşmalı klinik bulunamadı. "
                    "Lütfen daha sonra tekrar deneyin veya farklı bir işlem seçin."
                ),
                "procedure_id": procedure_id,
                "retryable": True,
            },
            meta=_meta_factory(),
        )

    # ─── 4. Build QUOTE envelope ─────────────────────────────────────
    # quote_id is a UUID stamped at response time. Clients pass it
    # back in /v1/quote/lead so the operator can trace which exact
    # price/clinic combination the patient is accepting. Not currently
    # persisted server-side — the QUOTE itself is a pure function of
    # (procedure_id, profile, target_city, locale, top_n), so we don't
    # need a database round-trip; the id is the audit handle.
    quote_id = str(uuid.uuid4())
    envelope = Envelope(
        type="QUOTE",
        session_id=session_id,
        turn_index=0,
        payload={
            "quote_id": quote_id,
            "procedure": {
                "id": procedure_id,
                "name_tr": procedure_catalog.name(procedure_id, request.locale),
                "category": procedure.get("category"),
                "duration_days": procedure.get("duration_days"),
                "post_op_no_fly_days": procedure.get("post_op_no_fly_days"),
                "anesthesia": procedure.get("anesthesia"),
                "complexity": procedure.get("complexity"),
            },
            "clinics": [c.model_dump() for c in clinics],
            "fit_to_travel_warnings": [w.model_dump() for w in warnings],
            "intent_resolution": intent_debug,
            "currency": "EUR",
        },
        meta=_meta_factory(),
    )

    await idem.store(envelope)
    bump_quote_metric("QUOTE", procedure)
    return envelope
