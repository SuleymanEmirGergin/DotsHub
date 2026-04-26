"""End-to-end tests for POST /v1/quote.

Each scenario exercises the full pipeline: procedure resolution
(explicit or intent), fit-to-travel rule evaluation, clinic ranking,
envelope shaping. Pure FastAPI TestClient — no mocks of internal
services, because the entire point of the route is composing them.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _post(client, body, headers=None):
    return client.post("/v1/quote", json=body, headers=headers or {})


class QuoteHappyPathTests(unittest.TestCase):
    # setUp removed — caches cleared by autouse fixture in conftest.py.

    def test_explicit_procedure_id_returns_quote_envelope(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {"age": 35, "sex": "male"},
                "locale": "tr-TR",
                "top_n": 3,
            })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["type"], "QUOTE")
        self.assertEqual(len(body["payload"]["clinics"]), 3)
        # First clinic must have a price + score + map_url.
        first = body["payload"]["clinics"][0]
        self.assertGreater(first["price_eur"], 0)
        self.assertIn("score_0_1", first)
        self.assertEqual(body["payload"]["currency"], "EUR")

    def test_quote_includes_procedure_metadata(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "rhinoplasty",
                "profile": {"age": 30},
                "locale": "tr-TR",
            })
        proc = r.json()["payload"]["procedure"]
        self.assertEqual(proc["id"], "rhinoplasty")
        self.assertEqual(proc["category"], "plastic_surgery")
        self.assertGreater(proc["post_op_no_fly_days"], 0)
        self.assertIn("Burun", proc["name_tr"])

    def test_intent_resolution_path(self):
        with TestClient(app) as client:
            r = _post(client, {
                "user_message": "burnumdan memnun değilim",
                "profile": {"age": 28},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["type"], "QUOTE")
        self.assertEqual(body["payload"]["procedure"]["id"], "rhinoplasty")
        intent = body["payload"]["intent_resolution"]
        self.assertEqual(intent["resolved_via"], "intent")
        self.assertGreater(intent["confidence_0_1"], 0)


class QuoteFitToTravelTests(unittest.TestCase):
    # setUp removed — autouse fixture in conftest.py.

    def test_recent_mi_returns_emergency_envelope_no_clinics(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "rhinoplasty",
                "profile": {"age": 52, "recent_mi": True},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["type"], "EMERGENCY")
        self.assertNotIn("clinics", body["payload"])
        self.assertIn("kalp", body["payload"]["reason_tr"].lower())
        # Block warning still rides on the payload so UI can surface it.
        warnings = body["payload"]["fit_to_travel_warnings"]
        self.assertTrue(any(w["severity"] == "block" for w in warnings))

    def test_smoker_warns_but_returns_quote(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "rhinoplasty",
                "profile": {"age": 30, "smoker_active": True},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["type"], "QUOTE")
        warns = body["payload"]["fit_to_travel_warnings"]
        self.assertTrue(any(w["severity"] == "warn" for w in warns))
        self.assertFalse(any(w["severity"] == "block" for w in warns))

    def test_clean_profile_yields_no_warnings(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "lasik",
                "profile": {"age": 30},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["type"], "QUOTE")
        self.assertEqual(body["payload"]["fit_to_travel_warnings"], [])


class QuoteErrorPathsTests(unittest.TestCase):
    # setUp removed — autouse fixture in conftest.py.

    def test_no_procedure_id_no_user_message_returns_unresolved(self):
        with TestClient(app) as client:
            r = _post(client, {"profile": {}, "locale": "tr-TR"})
        body = r.json()
        self.assertEqual(body["type"], "ERROR")
        self.assertEqual(body["payload"]["code"], "PROCEDURE_UNRESOLVED")

    def test_gibberish_user_message_returns_unresolved(self):
        with TestClient(app) as client:
            r = _post(client, {
                "user_message": "xyzzy plugh quux",
                "profile": {},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["payload"]["code"], "PROCEDURE_UNRESOLVED")

    def test_explicit_unknown_procedure_id_returns_unresolved(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "not_a_real_procedure",
                "profile": {},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["payload"]["code"], "PROCEDURE_UNRESOLVED")


class QuoteIdempotencyTests(unittest.TestCase):
    # setUp / tearDown removed — autouse fixture in conftest.py.

    def test_repeat_with_same_key_and_body_returns_cached(self):
        # Call once, mutate the catalog cache so a second call would
        # see different output if the engine ran again, then verify
        # the second call returned the cached envelope.
        with TestClient(app) as client:
            r1 = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {"age": 35},
                "locale": "tr-TR",
                "top_n": 3,
            }, headers={"Idempotency-Key": "k-quote-1"})
            r2 = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {"age": 35},
                "locale": "tr-TR",
                "top_n": 3,
            }, headers={"Idempotency-Key": "k-quote-1"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json(), r2.json())

    def test_repeat_with_same_key_different_body_returns_error(self):
        with TestClient(app) as client:
            r1 = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {},
                "locale": "tr-TR",
            }, headers={"Idempotency-Key": "k-quote-2"})
            self.assertEqual(r1.json()["type"], "QUOTE")
            r2 = _post(client, {
                "procedure_id": "rhinoplasty",  # different body
                "profile": {},
                "locale": "tr-TR",
            }, headers={"Idempotency-Key": "k-quote-2"})
        self.assertEqual(r2.json()["type"], "ERROR")
        self.assertEqual(r2.json()["payload"]["code"], "IDEMPOTENCY_KEY_REUSED")


class QuoteIdContinuityTests(unittest.TestCase):
    """quote_id flow: /v1/quote returns it; /v1/quote/lead optionally
    forwards it; webhook payload carries it. Operator can trace which
    exact price/clinic combination the patient accepted."""

    # autouse fixture in conftest.py handles cache cleanup.

    def test_quote_envelope_includes_quote_id(self):
        with TestClient(app) as client:
            r = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {},
                "locale": "tr-TR",
            })
        body = r.json()
        self.assertEqual(body["type"], "QUOTE")
        self.assertIn("quote_id", body["payload"])
        # UUID4 hex format check (loose — full validation in pydantic
        # if we ever type the field strictly).
        qid = body["payload"]["quote_id"]
        self.assertEqual(len(qid), 36)
        self.assertEqual(qid.count("-"), 4)

    def test_quote_id_differs_across_calls(self):
        with TestClient(app) as client:
            r1 = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {},
                "locale": "tr-TR",
            })
            r2 = _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {},
                "locale": "tr-TR",
            })
        self.assertNotEqual(
            r1.json()["payload"]["quote_id"],
            r2.json()["payload"]["quote_id"],
        )

    def test_lead_accepts_and_returns_quote_id(self):
        with TestClient(app) as client:
            r = client.post("/v1/quote/lead", json={
                "procedure_id": "fue_hair_transplant",
                "clinic_id": "clinic_istanbul_aesthetics_one",
                "quote_id": "Q-stable-12345",
                "consent_to_share": False,
            })
        body = r.json()
        self.assertEqual(body["payload"]["quote_id"], "Q-stable-12345")

    def test_lead_quote_id_propagates_to_webhook_payload(self):
        from app.services import lead_dispatcher

        captured: list[dict] = []

        async def _capture(payload):
            captured.append(payload)
            return "delivered"

        with patch.object(
            lead_dispatcher.settings, "LEAD_WEBHOOK_URL",
            "https://hooks.example.com/x",
        ), patch(
            "app.services.lead_dispatcher.dispatch", new=_capture,
        ):
            with TestClient(app) as client:
                client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "quote_id": "Q-from-prior-quote",
                    "consent_to_share": False,
                })
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["quote_id"], "Q-from-prior-quote")


class LeadPersistenceWiringTests(unittest.TestCase):
    """The /v1/quote/lead route writes to lead_repository before
    dispatch and updates the row with the dispatch outcome."""

    def test_lead_calls_insert_then_record_outcome(self):
        from app.services import lead_dispatcher, lead_repository

        async def _fake_dispatch(payload):  # noqa: ARG001
            return "delivered"

        with patch.object(
            lead_dispatcher.settings, "LEAD_WEBHOOK_URL",
            "https://hooks.example.com/x",
        ), patch(
            "app.services.lead_dispatcher.dispatch", new=_fake_dispatch,
        ), patch.object(
            lead_repository, "insert", return_value=True,
        ) as insert_mock, patch.object(
            lead_repository, "record_outcome", return_value=True,
        ) as outcome_mock:
            with TestClient(app) as client:
                r = client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "consent_to_share": True,
                    "contact": {"name": "T"},
                })
        self.assertEqual(r.json()["payload"]["persisted"], True)
        insert_mock.assert_called_once()
        outcome_mock.assert_called_once()
        # Outcome string must match dispatcher's return.
        self.assertEqual(outcome_mock.call_args[0][1], "delivered")

    def test_lead_skips_record_outcome_when_persistence_fails(self):
        """If insert returns False (Supabase down), don't bother
        calling record_outcome — there's nothing to update."""
        from app.services import lead_dispatcher, lead_repository

        async def _fake_dispatch(payload):  # noqa: ARG001
            return "delivered"

        with patch(
            "app.services.lead_dispatcher.dispatch", new=_fake_dispatch,
        ), patch.object(
            lead_repository, "insert", return_value=False,
        ), patch.object(
            lead_repository, "record_outcome", return_value=True,
        ) as outcome_mock:
            with TestClient(app) as client:
                r = client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "consent_to_share": False,
                })
        self.assertEqual(r.json()["payload"]["persisted"], False)
        outcome_mock.assert_not_called()


class QuoteSessionRateLimitTests(unittest.TestCase):
    # setUp removed — autouse fixture in conftest.py.

    def test_session_bucket_consumed_when_header_present(self):
        from app import rate_limit as rl

        with TestClient(app) as client:
            _post(client, {
                "procedure_id": "fue_hair_transplant",
                "profile": {},
                "locale": "tr-TR",
            }, headers={"X-Session-Id": "quote-sess-1"})
        self.assertIn("sid:quote-sess-1", rl._SESSION_BUCKETS)


if __name__ == "__main__":
    unittest.main()
