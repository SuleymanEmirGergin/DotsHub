"""Health-tourism Prometheus counter wiring.

Five counters added in this commit:
    quote_total{outcome, procedure_category}
    itinerary_total{outcome, procedure_category}
    lead_total{webhook_status, consent_to_share}
    lead_webhook_dispatch_total{outcome}
    procedure_intent_outcome_total{resolved_via}

Tests verify each counter increments on the documented signal —
without these, the dashboard wiring would silently no-op (the original
gap in the audit). Each scenario reads the counter value before / after
the request and asserts an exact +1 delta.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.observability import (
    itinerary_total,
    lead_total,
    lead_webhook_dispatch_total,
    procedure_intent_outcome_total,
    quote_total,
)


def _read(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


class QuoteCounterTests(unittest.TestCase):
    def test_quote_outcome_quote_increments_with_category(self):
        before = _read(
            quote_total, outcome="QUOTE", procedure_category="hair"
        )
        with TestClient(app) as client:
            r = client.post("/v1/quote", json={
                "procedure_id": "fue_hair_transplant",
                "profile": {},
                "locale": "tr-TR",
            })
        self.assertEqual(r.json()["type"], "QUOTE")
        after = _read(
            quote_total, outcome="QUOTE", procedure_category="hair"
        )
        self.assertEqual(after - before, 1.0)

    def test_quote_outcome_emergency_on_block(self):
        before = _read(
            quote_total, outcome="EMERGENCY",
            procedure_category="plastic_surgery",
        )
        with TestClient(app) as client:
            r = client.post("/v1/quote", json={
                "procedure_id": "rhinoplasty",
                "profile": {"recent_mi": True},
                "locale": "tr-TR",
            })
        self.assertEqual(r.json()["type"], "EMERGENCY")
        after = _read(
            quote_total, outcome="EMERGENCY",
            procedure_category="plastic_surgery",
        )
        self.assertEqual(after - before, 1.0)

    def test_quote_outcome_error_on_unresolved(self):
        before = _read(
            quote_total, outcome="ERROR", procedure_category="unknown"
        )
        with TestClient(app) as client:
            client.post("/v1/quote", json={
                "user_message": "xyzzy gibberish",
                "profile": {},
                "locale": "tr-TR",
            })
        after = _read(
            quote_total, outcome="ERROR", procedure_category="unknown"
        )
        self.assertEqual(after - before, 1.0)


class ItineraryCounterTests(unittest.TestCase):
    def test_itinerary_outcome_itinerary_increments(self):
        before = _read(
            itinerary_total, outcome="ITINERARY", procedure_category="hair"
        )
        with TestClient(app) as client:
            r = client.post("/v1/quote/itinerary", json={
                "procedure_id": "fue_hair_transplant",
                "clinic_id": "clinic_istanbul_aesthetics_one",
                "arrival_date": "2026-05-15",
                "profile": {},
                "locale": "tr-TR",
            })
        self.assertEqual(r.json()["type"], "ITINERARY")
        after = _read(
            itinerary_total, outcome="ITINERARY", procedure_category="hair"
        )
        self.assertEqual(after - before, 1.0)

    def test_itinerary_outcome_error_on_mismatch(self):
        before = _read(
            itinerary_total, outcome="ERROR",
            procedure_category="ophthalmology",
        )
        with TestClient(app) as client:
            client.post("/v1/quote/itinerary", json={
                "procedure_id": "lasik",
                "clinic_id": "clinic_ankara_cardiac",  # doesn't offer LASIK
                "arrival_date": "2026-05-15",
                "profile": {},
            })
        after = _read(
            itinerary_total, outcome="ERROR",
            procedure_category="ophthalmology",
        )
        self.assertEqual(after - before, 1.0)


class LeadCounterTests(unittest.TestCase):
    def test_lead_total_increments_with_webhook_status(self):
        # No webhook configured → status = "not_configured".
        from app.services import lead_dispatcher

        before = _read(
            lead_total, webhook_status="not_configured", consent_to_share="true"
        )
        with patch.object(lead_dispatcher.settings, "LEAD_WEBHOOK_URL", ""):
            with TestClient(app) as client:
                client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "consent_to_share": True,
                    "contact": {"name": "T"},
                })
        after = _read(
            lead_total, webhook_status="not_configured", consent_to_share="true"
        )
        self.assertEqual(after - before, 1.0)

    def test_lead_total_consent_label_matches_request(self):
        from app.services import lead_dispatcher

        before = _read(
            lead_total, webhook_status="not_configured",
            consent_to_share="false",
        )
        with patch.object(lead_dispatcher.settings, "LEAD_WEBHOOK_URL", ""):
            with TestClient(app) as client:
                client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "consent_to_share": False,
                })
        after = _read(
            lead_total, webhook_status="not_configured",
            consent_to_share="false",
        )
        self.assertEqual(after - before, 1.0)


class LeadWebhookDispatchCounterTests(unittest.TestCase):
    """The counter that was previously broken — referenced from
    lead_dispatcher but never registered. Now it bumps for real."""

    def test_dispatch_counter_increments_on_delivered(self):
        # Trigger a real dispatch via patching the inner http client.
        from app.services import lead_dispatcher
        from unittest.mock import AsyncMock, MagicMock

        import httpx

        before = _read(
            lead_webhook_dispatch_total, outcome="delivered"
        )

        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.text = ""

        async def _fake_post(*args, **kwargs):  # noqa: ARG001
            return response

        async def _run():
            with patch.object(
                lead_dispatcher.settings,
                "LEAD_WEBHOOK_URL",
                "https://x.example/hook",
            ), patch.object(
                httpx.AsyncClient, "post", new=_fake_post
            ):
                await lead_dispatcher.dispatch({"any": "payload"})

        import asyncio
        asyncio.run(_run())

        after = _read(
            lead_webhook_dispatch_total, outcome="delivered"
        )
        self.assertEqual(after - before, 1.0)


class ProcedureIntentOutcomeCounterTests(unittest.TestCase):
    def test_explicit_resolution_bumps_explicit(self):
        before = _read(
            procedure_intent_outcome_total, resolved_via="explicit"
        )
        with TestClient(app) as client:
            client.post("/v1/quote", json={
                "procedure_id": "lasik",
                "profile": {},
                "locale": "tr-TR",
            })
        after = _read(
            procedure_intent_outcome_total, resolved_via="explicit"
        )
        self.assertEqual(after - before, 1.0)

    def test_synonym_match_bumps_intent(self):
        before = _read(
            procedure_intent_outcome_total, resolved_via="intent"
        )
        with TestClient(app) as client:
            client.post("/v1/quote", json={
                "user_message": "saç ekimi yaptırmak istiyorum",
                "profile": {},
                "locale": "tr-TR",
            })
        after = _read(
            procedure_intent_outcome_total, resolved_via="intent"
        )
        self.assertEqual(after - before, 1.0)

    def test_unresolved_bumps_unresolved(self):
        before = _read(
            procedure_intent_outcome_total, resolved_via="unresolved"
        )
        with TestClient(app) as client:
            client.post("/v1/quote", json={
                "user_message": "totally unrelated gibberish",
                "profile": {},
                "locale": "tr-TR",
            })
        after = _read(
            procedure_intent_outcome_total, resolved_via="unresolved"
        )
        self.assertEqual(after - before, 1.0)


if __name__ == "__main__":
    unittest.main()
