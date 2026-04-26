"""Tests for the lead-conversion webhook layer.

Two layers:
    1. ``services/lead_dispatcher`` — payload shaping, retry policy,
      consent-gated PII redaction.
    2. ``POST /v1/quote/lead`` — accept envelope, mismatch error path,
      webhook dispatch wired in.

Every HTTP egress is mocked.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import lead_dispatcher


# ─── build_payload ───────────────────────────────────────────────────


def _stub_procedure():
    return {
        "id": "fue_hair_transplant",
        "category": "hair",
        "name": {"tr": "FUE Saç Ekimi", "en": "FUE Hair Transplant"},
    }


def _stub_clinic():
    return {
        "id": "clinic_x",
        "name": "Demo Clinic",
        "city": "İstanbul",
    }


def _contact():
    return {
        "name": "Ali Demir",
        "email": "ali@example.com",
        "phone": "+901234567890",
        "preferred_contact": "whatsapp",
        "best_time": "afternoon",
    }


def test_build_payload_with_consent_includes_contact_fields():
    out = lead_dispatcher.build_payload(
        lead_id="L1",
        session_id="S1",
        procedure=_stub_procedure(),
        clinic=_stub_clinic(),
        contact=_contact(),
        consent_to_share=True,
        locale="tr-TR",
        notes="hello",
        quoted_price_eur=2500,
    )
    assert out["consent_to_share"] is True
    assert out["contact"]["email"] == "ali@example.com"
    assert out["contact"]["phone"] == "+901234567890"
    assert out["procedure"]["id"] == "fue_hair_transplant"
    assert out["clinic"]["city"] == "İstanbul"
    assert out["quoted_price_eur"] == 2500


def test_build_payload_without_consent_redacts_contact():
    out = lead_dispatcher.build_payload(
        lead_id="L1",
        session_id="S1",
        procedure=_stub_procedure(),
        clinic=_stub_clinic(),
        contact=_contact(),
        consent_to_share=False,
        locale="tr-TR",
        notes="",
        quoted_price_eur=2500,
    )
    assert out["consent_to_share"] is False
    assert out["contact"] == {"redacted": True}
    # Procedure / clinic / session_id still present so operator can
    # follow up via the patient's session.
    assert out["session_id"] == "S1"
    assert out["clinic"]["id"] == "clinic_x"


# ─── is_configured ───────────────────────────────────────────────────


def test_is_configured_false_when_url_blank():
    with patch.object(lead_dispatcher.settings, "LEAD_WEBHOOK_URL", ""):
        assert lead_dispatcher.is_configured() is False


def test_is_configured_true_when_url_set():
    with patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_URL",
        "https://hooks.slack.com/services/X",
    ):
        assert lead_dispatcher.is_configured() is True


# ─── dispatch ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_returns_false_when_unconfigured():
    with patch.object(lead_dispatcher.settings, "LEAD_WEBHOOK_URL", ""):
        out = await lead_dispatcher.dispatch({"any": "payload"})
    assert out is False


@pytest.mark.asyncio
async def test_dispatch_returns_true_on_2xx():
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = "ok"

    async def _fake_post(*args, **kwargs):  # noqa: ARG001
        return response

    with patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_URL", "https://x.example/hook"
    ), patch.object(
        httpx.AsyncClient, "post", new=_fake_post
    ):
        out = await lead_dispatcher.dispatch({"any": "payload"})
    assert out is True


@pytest.mark.asyncio
async def test_dispatch_returns_false_on_4xx_no_retry():
    """4xx = permanent (bad URL or auth). One attempt only."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = "unauthorized"

    call_count = {"n": 0}

    async def _fake_post(*args, **kwargs):  # noqa: ARG001
        call_count["n"] += 1
        return response

    with patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_URL", "https://x.example/hook"
    ), patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_MAX_RETRIES", 3
    ), patch.object(
        httpx.AsyncClient, "post", new=_fake_post
    ):
        out = await lead_dispatcher.dispatch({"x": 1})
    assert out is False
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_dispatch_retries_on_5xx_and_eventually_succeeds():
    statuses = iter([500, 503, 200])

    async def _fake_post(*args, **kwargs):  # noqa: ARG001
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = next(statuses)
        resp.text = ""
        return resp

    with patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_URL", "https://x.example/hook"
    ), patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_MAX_RETRIES", 3
    ), patch.object(
        httpx.AsyncClient, "post", new=_fake_post
    ), patch(
        "app.services.lead_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        out = await lead_dispatcher.dispatch({"x": 1})
    assert out is True


@pytest.mark.asyncio
async def test_dispatch_returns_false_after_exhausting_retries():
    async def _fake_post(*args, **kwargs):  # noqa: ARG001
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 500
        resp.text = ""
        return resp

    with patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_URL", "https://x.example/hook"
    ), patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_MAX_RETRIES", 2
    ), patch.object(
        httpx.AsyncClient, "post", new=_fake_post
    ), patch(
        "app.services.lead_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        out = await lead_dispatcher.dispatch({"x": 1})
    assert out is False


@pytest.mark.asyncio
async def test_dispatch_handles_network_exception_with_retry():
    attempts = {"n": 0}

    async def _flaky(*args, **kwargs):  # noqa: ARG001
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectError("dns")
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.text = ""
        return resp

    with patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_URL", "https://x.example/hook"
    ), patch.object(
        lead_dispatcher.settings, "LEAD_WEBHOOK_MAX_RETRIES", 3
    ), patch.object(
        httpx.AsyncClient, "post", new=_flaky
    ), patch(
        "app.services.lead_dispatcher.asyncio.sleep", new=AsyncMock()
    ):
        out = await lead_dispatcher.dispatch({"x": 1})
    assert out is True
    assert attempts["n"] == 2


