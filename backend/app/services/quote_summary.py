"""LLM-generated patient-facing summary for /v1/quote.

The QUOTE envelope returns a structured ranking of clinics; this
module adds an optional 2-3 sentence Turkish blurb explaining why the
top clinic was picked, written in patient language. The blurb is the
``payload.summary_tr`` field on a QUOTE envelope; it is ``None`` when:

  - feature flag (``QUOTE_SUMMARY_LLM_ENABLED``) is off
  - all configured providers are disabled or failed
  - the cache miss path triggers a background generate (first request
    after a cache invalidation; subsequent calls hit the cache)

Why background, not inline
    Wiro's submit + poll cycle for the LLMs we support takes 5-30s
    typical. Inlining that would blow the /v1/quote p95 SLO. The
    background-task pattern + LRU cache means:
      - First call for a (procedure, clinic, locale) combo: returns
        immediately with ``summary_tr=None`` and fires a fire-and-forget
        generate. The frontend renders the QUOTE skeleton; the next
        request (same combo) returns the cached blurb.
      - Subsequent calls within TTL (24h default): cache hit, ~0ms.

Provider chain
    ``QUOTE_SUMMARY_LLM_PROVIDERS`` is a comma-separated env list of
    provider keys, primary first (default ``"qwen,gpt5_mini"``). Each
    provider's ``is_enabled()`` is checked; disabled providers are
    skipped (the operator might have removed credentials for one
    vendor). The first non-empty response wins; if all providers fail
    we leave ``summary_tr=None`` and the next request will retry on
    cache miss.

Cache
    In-memory LRU keyed on (procedure_id, top_clinic_id, locale). The
    cache is per-process; multi-instance deployments will see lower
    hit rates until we promote this to Redis (deferred — single-process
    deployment is the current production target).

Observability
    - Prometheus: ``quote_summary_total{provider, outcome}``,
      ``quote_summary_latency_seconds{provider}``,
      ``quote_summary_cache_total{result}``.
    - Supabase ``llm_calls`` row per provider attempt (same shape as
      procedure_intent_llm), tagged with ``nlu_source="quote_summary_llm"``.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from app.core.config import settings
from app.observability.metrics import (
    quote_summary_cache_total,
    quote_summary_latency_seconds,
    quote_summary_total,
)
from app.pii import redact_pii
from app.services.ai import gemini_llm, gpt5_mini_llm, grok_llm, qwen_llm

logger = logging.getLogger(__name__)


# ─── Provider registry ──────────────────────────────────────────────
#
# Module references — NOT direct function references — so tests can
# monkeypatch ``provider_module.is_enabled`` and ``.generate`` on a
# per-provider basis. Adding a new provider is a single line plus a
# config-defaulted env entry.

_PROVIDERS: dict[str, Any] = {
    "qwen": qwen_llm,
    "gpt5_mini": gpt5_mini_llm,
    "gemini": gemini_llm,
    "grok": grok_llm,
}


def _provider_chain() -> list[str]:
    """Return the configured provider chain, preserving order."""
    raw = getattr(settings, "QUOTE_SUMMARY_LLM_PROVIDERS", "") or ""
    return [name.strip() for name in raw.split(",") if name.strip()]


# ─── Cache ──────────────────────────────────────────────────────────
#
# Plain LRU dict + lock. ``OrderedDict.move_to_end`` gives us O(1)
# touch; ``popitem(last=False)`` evicts the oldest entry. Module-level
# state — the autouse pytest fixture in conftest.py doesn't clear this
# (it doesn't know about it), so tests that need a clean slate call
# ``_cache_clear()`` explicitly via the helper below.

_CACHE: "OrderedDict[str, tuple[float, str]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _cache_get(key: str) -> Optional[str]:
    ttl = float(getattr(settings, "QUOTE_SUMMARY_CACHE_TTL_SECONDS", 86400))
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        ts, value = entry
        if now - ts > ttl:
            # Expired — drop and miss. Avoids returning stale text after
            # the operator updates clinic copy or pricing.
            _CACHE.pop(key, None)
            return None
        _CACHE.move_to_end(key)
        return value


def _cache_set(key: str, value: str) -> None:
    max_entries = int(getattr(settings, "QUOTE_SUMMARY_CACHE_MAX_ENTRIES", 256))
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > max_entries:
            _CACHE.popitem(last=False)


def _cache_clear() -> None:
    """Explicit reset — used by tests. Production has no caller."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _cache_key(*, procedure_id: str, top_clinic_id: str, locale: str) -> str:
    """Hash the inputs that meaningfully change the summary text.

    Price + city are deliberately excluded: price varies by ±EUR fees
    that don't change the patient-facing copy; city is a function of
    the clinic anyway. Including them would tank the hit rate without
    improving fidelity.
    """
    raw = f"{procedure_id}|{top_clinic_id}|{(locale or 'tr').lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ─── Prompt construction ────────────────────────────────────────────


