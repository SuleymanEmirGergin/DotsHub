"""Lead webhook dispatcher.

When a patient accepts a quote, the route handler builds a lead
payload (procedure + clinic + contact info + consent flag) and asks
this module to ship it to the configured CRM via HTTP POST. We
support any JSON-accepting receiver: Slack incoming webhooks,
Make/Zapier hooks, generic CRM endpoints — all the same wire shape.

Why a dedicated module
    - PII handling is concentrated. The redaction policy and the
      consent gate live in one file, easy to audit.
    - Retry policy is uniform. Slow CRMs don't get to add seconds to
      every quote-acceptance flow.
    - Adding a second destination later (e.g. dual-write to Slack +
      generic CRM) is a 1-file change.

Failure-mode contract
    The lead route returns success to the caller as long as the lead
    is accepted server-side. Webhook delivery is best-effort and
    non-blocking — a failed dispatch logs WARN with the response body
    snippet, increments the prometheus error counter, and that's it.
    The caller is not told the webhook failed because they cannot
    act on it (the CRM is the operator's problem).

Privacy
    Without ``consent_to_share=True`` on the request, contact PII
    (name/email/phone) is REMOVED from the webhook payload before
    dispatch. The lead is still sent so the operator can follow up
    via the patient's session_id, but no personal data leaves the
    backend until consent is recorded.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Prometheus counters (lazy-imported, optional) ───────────────────


def _inc_counter(name: str, **labels: str) -> None:
    """Lookup the named counter; no-op if prometheus_client is missing
    or the metric isn't registered. Keeps the dispatcher importable in
    test envs without metrics."""
    try:
        from app import observability
        counter = getattr(observability, name, None)
        if counter is None:
            return
        counter.labels(**labels).inc() if labels else counter.inc()
    except Exception:  # pragma: no cover — defensive
        return


# ─── Configuration ───────────────────────────────────────────────────


def is_configured() -> bool:
    return bool(getattr(settings, "LEAD_WEBHOOK_URL", "") or "")


def _headers() -> dict[str, str]:
    out = {"content-type": "application/json"}
    token = getattr(settings, "LEAD_WEBHOOK_AUTH_TOKEN", "") or ""
    if token:
        out["authorization"] = f"Bearer {token}"
    return out


# ─── Payload shaping ─────────────────────────────────────────────────


def build_payload(
    *,
    lead_id: str,
    session_id: str,
    procedure: dict[str, Any],
    clinic: dict[str, Any],
    contact: dict[str, Any],
    consent_to_share: bool,
    locale: str,
    notes: str,
    quoted_price_eur: Optional[int] = None,
) -> dict[str, Any]:
    """Assemble the JSON object posted to the webhook.

    Without consent, contact fields are stripped — the operator gets
    enough to audit the lead (session_id, locale, procedure, clinic,
    timestamp) but no personal identifiers.
    """
    payload: dict[str, Any] = {
        "type": "health_tourism_lead",
        "lead_id": lead_id,
        "session_id": session_id,
        "locale": locale,
        "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "procedure": {
            "id": procedure.get("id"),
            "category": procedure.get("category"),
            "name_tr": (procedure.get("name") or {}).get("tr"),
            "name_en": (procedure.get("name") or {}).get("en"),
        },
        "clinic": {
            "id": clinic.get("id"),
            "name": clinic.get("name"),
            "city": clinic.get("city"),
        },
        "quoted_price_eur": quoted_price_eur,
        "consent_to_share": bool(consent_to_share),
        "notes": notes or "",
    }
    if consent_to_share:
        payload["contact"] = {
            "name": contact.get("name", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "preferred_contact": contact.get("preferred_contact", ""),
            "best_time": contact.get("best_time", ""),
        }
    else:
        # Sentinel marker so the receiving operator knows this lead is
        # waiting on consent; they should follow up via the patient's
        # next session, not by guessing contact details.
        payload["contact"] = {"redacted": True}
    return payload


# ─── Dispatch ────────────────────────────────────────────────────────


async def _post_once(
    client: httpx.AsyncClient, url: str, body: dict, timeout: float
) -> httpx.Response:
    return await client.post(
        url, json=body, headers=_headers(), timeout=timeout
    )


async def dispatch(payload: dict) -> str:
    """POST the payload with bounded retries. Return one of the
    granular outcome strings used by ``lead_repository.record_outcome``:

      - "delivered"        → 2xx response on any attempt
      - "failed_4xx"       → 4xx client error (permanent, no retry)
      - "failed_exhausted" → all retries returned 5xx / network error
      - "not_configured"   → LEAD_WEBHOOK_URL is empty (drop silently)

    The state-machine is shared with the persistence layer so a
    typo here would surface as a CHECK-constraint violation in
    the SQL migration. Backoff: 250 ms × attempt up to 1 s.
    """
    if not is_configured():
        logger.debug("lead_dispatcher.no_webhook_configured")
        return "not_configured"

    url = settings.LEAD_WEBHOOK_URL
    timeout = float(getattr(settings, "LEAD_WEBHOOK_TIMEOUT_SECONDS", 5.0))
    max_retries = max(1, int(getattr(settings, "LEAD_WEBHOOK_MAX_RETRIES", 3)))

    async with httpx.AsyncClient() as client:
        for attempt in range(1, max_retries + 1):
            try:
                resp = await _post_once(client, url, payload, timeout)
                if 200 <= resp.status_code < 300:
                    _inc_counter("lead_webhook_dispatch_total", outcome="delivered")
                    return "delivered"
                # 4xx is permanent — don't retry. The webhook URL or
                # auth token is wrong; the operator must fix it.
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        "lead_dispatcher.permanent_failure status=%d body=%r",
                        resp.status_code, resp.text[:200],
                    )
                    _inc_counter(
                        "lead_webhook_dispatch_total", outcome="failed_4xx"
                    )
                    return "failed_4xx"
                # 5xx → transient, retry within the cap
                logger.info(
                    "lead_dispatcher.transient_failure attempt=%d status=%d",
                    attempt, resp.status_code,
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.info(
                    "lead_dispatcher.network_failure attempt=%d %s",
                    attempt, exc,
                )
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.warning(
                    "lead_dispatcher.unexpected attempt=%d %s",
                    attempt, exc,
                )

            if attempt < max_retries:
                # Bounded linear backoff: 250 ms, 500 ms, 750 ms ...
                await asyncio.sleep(min(0.25 * attempt, 1.0))

    _inc_counter("lead_webhook_dispatch_total", outcome="failed_exhausted")
    return "failed_exhausted"
