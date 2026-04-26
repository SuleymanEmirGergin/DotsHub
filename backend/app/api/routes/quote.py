"""POST /v1/quote — Health-tourism quote endpoint.

Pipeline
    1. Resolve procedure_id (explicit body field, or extracted from
       free-text via procedure_intent).
    2. Run fit-to-travel rules against the patient profile + procedure.
    3. If any rule with severity 'block' triggers, return an
       EMERGENCY-style envelope; the patient should seek local care
       first. We DO NOT return a quote — that would put commercial
       above clinical.
    4. Otherwise rank clinics for the procedure (quote_engine) and
       return a QUOTE envelope. ``warn``-severity rules ride along on
       the payload so the UI can surface them next to the quote.

Disclaimer pattern matches the existing /v1/triage/turn endpoint:
quote prices are non-binding indicative bands, every payload includes
the standard disclaimer + medical-tourism specific copy.

Idempotency
    Same `Idempotency-Key` mechanism as /v1/triage/turn — quote
    generation is a pure function of (procedure_id, profile,
    target_city, locale, top_n), so caching the response under a
    client-supplied key is safe and prevents accidental double-quotes
    on flaky retries.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request

from app.idempotency import (
    IdempotencyMismatch,
    compute_body_hash,
    lookup_cached,
    store_response,
)
from app.models.schemas import (
    Envelope,
    Meta,
    QuoteRequest,
)
from app.services import (
    fit_to_travel,
    procedure_catalog,
    procedure_intent,
    quote_engine,
)

logger = logging.getLogger(__name__)
router = APIRouter()


_QUOTE_DISCLAIMER_TR = (
    "Bu fiyatlar bağlayıcı değildir; klinik onayı, ön muayene ve nihai "
    "tedavi planı sonrası kesinleşir. Sağlık turizmi aracılık hizmetidir, "
    "tıbbi tavsiye değildir."
)


def _make_meta() -> Meta:
    return Meta(
        disclaimer_tr=_QUOTE_DISCLAIMER_TR,
        timestamp=datetime.now(timezone.utc),
    )


def _resolve_procedure_id(req: QuoteRequest) -> Optional[tuple[str, dict]]:
    """Pick the procedure id. Explicit > extracted from user_message.

    Returns ``(procedure_id, debug_info)`` so the route can include
    extraction confidence in the response meta — useful for the UI to
    decide whether to ask "Did you mean X?" instead of jumping
    straight to a quote.
    """
    if req.procedure_id:
        if req.procedure_id in procedure_catalog.procedure_ids():
            return req.procedure_id, {"resolved_via": "explicit"}
        return None
    if req.user_message:
        match = procedure_intent.extract(req.user_message, req.locale)
        if match is not None:
            return match.procedure_id, {
                "resolved_via": "intent",
                "confidence_0_1": match.confidence_0_1,
                "matched_synonyms": match.matched_synonyms,
            }
    return None


@router.post("/quote", response_model=Envelope)
async def quote(http_request: Request, request: QuoteRequest):
    """Generate a non-binding quote for a health-tourism procedure."""
    session_id = http_request.headers.get("x-session-id") or str(uuid.uuid4())

    # ─── Idempotency check (mirrors /v1/triage/turn pattern) ───
    idempotency_key = http_request.headers.get("idempotency-key")
    body_hash: Optional[str] = None
    redis_client = getattr(http_request.app.state, "redis", None)
    if idempotency_key:
        try:
            body_hash = compute_body_hash(request.model_dump(mode="json"))
            cached = await lookup_cached(redis_client, idempotency_key, body_hash)
            if cached is not None:
                return Envelope.model_validate(cached)
        except IdempotencyMismatch:
            return Envelope(
                type="ERROR",
                session_id=session_id,
                turn_index=0,
                payload={
                    "code": "IDEMPOTENCY_KEY_REUSED",
                    "message_tr": (
                        "Idempotency-Key aynı ama istek gövdesi farklı."
                    ),
                    "retryable": False,
                },
                meta=_make_meta(),
            )
        except Exception as exc:
            logger.warning(
                "quote.idempotency_lookup_failed: %s; proceeding without cache",
                exc,
            )
            body_hash = None

    # ─── 1. Resolve procedure_id ─────────────────────────────────────
    resolved = _resolve_procedure_id(request)
    if resolved is None:
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
            meta=_make_meta(),
        )
    procedure_id, intent_debug = resolved
    procedure = procedure_catalog.get_procedure(procedure_id)
    assert procedure is not None  # _resolve_procedure_id guarantees existence

    # ─── 2. Fit-to-travel evaluation ─────────────────────────────────
    warnings = fit_to_travel.evaluate(
        request.profile, procedure_id, request.locale
    )
    if fit_to_travel.has_block(warnings):
        # 'Block' rules return EMERGENCY-style envelope. The first
        # rule's reason carries primary copy; remaining warnings ride
        # in the payload so the UI can list them.
        first_block = next(w for w in warnings if w.severity == "block")
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
            meta=_make_meta(),
        )

    # ─── 3. Rank clinics ─────────────────────────────────────────────
    clinics = quote_engine.rank_clinics(
        procedure_id=procedure_id,
        locale=request.locale,
        target_city=request.target_city,
        top_n=request.top_n,
    )
    if not clinics:
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
            meta=_make_meta(),
        )

    # ─── 4. Build QUOTE envelope ─────────────────────────────────────
    envelope = Envelope(
        type="QUOTE",
        session_id=session_id,
        turn_index=0,
        payload={
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
        meta=_make_meta(),
    )

    # ─── 5. Cache for idempotency ────────────────────────────────────
    if idempotency_key and body_hash is not None:
        try:
            await store_response(
                redis_client,
                idempotency_key,
                body_hash,
                envelope.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.warning(
                "quote.idempotency_store_failed: %s", exc
            )

    return envelope