_PROMPT_TEMPLATE = (
    "Sen bir sağlık turizmi danışmanısın. Aşağıdaki teklifi hasta için "
    "Türkçe, 2-3 cümlelik bir özet halinde açıkla. Tıbbi tavsiye ve "
    "tanı koyma; sadece klinik, prosedür ve tahmini fiyat bilgisini "
    "patient-friendly bir dille aktar. Cevapta sadece özet metni "
    "döndür — başlık, madde işareti veya 'Özet:' gibi bir önek "
    "ekleme.\n\n"
    "Prosedür: {procedure_name_tr} ({complexity}, ~{duration_days} gün)\n"
    "Klinik: {clinic_name}, {clinic_city}\n"
    "Tahmini fiyat: {price_amount} {price_currency}"
)


def _build_prompt(
    *,
    procedure_name_tr: str,
    complexity: str,
    duration_days: Any,
    clinic_name: str,
    clinic_city: str,
    price_amount: Any,
    price_currency: str,
) -> str:
    """Render the prompt and apply PII redaction.

    There's no patient PII in the inputs (clinic + procedure metadata
    is operator-curated), but ``redact_pii`` is cheap insurance against
    the day someone passes a clinic name like 'Acme Surgery (info@x.com)'
    that includes contact details which shouldn't echo to Wiro.
    """
    raw = _PROMPT_TEMPLATE.format(
        procedure_name_tr=procedure_name_tr or "",
        complexity=complexity or "",
        duration_days=duration_days if duration_days is not None else "",
        clinic_name=clinic_name or "",
        clinic_city=clinic_city or "",
        price_amount=price_amount if price_amount is not None else "",
        price_currency=price_currency or "",
    )
    return redact_pii(raw)


# ─── Supabase log ───────────────────────────────────────────────────


def _sentry_breadcrumb(
    *,
    provider: str,
    outcome: str,
    latency_ms: int,
    error_type: Optional[str] = None,
) -> None:
    """Attach a Sentry breadcrumb for the provider attempt.

    Background tasks DON'T inherit the request scope, so any unhandled
    exception in ``generate_and_cache`` shows up as a generic
    background event without context. Breadcrumbs added here surface
    the provider-by-provider attempts on the same trail when an
    exception eventually does fire (e.g. ``Exception`` clause caught
    one provider but the next raised something we missed).

    Wrapped in try/except so an observability hiccup never crashes
    the BG task — same convention the Supabase log uses."""
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            category="quote_summary",
            message=f"provider={provider} outcome={outcome}",
            level="info" if outcome == "success" else "warning",
            data={
                "provider": provider,
                "outcome": outcome,
                "latency_ms": latency_ms,
                "error_type": error_type,
            },
        )
    except Exception:  # noqa: BLE001 — observability must not raise
        pass


