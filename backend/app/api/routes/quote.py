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
from datetime import date, datetime, timezone
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
    ItineraryRequest,
    LeadRequest,
    Meta,
    QuoteRequest,
)
from app.observability import (
    itinerary_total,
    lead_total,
    procedure_intent_outcome_total,
    quote_total,
)
from app.services import (
    clinic_registry,
    fit_to_travel,
    itinerary_engine,
    lead_dispatcher,
    lead_repository,
    procedure_catalog,
    procedure_intent,
    procedure_intent_llm,
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


# ─── Counter helpers (single bump-site per envelope creation) ────────


def _bump_quote_metric(envelope_type: str, procedure: Optional[dict]) -> None:
    """Single counter-bump entry point so every quote() return path
    records its outcome consistently. Procedure category is bounded
    by the JSON catalog (8 distinct values + "unknown")."""
    category = (procedure or {}).get("category") or "unknown"
    quote_total.labels(outcome=envelope_type, procedure_category=category).inc()


def _bump_itinerary_metric(envelope_type: str, procedure: Optional[dict]) -> None:
    category = (procedure or {}).get("category") or "unknown"
    itinerary_total.labels(
        outcome=envelope_type, procedure_category=category
    ).inc()


def _bump_lead_metric(webhook_status: str, consent_to_share: bool) -> None:
    lead_total.labels(
        webhook_status=webhook_status,
        consent_to_share="true" if consent_to_share else "false",
    ).inc()


def _resolve_procedure_id(req: QuoteRequest) -> Optional[tuple[str, dict]]:
    """Pick the procedure id. Explicit > deterministic intent > LLM intent.

    Returns ``(procedure_id, debug_info)`` so the route can include
    extraction confidence in the response meta — useful for the UI to
    decide whether to ask "Did you mean X?" instead of jumping
    straight to a quote.

    Resolution order:
      1. Explicit ``procedure_id`` field (no extraction).
      2. Deterministic synonym match (fast, free, audit-friendly).
      3. LLM fallback — only when the synonym matcher is uncertain
         AND the feature flag is on. See ``procedure_intent_llm`` for
         the cost/confidence rationale.
    """
    if req.procedure_id:
        if req.procedure_id in procedure_catalog.procedure_ids():
            procedure_intent_outcome_total.labels(resolved_via="explicit").inc()
            return req.procedure_id, {"resolved_via": "explicit"}
        # Explicit but unknown — counts as unresolved.
        procedure_intent_outcome_total.labels(resolved_via="unresolved").inc()
        return None
    if not req.user_message:
        procedure_intent_outcome_total.labels(resolved_via="unresolved").inc()
        return None

    # Step 2: deterministic.
    match = procedure_intent.extract(req.user_message, req.locale)
    if match is not None and not procedure_intent_llm.should_fallback(match):
        procedure_intent_outcome_total.labels(resolved_via="intent").inc()
        return match.procedure_id, {
            "resolved_via": "intent",
            "confidence_0_1": match.confidence_0_1,
            "matched_synonyms": match.matched_synonyms,
        }

    # Step 3: LLM fallback — only fires when the deterministic pass
    # was uncertain AND the operator has flipped the feature flag.
    # Failures here return None and let the caller surface
    # PROCEDURE_UNRESOLVED — the LLM is a quality nudge, not a hard
    # dependency.
    if procedure_intent_llm.should_fallback(match):
        llm_match = procedure_intent_llm.extract_via_llm(
            req.user_message, req.locale
        )
        if llm_match is not None:
            procedure_intent_outcome_total.labels(resolved_via="llm_intent").inc()
            return llm_match.procedure_id, {
                "resolved_via": "llm_intent",
                "confidence_0_1": llm_match.confidence_0_1,
                "deterministic_confidence_0_1": (
                    match.confidence_0_1 if match else 0.0
                ),
                "matched_synonyms": llm_match.matched_synonyms,
            }

    # Deterministic match exists but below threshold + LLM disabled or
    # also failed → still return the deterministic answer rather than
    # losing the lead. The UI can decide to confirm with the user.
    if match is not None:
        procedure_intent_outcome_total.labels(resolved_via="intent").inc()
        return match.procedure_id, {
            "resolved_via": "intent",
            "confidence_0_1": match.confidence_0_1,
            "matched_synonyms": match.matched_synonyms,
        }
    procedure_intent_outcome_total.labels(resolved_via="unresolved").inc()
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
        _bump_quote_metric("ERROR", None)
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
        _bump_quote_metric("EMERGENCY", procedure)
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
        _bump_quote_metric("ERROR", procedure)
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

    _bump_quote_metric("QUOTE", procedure)
    return envelope


# ──────────────────────────────────────────────────────────
# POST /v1/quote/itinerary
# ──────────────────────────────────────────────────────────

_ITINERARY_DISCLAIMER_TR = (
    "Bu plan illustratiftir; klinik onayı ve ön muayene sonrasında nihai "
    "takvim değişebilir. Sağlık turizmi aracılık hizmetidir, tıbbi tavsiye "
    "değildir."
)


def _make_itinerary_meta() -> Meta:
    return Meta(
        disclaimer_tr=_ITINERARY_DISCLAIMER_TR,
        timestamp=datetime.now(timezone.utc),
    )


def _parse_arrival_date(raw: str) -> Optional[date]:
    """Parse 'YYYY-MM-DD' or return None if malformed.

    We don't accept time components — itinerary granularity is per-day.
    Anything else is a 422-style client error surfaced via ERROR envelope.
    """
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


@router.post("/quote/itinerary", response_model=Envelope)
async def quote_itinerary(http_request: Request, request: ItineraryRequest):
    """Generate a day-by-day itinerary for a chosen procedure + clinic + date."""
    session_id = http_request.headers.get("x-session-id") or str(uuid.uuid4())

    # Idempotency mirror of /v1/quote — same retry-safety guarantees.
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
                    "message_tr": "Idempotency-Key aynı ama istek gövdesi farklı.",
                    "retryable": False,
                },
                meta=_make_itinerary_meta(),
            )
        except Exception as exc:
            logger.warning(
                "itinerary.idempotency_lookup_failed: %s; proceeding", exc
            )
            body_hash = None

    # ─── 1. Validate procedure / clinic / date ────────────────────────
    procedure = procedure_catalog.get_procedure(request.procedure_id)
    if procedure is None:
        _bump_itinerary_metric("ERROR", None)
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
            meta=_make_itinerary_meta(),
        )
    clinic = clinic_registry.get_clinic(request.clinic_id)
    if clinic is None or request.procedure_id not in clinic.get("procedures_offered", []):
        _bump_itinerary_metric("ERROR", procedure)
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
            meta=_make_itinerary_meta(),
        )
    arrival_date = _parse_arrival_date(request.arrival_date)
    if arrival_date is None:
        _bump_itinerary_metric("ERROR", procedure)
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
            meta=_make_itinerary_meta(),
        )

    # ─── 2. Re-run fit-to-travel (health may have changed since quote) ─
    warnings = fit_to_travel.evaluate(
        request.profile, request.procedure_id, request.locale
    )
    if fit_to_travel.has_block(warnings):
        first_block = next(w for w in warnings if w.severity == "block")
        _bump_itinerary_metric("EMERGENCY", procedure)
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
            meta=_make_itinerary_meta(),
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
        _bump_itinerary_metric("ERROR", procedure)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "ITINERARY_GENERATION_FAILED",
                "message_tr": "Plan oluşturulamadı; lütfen tekrar deneyin.",
                "retryable": True,
            },
            meta=_make_itinerary_meta(),
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
        meta=_make_itinerary_meta(),
    )

    if idempotency_key and body_hash is not None:
        try:
            await store_response(
                redis_client,
                idempotency_key,
                body_hash,
                envelope.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.warning("itinerary.idempotency_store_failed: %s", exc)

    _bump_itinerary_metric("ITINERARY", procedure)
    return envelope


# ──────────────────────────────────────────────────────────
# POST /v1/quote/lead  — patient accepts a quote, lead goes to CRM
# ──────────────────────────────────────────────────────────


_LEAD_DISCLAIMER_TR = (
    "Talebiniz alındı. Klinik temsilcisi en kısa sürede sizinle iletişime "
    "geçecektir. Sağlık turizmi aracılık hizmetidir, tıbbi tavsiye değildir."
)
_LEAD_DISCLAIMER_NO_CONSENT_TR = (
    "Talebiniz iletişim onayı verilmediğinden anonim olarak alındı. "
    "İletişim için bir sonraki başvuruda KVKK onayı vermeniz gerekir."
)


def _make_lead_meta() -> Meta:
    return Meta(
        disclaimer_tr=_LEAD_DISCLAIMER_TR,
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/quote/lead", response_model=Envelope)
async def quote_lead(http_request: Request, request: LeadRequest):
    """Accept a quote, hand the lead off to the configured webhook.

    Returns a RESULT envelope with a ``LEAD_ACCEPTED`` code so the
    client UI can show a confirmation. The webhook dispatch happens
    inside this handler (await), but the dispatcher's failure is
    swallowed — the patient sees success either way; the operator
    sees the failure in logs/metrics.
    """
    session_id = http_request.headers.get("x-session-id") or str(uuid.uuid4())
    lead_id = str(uuid.uuid4())

    procedure = procedure_catalog.get_procedure(request.procedure_id)
    clinic = clinic_registry.get_clinic(request.clinic_id)
    if procedure is None or clinic is None or request.procedure_id not in clinic.get(
        "procedures_offered", []
    ):
        _bump_lead_metric("rejected_mismatch", request.consent_to_share)
        return Envelope(
            type="ERROR",
            session_id=session_id,
            turn_index=0,
            payload={
                "code": "CLINIC_PROCEDURE_MISMATCH",
                "message_tr": (
                    "Seçtiğiniz klinik bu prosedürü sunmuyor."
                ),
                "procedure_id": request.procedure_id,
                "clinic_id": request.clinic_id,
                "retryable": True,
            },
            meta=_make_lead_meta(),
        )

    quoted_price = None
    base = (procedure.get("price_band_eur") or {}).get("mid")
    if base is not None:
        quoted_price = int(round(base * float(clinic.get("price_modifier", 1.0))))

    # ─── Persist BEFORE dispatching ───────────────────────────────────
    # The lead row is the durable handle. If Supabase is down, we
    # still proceed to webhook (the operator gets the lead via CRM
    # even without our DB record); the gap surfaces in metrics, not
    # in user-facing 5xx.
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
    # quote_id propagates to the webhook payload so the receiver can
    # cross-reference the offer the patient accepted.
    if request.quote_id:
        payload["quote_id"] = request.quote_id

    # ─── Dispatch webhook ─────────────────────────────────────────────
    outcome = "not_configured"
    try:
        outcome = await lead_dispatcher.dispatch(payload)
    except Exception as exc:
        logger.warning("lead.dispatch_unexpected: %s", exc)
        outcome = "errored"

    # ─── Update DB row with outcome ───────────────────────────────────
    if persisted:
        lead_repository.record_outcome(lead_id, outcome)

    _bump_lead_metric(outcome, request.consent_to_share)

    return Envelope(
        type="RESULT",
        session_id=session_id,
        turn_index=0,
        payload={
            "code": "LEAD_ACCEPTED",
            "lead_id": lead_id,
            "quote_id": request.quote_id,
            "consent_to_share": bool(request.consent_to_share),
            "webhook_status": outcome,
            "webhook_configured": lead_dispatcher.is_configured(),
            "persisted": persisted,
            "next_steps_tr": (
                "Klinik temsilcisi 24 saat içinde sizinle iletişime geçecektir."
                if request.consent_to_share
                else _LEAD_DISCLAIMER_NO_CONSENT_TR
            ),
            "procedure_id": request.procedure_id,
            "procedure_name_tr": procedure_catalog.name(
                request.procedure_id, request.locale
            ),
            "clinic_id": request.clinic_id,
            "clinic_name": clinic["name"],
            "quoted_price_eur": quoted_price,
        },
        meta=_make_lead_meta(),
    )