# ─── Route integration ───────────────────────────────────────────────


class LeadRouteTests(unittest.TestCase):
    # setUp removed — autouse fixture in conftest.py.

    def test_lead_with_consent_returns_lead_accepted(self):
        with patch.object(
            lead_dispatcher.settings, "LEAD_WEBHOOK_URL", ""
        ):
            with TestClient(app) as client:
                r = client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "contact": {
                        "name": "Test",
                        "email": "t@example.com",
                        "phone": "+1",
                    },
                    "consent_to_share": True,
                    "locale": "tr-TR",
                })
        body = r.json()
        self.assertEqual(body["type"], "RESULT")
        self.assertEqual(body["payload"]["code"], "LEAD_ACCEPTED")
        self.assertTrue(body["payload"]["consent_to_share"])
        # No webhook configured → reported truthfully.
        self.assertFalse(body["payload"]["webhook_delivered"])
        self.assertFalse(body["payload"]["webhook_configured"])

    def test_lead_clinic_procedure_mismatch_returns_error(self):
        with TestClient(app) as client:
            r = client.post("/v1/quote/lead", json={
                "procedure_id": "lasik",
                "clinic_id": "clinic_ankara_cardiac",  # doesn't offer LASIK
                "contact": {},
                "consent_to_share": False,
            })
        self.assertEqual(
            r.json()["payload"]["code"], "CLINIC_PROCEDURE_MISMATCH"
        )

    def test_lead_dispatches_webhook_when_configured(self):
        # Simulate a configured webhook returning 200.
        async def _fake_dispatch(payload):  # noqa: ARG001
            return True

        with patch.object(
            lead_dispatcher.settings, "LEAD_WEBHOOK_URL",
            "https://hooks.example.com/x",
        ), patch(
            "app.services.lead_dispatcher.dispatch",
            new=_fake_dispatch,
        ):
            with TestClient(app) as client:
                r = client.post("/v1/quote/lead", json={
                    "procedure_id": "fue_hair_transplant",
                    "clinic_id": "clinic_istanbul_aesthetics_one",
                    "contact": {"name": "T"},
                    "consent_to_share": True,
                })
        body = r.json()
        self.assertTrue(body["payload"]["webhook_configured"])
        self.assertTrue(body["payload"]["webhook_delivered"])
