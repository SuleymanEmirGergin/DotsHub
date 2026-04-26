"""POST /v1/quote/itinerary — day-by-day plan generator."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request

from app.idempotency import IDEMPOTENCY_QUOTE_TTL_SEC, IdempotencyHelper
from app.models.schemas import Envelope, ItineraryRequest
from app.services import (
    clinic_registry,
    fit_to_travel,
    itinerary_engine,
    procedure_catalog,
)

from ._shared import (
    ITINERARY_DISCLAIMER_TR,
    bump_itinerary_metric,
    make_meta,
    parse_arrival_date,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _meta_factory():
    return make_meta(ITINERARY_DISCLAIMER_TR)


@router.post("/quote/itinerary", response_model=Envelope)
async def quote_itinerary(http_request: Request, request: ItineraryRequest):
    """Generate a day-by-day itinerary for a chosen procedure + clinic + date.

    Pipeline:
        1. Validate procedure / clinic / date triplet.
        2. Re-run fit-to-travel rules (health may have changed since
           the original quote — block returns EMERGENCY).
        3. Generate the per-category template-based itinerary.
        4. Build ITINERARY envelope.
    """
    session_id = http_request.headers.get("x-session-id") or str(uuid.uuid4())

    idem = IdempotencyHelper(
        http_request, request, _meta_factory, session_id,
        ttl_sec=IDEMPOTENCY_QUOTE_TTL_SEC,
    )
    early = await idem.check()
    if early is not None:
        return early

    # ─── 1. Validate procedure / clinic / date ────────────────────────
    procedure = procedure_catalog.get_procedure(request.procedure_id)
    if procedure is None:
        bump_itinerary_metric("ERROR", None)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "PROCEDURE_UNKNOWN",
                "message_tr": "Bu prosedür kataloğumuzda yok.",
                "procedure_id": request.procedure_id,
                "retryable": False,
            },
            meta=_meta_factory(),
        )
    clinic = clinic_registry.get_clinic(request.clinic_id)
    if clinic is None or request.procedure_id not in clinic.get(
        "procedures_offered", []
    ):
        bump_itinerary_metric("ERROR", procedure)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "CLINIC_PROCEDURE_MISMATCH",
                "message_tr": (
                    "Seçtiğiniz klinik bu prosedürü sunmuyor. Lütfen başka "
                    "bir klinik seçin."
                ),
                "procedure_id": request.procedure_id,
                "clinic_id": request.clinic_id,
                "retryable": True,
            },
            meta=_meta_factory(),
        )
    arrival_date = parse_arrival_date(request.arrival_date)
    if arrival_date is None:
        bump_itinerary_metric("ERROR", procedure)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "ARRIVAL_DATE_INVALID",
                "message_tr": (
                    "Varış tarihi YYYY-MM-DD formatında olmalı (örn. 2026-05-15)."
                ),
                "retryable": False,
            },
            meta=_meta_factory(),
        )

    # ─── 2. Re-run fit-to-travel ─────────────────────────────────────
    warnings = fit_to_travel.evaluate(
        request.profile, request.procedure_id, request.locale
    )
    if fit_to_travel.has_block(warnings):
        first_block = next(w for w in warnings if w.severity == "block")
        bump_itinerary_metric("EMERGENCY", procedure)
        return Envelope(
            type="EMERGENCY",
            session_id=session_id,
            turn_index=0,
            payload={
                "urgency": "ROUTINE_BUT_NOT_TRAVEL_FIT",
                "reason_tr": first_block.reason_tr,
                "instructions_tr": [first_block.recommendation_tr],
                "fit_to_travel_warnings": [w.model_dump() for w in warnings],
                "procedure_id": request.procedure_id,
                "procedure_name_tr": procedure_catalog.name(
                    request.procedure_id, request.locale
                ),
            },
            meta=_meta_factory(),
        )

    # ─── 3. Generate itinerary ────────────────────────────────────────
    itin = itinerary_engine.generate(
        procedure_id=request.procedure_id,
        clinic_id=request.clinic_id,
        arrival_date=arrival_date,
        locale=request.locale,
    )
    if itin is None:
        # Defensive: validation above should make this unreachable, but
        # the engine returning None is a contract we should surface
        # explicitly rather than 500'ing.
        bump_itinerary_metric("ERROR", procedure)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "ITINERARY_GENERATION_FAILED",
                "message_tr": "Plan oluşturulamadı; lütfen tekrar deneyin.",
                "retryable": True,
            },
            meta=_meta_factory(),
        )

    envelope = Envelope(
        type="ITINERARY",
        session_id=session_id,
        turn_index=0,
        payload={
            "procedure_id": itin.procedure_id,
            "procedure_name_tr": itin.procedure_name,
            "clinic_id": itin.clinic_id,
            "clinic_name": itin.clinic_name,
            "clinic_city": itin.clinic_city,
            "arrival_date": itin.arrival_date_iso,
            "departure_date": itin.departure_date_iso,
            "total_days": itin.total_days,
            "items": [item._asdict() for item in itin.items],
            "pre_op_requirements": itin.pre_op_requirements,
            "post_op_no_fly_days": itin.post_op_no_fly_days,
            "post_op_followup_window_days": itin.post_op_followup_window_days,
            "fit_to_travel_warnings": [w.model_dump() for w in warnings],
        },
        meta=_meta_factory(),
    )

    await idem.store(envelope)
    bump_itinerary_metric("ITINERARY", procedure)
    return envelope