def _log_llm_call(
    *,
    provider: str,
    success: bool,
    latency_ms: int,
    error_type: Optional[str],
) -> None:
    """Append one row to ``llm_calls`` (fire-and-forget daemon thread).

    Same table + shape as procedure_intent_llm, tagged via the
    ``nlu_source`` column so dashboards can split quote_summary
    traffic from procedure-intent traffic. ``input_tokens`` /
    ``output_tokens`` are 0: Wiro doesn't surface token counts on the
    /Task/Detail response (only ``elapsedseconds`` and ``totalcost``).
    Cost per call lives in ``totalcost`` if a future migration adds it.
    """
    if not getattr(settings, "LLM_NLU_LOG_TO_SUPABASE", False):
        return

    row = {
        "session_id": None,
        "provider": "wiro",
        "model": provider,  # short provider label (qwen / gpt5_mini / ...)
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms": latency_ms,
        "success": success,
        "error_type": error_type,
        "nlu_source": "quote_summary_llm",
    }

    def _insert() -> None:
        try:
            from app.db import supabase
            supabase.table("llm_calls").insert(row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("quote_summary.log_failed: %s", exc)

    threading.Thread(target=_insert, daemon=True).start()


# ─── Public API ─────────────────────────────────────────────────────


def is_enabled() -> bool:
    return bool(getattr(settings, "QUOTE_SUMMARY_LLM_ENABLED", False))


def lookup_cached(
    *, procedure_id: str, top_clinic_id: str, locale: str
) -> Optional[str]:
    """Cache-only lookup. Returns the stored summary if present and
    fresh, ``None`` otherwise. Does NOT invoke any LLM. Used by the
    /v1/quote route for the inline cache hit path."""
    if not is_enabled():
        return None
    key = _cache_key(
        procedure_id=procedure_id,
        top_clinic_id=top_clinic_id,
        locale=locale,
    )
    value = _cache_get(key)
    quote_summary_cache_total.labels(
        result="hit" if value is not None else "miss"
    ).inc()
    return value


def generate_and_cache(
    *,
    procedure_id: str,
    procedure_name_tr: str,
    complexity: str,
    duration_days: Any,
    top_clinic_id: str,
    clinic_name: str,
    clinic_city: str,
    price_amount: Any,
    price_currency: str,
    locale: str,
) -> Optional[str]:
    """Run the provider chain and cache the first non-empty response.

    Returns the generated text on success, ``None`` if every provider
    in the chain failed / was disabled. Always called from a background
    task — the route handler does NOT await this directly.

    Idempotent: re-running with the same inputs returns the cached
    value without invoking another provider.
    """
    if not is_enabled():
        return None

    key = _cache_key(
        procedure_id=procedure_id,
        top_clinic_id=top_clinic_id,
        locale=locale,
    )
    cached = _cache_get(key)
    if cached is not None:
        return cached

    prompt = _build_prompt(
        procedure_name_tr=procedure_name_tr,
        complexity=complexity,
        duration_days=duration_days,
        clinic_name=clinic_name,
        clinic_city=clinic_city,
        price_amount=price_amount,
        price_currency=price_currency,
    )
    timeout = float(
        getattr(settings, "QUOTE_SUMMARY_LLM_TIMEOUT_SECONDS", 30.0)
    )

    for provider_name in _provider_chain():
        module = _PROVIDERS.get(provider_name)
        if module is None:
            logger.warning(
                "quote_summary.unknown_provider: %s (skipping)", provider_name
            )
            continue
        if not module.is_enabled():
            quote_summary_total.labels(
                provider=provider_name, outcome="disabled"
            ).inc()
            continue

        t_start = time.perf_counter()
        try:
            text = module.generate(prompt=prompt, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — never crash the BG task
            elapsed_ms = int((time.perf_counter() - t_start) * 1000)
            quote_summary_total.labels(
                provider=provider_name, outcome="error"
            ).inc()
            quote_summary_latency_seconds.labels(provider=provider_name).observe(
                elapsed_ms / 1000.0
            )
            err = type(exc).__name__.lower()
            error_type = (
                "timeout" if "timeout" in err
                else "rate_limit" if "ratelimit" in err
                else "error"
            )
            _log_llm_call(
                provider=provider_name,
                success=False,
                latency_ms=elapsed_ms,
                error_type=error_type,
            )
            _sentry_breadcrumb(
                provider=provider_name,
                outcome="error",
                latency_ms=elapsed_ms,
                error_type=error_type,
            )
            logger.warning(
                "quote_summary.provider_failed provider=%s: %s",
                provider_name, exc,
            )
            continue

        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        quote_summary_latency_seconds.labels(provider=provider_name).observe(
            elapsed_ms / 1000.0
        )

        if text and text.strip():
            quote_summary_total.labels(
                provider=provider_name, outcome="success"
            ).inc()
            _log_llm_call(
                provider=provider_name,
                success=True,
                latency_ms=elapsed_ms,
                error_type=None,
            )
            _sentry_breadcrumb(
                provider=provider_name,
                outcome="success",
                latency_ms=elapsed_ms,
            )
            cleaned = text.strip()
            _cache_set(key, cleaned)
            return cleaned

        quote_summary_total.labels(
            provider=provider_name, outcome="empty"
        ).inc()
        _log_llm_call(
            provider=provider_name,
            success=False,
            latency_ms=elapsed_ms,
            error_type="empty",
        )
        _sentry_breadcrumb(
            provider=provider_name,
            outcome="empty",
            latency_ms=elapsed_ms,
            error_type="empty",
        )

    return None
