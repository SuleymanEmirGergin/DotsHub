"""Shared helpers for the three health-tourism route handlers.

Why a `_shared` module instead of cross-importing between route files
    Each route file would otherwise need to import from its sibling,
    creating circular-import risk if the import order shifts. A
    sibling that owns the shared concern keeps the dependency graph
    a tree.

Contents:
    Disclaimers       — TR copy strings reused in Envelope.meta
    make_meta()       — single Meta-builder, parametrized on disclaimer
    _bump_*_metric()  — Prometheus counter wrappers (one per endpoint)
    _resolve_procedure_id() — quote endpoint's 3-tier intent resolver
    _parse_arrival_date()   — itinerary endpoint's date parser
    _dispatch_and_record()  — lead endpoint's BackgroundTasks coroutine
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from app.models.schemas import Meta, QuoteRequest
from app.observability import (
    itinerary_total,
    lead_total,
    procedure_intent_outcome_total,
    quote_total,
)
from app.services import (
    lead_dispatcher,
    lead_repository,
    procedure_catalog,
    procedure_intent,
    procedure_intent_llm,
)

logger = logging.getLogger(__name__)


# ─── Disclaimer copy ─────────────────────────────────────────────────

QUOTE_DISCLAIMER_TR = (
    "Bu fiyatlar bağlayıcı değildir; klinik onayı, ön muayene ve nihai "
    "tedavi planı sonrası kesinleşir. Sağlık turizmi aracılık hizmetidir, "
    "tıbbi tavsiye değildir."
)
ITINERARY_DISCLAIMER_TR = (
    "Bu plan illustratiftir; klinik onayı ve ön muayene sonrasında nihai "
    "takvim değişebilir. Sağlık turizmi aracılık hizmetidir, tıbbi tavsiye "
    "değildir."
)
LEAD_DISCLAIMER_TR = (
    "Talebiniz alındı. Klinik temsilcisi en kısa sürede sizinle iletişime "
    "geçecektir. Sağlık turizmi aracılık hizmetidir, tıbbi tavsiye değildir."
)
LEAD_DISCLAIMER_NO_CONSENT_TR = (
    "Talebiniz iletişim onayı verilmediğinden anonim olarak alındı. "
    "İletişim için bir sonraki başvuruda KVKK onayı vermeniz gerekir."
)


# ─── Meta builder (R4: replaces three near-identical functions) ──────

def make_meta(disclaimer_tr: str) -> Meta:
    """Construct an Envelope.meta block. Disclaimer is the only field
    that varies across the three endpoints; previously each route had
    its own `_make_*_meta` function, all identical except for that one
    constant. The IdempotencyHelper accepts any zero-arg callable, so
    routes pass `lambda: make_meta(QUOTE_DISCLAIMER_TR)`."""
    return Meta(
        disclaimer_tr=disclaimer_tr,
        timestamp=datetime.now(timezone.utc),
    )


# ─── Prometheus counter helpers ──────────────────────────────────────

def bump_quote_metric(envelope_type: str, procedure: Optional[dict]) -> None:
    category = (procedure or {}).get("category") or "unknown"
    quote_total.labels(outcome=envelope_type, procedure_category=category).inc()


def bump_itinerary_metric(envelope_type: str, procedure: Optional[dict]) -> None:
    category = (procedure or {}).get("category") or "unknown"
    itinerary_total.labels(
        outcome=envelope_type, procedure_category=category
    ).inc()


def bump_lead_metric(webhook_status: str, consent_to_share: bool) -> None:
    lead_total.labels(
        webhook_status=webhook_status,
        consent_to_share="true" if consent_to_share else "false",
    ).inc()


# ─── Procedure-intent resolution (used by quote endpoint only) ──────

def resolve_procedure_id(
    req: QuoteRequest,
) -> Optional[tuple[str, dict]]:
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
        procedure_intent_outcome_total.labels(resolved_via="unresolved").inc()
        return None
    if not req.user_message:
        procedure_intent_outcome_total.labels(resolved_via="unresolved").inc()
        return None

    match = procedure_intent.extract(req.user_message, req.locale)
    if match is not None and not procedure_intent_llm.should_fallback(match):
        procedure_intent_outcome_total.labels(resolved_via="intent").inc()
        return match.procedure_id, {
            "resolved_via": "intent",
            "confidence_0_1": match.confidence_0_1,
            "matched_synonyms": match.matched_synonyms,
        }

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

    if match is not None:
        procedure_intent_outcome_total.labels(resolved_via="intent").inc()
        return match.procedure_id, {
            "resolved_via": "intent",
            "confidence_0_1": match.confidence_0_1,
            "matched_synonyms": match.matched_synonyms,
        }
    procedure_intent_outcome_total.labels(resolved_via="unresolved").inc()
    return None


# ─── Date parser (used by itinerary endpoint only) ──────────────────

def parse_arrival_date(raw: str) -> Optional[date]:
    """Parse 'YYYY-MM-DD' or return None if malformed.

    We don't accept time components — itinerary granularity is per-day.
    Anything else is a 422-style client error surfaced via ERROR envelope.
    """
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


# ─── Lead webhook background task ────────────────────────────────────

async def dispatch_and_record(
    *,
    lead_id: str,
    payload: dict,
    persisted: bool,
    consent_to_share: bool,
) -> None:
    """Background task: deliver the webhook, update the DB row, bump
    the prometheus counter. Runs after the response is sent so a slow
    CRM does NOT add to user-visible latency.

    Failure-mode contract: every step fail-soft, the user sees no
    consequence, ops sees the gap in metrics + the lead row's
    terminal `webhook_status`.
    """
    try:
        outcome = await lead_dispatcher.dispatch(payload)
    except Exception as exc:
        logger.warning("lead.bg_dispatch_unexpected: %s", exc)
        outcome = "errored"
    if persisted:
        lead_repository.record_outcome(lead_id, outcome)
    bump_lead_metric(outcome, consent_to_share)
