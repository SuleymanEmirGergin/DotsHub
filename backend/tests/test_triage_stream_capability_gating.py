"""SSE capability gating: /v1/triage/stream must filter the envelope
event payload against ``X-Client-Capabilities`` the same way
``CapabilityGateMiddleware`` does for /v1/triage/turn.

Why this exists:
    The middleware's content-type guard skips ``text/event-stream``
    responses, which means SSE bypassed capability gating entirely
    until this fix. An old client that didn't advertise
    ``curated_meta`` would still receive curated fields over SSE — a
    real contract leak. These tests pin both directions: with caps the
    gated fields appear, without caps they're stripped. Same envelope,
    different transport — same shape.
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import triage as triage_routes
from app.main import app
from app.models.schemas import Envelope, Meta


def _meta() -> Meta:
    return Meta(
        disclaimer_tr="Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır.",
        timestamp=datetime.now(timezone.utc),
    )


def _result_envelope_with_curated() -> Envelope:
    return Envelope(
        type="RESULT",
        session_id="sse-session",
        turn_index=1,
        payload={
            "urgency": "ROUTINE",
            "recommended_specialty": {"id": "neurology", "name_tr": "Nöroloji"},
            "top_conditions": [
                {
                    "disease_label": "Migren",
                    "score_0_1": 0.71,
                    "icd10": "G43",
                    "disease_description_tr": "Tek taraflı zonklayıcı baş ağrısı",
                    "self_care_tr": ["sessiz oda"],
                }
            ],
            "doctor_ready_summary_tr": [],
            "safety_notes_tr": [],
        },
        meta=_meta(),
    )


def _emergency_envelope_with_specialty() -> Envelope:
    return Envelope(
        type="EMERGENCY",
        session_id="sse-session-em",
        turn_index=1,
        payload={
            "urgency": "EMERGENCY",
            "reason_tr": "Şiddetli göğüs ağrısı + nefes darlığı",
            "instructions_tr": ["112"],
            "recommended_specialty": {"id": "emergency", "name_tr": "Acil Tıp"},
        },
        meta=_meta(),
    )


def _parse_envelope_event(body: str) -> dict:
    """Find the ``event: envelope\\ndata: {...}`` block and return the
    decoded JSON payload. SSE delimits events with double newlines."""
    for chunk in body.split("\n\n"):
        lines = chunk.splitlines()
        if not lines or lines[0] != "event: envelope":
            continue
        for line in lines[1:]:
            if line.startswith("data: "):
                return json.loads(line[len("data: ") :])
    raise AssertionError(f"no envelope event in SSE body:\n{body}")


def _post_stream(client: TestClient, headers: dict | None = None):
    return client.post(
        "/v1/triage/stream",
        json={
            "session_id": None,
            "locale": "tr-TR",
            "user_message": "Başım ağrıyor",
        },
        headers=headers or {},
    )


class SSECapabilityGatingTests(unittest.TestCase):
    def test_old_client_without_caps_does_not_see_curated_fields(self):
        stub = _result_envelope_with_curated()
        with patch.object(
            triage_routes, "_handle_turn_supabase", return_value=stub
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = _post_stream(client)  # no X-Client-Capabilities
        self.assertEqual(r.status_code, 200, r.text)
        envelope = _parse_envelope_event(r.text)
        top = envelope["payload"]["top_conditions"][0]
        # baseline routing/score still visible
        self.assertEqual(top["disease_label"], "Migren")
        self.assertAlmostEqual(top["score_0_1"], 0.71)
        # curated fields stripped
        self.assertNotIn("icd10", top)
        self.assertNotIn("disease_description_tr", top)
        self.assertNotIn("self_care_tr", top)

    def test_capable_client_with_curated_meta_sees_curated_fields(self):
        stub = _result_envelope_with_curated()
        with patch.object(
            triage_routes, "_handle_turn_supabase", return_value=stub
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = _post_stream(
                    client,
                    headers={"X-Client-Capabilities": "curated_meta"},
                )
        self.assertEqual(r.status_code, 200, r.text)
        envelope = _parse_envelope_event(r.text)
        top = envelope["payload"]["top_conditions"][0]
        self.assertEqual(top["icd10"], "G43")
        self.assertIn("disease_description_tr", top)

    def test_old_client_emergency_does_not_see_recommended_specialty(self):
        stub = _emergency_envelope_with_specialty()
        with patch.object(
            triage_routes, "_handle_turn_supabase", return_value=stub
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = _post_stream(client)
        self.assertEqual(r.status_code, 200, r.text)
        envelope = _parse_envelope_event(r.text)
        # routing fields still visible
        self.assertEqual(envelope["payload"]["urgency"], "EMERGENCY")
        self.assertIn("reason_tr", envelope["payload"])
        # gated specialty stripped on EMERGENCY without cap
        self.assertNotIn("recommended_specialty", envelope["payload"])

    def test_capable_client_emergency_sees_recommended_specialty(self):
        stub = _emergency_envelope_with_specialty()
        with patch.object(
            triage_routes, "_handle_turn_supabase", return_value=stub
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = _post_stream(
                    client,
                    headers={
                        "X-Client-Capabilities": "emergency_specialty",
                    },
                )
        self.assertEqual(r.status_code, 200, r.text)
        envelope = _parse_envelope_event(r.text)
        self.assertEqual(
            envelope["payload"]["recommended_specialty"]["id"], "emergency"
        )

    def test_streaming_envelope_token_alone_does_not_unlock_curated_fields(
        self,
    ):
        # streaming_envelope is a transport-mode advertisement; alone it
        # must NOT grant access to curated_meta-gated fields.
        stub = _result_envelope_with_curated()
        with patch.object(
            triage_routes, "_handle_turn_supabase", return_value=stub
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = _post_stream(
                    client,
                    headers={"X-Client-Capabilities": "streaming_envelope"},
                )
        self.assertEqual(r.status_code, 200, r.text)
        envelope = _parse_envelope_event(r.text)
        top = envelope["payload"]["top_conditions"][0]
        self.assertNotIn("icd10", top)
        self.assertNotIn("self_care_tr", top)


if __name__ == "__main__":
    unittest.main()
