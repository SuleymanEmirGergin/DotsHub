"""Tests for GET /v1/config/features — the mobile startup contract.

Scope: verify the endpoint shape stays stable and the M4 client_version
block is carried through settings. Any change to the payload shape
here breaks mobile startup, so treat a test edit here as a protocol
change that needs a mobile counterpart.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.version_gating import KNOWN_CAPABILITIES


class FeaturesEndpointTests(unittest.TestCase):
    def test_returns_llm_flags_and_version_policy(self):
        with TestClient(app) as client:
            res = client.get("/v1/config/features")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Legacy flags — mobile pre-M4 relies on these.
        self.assertIn("llm_nlu_enabled", data)
        self.assertIn("llm_explain_enabled", data)
        # M4 version-gate block.
        self.assertIn("client_version", data)
        cv = data["client_version"]
        for key in ("min", "latest", "mode", "update_url_ios", "update_url_android"):
            self.assertIn(key, cv)
        self.assertIn(cv["mode"], {"off", "warn", "block"})

    def test_honors_enforcement_mode_override(self):
        """A settings flip to 'block' surfaces through the endpoint."""
        with patch("app.main.settings.CLIENT_VERSION_ENFORCEMENT", "block"):
            with patch("app.main.settings.MIN_CLIENT_VERSION", "1.2.0"):
                with TestClient(app) as client:
                    res = client.get("/v1/config/features")
        data = res.json()
        self.assertEqual(data["client_version"]["mode"], "block")
        self.assertEqual(data["client_version"]["min"], "1.2.0")

    def test_update_urls_null_when_empty(self):
        """Empty settings strings should serialize as null, not ''.
        The mobile client checks `url != null` to decide whether to
        show the store link — an empty string would render a broken
        'Güncelle' button linking nowhere."""
        with patch("app.main.settings.CLIENT_VERSION_UPDATE_URL_IOS", ""):
            with patch("app.main.settings.CLIENT_VERSION_UPDATE_URL_ANDROID", ""):
                with TestClient(app) as client:
                    res = client.get("/v1/config/features")
        data = res.json()
        self.assertIsNone(data["client_version"]["update_url_ios"])
        self.assertIsNone(data["client_version"]["update_url_android"])


class CapabilitiesEndpointTests(unittest.TestCase):
    """GET /v1/config/capabilities — runtime capability discovery.

    Returns the canonical token list the server understands. The mobile
    build can compare this to its `CLIENT_CAPABILITIES` constant and log
    drift (token unknown to server, or token server knows but client
    doesn't advertise) without needing a CI run.
    """

    def test_returns_known_capability_tokens_sorted(self):
        with TestClient(app) as client:
            res = client.get("/v1/config/capabilities")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("capabilities", data)
        self.assertIn("count", data)
        # Byte-stable: sorted alphabetically.
        self.assertEqual(data["capabilities"], sorted(KNOWN_CAPABILITIES))
        self.assertEqual(data["count"], len(KNOWN_CAPABILITIES))

    def test_includes_streaming_envelope_token(self):
        # A1's new token must appear here so mobile drift detection sees
        # it. This is a contract-level smoke test — if streaming_envelope
        # disappears from the registry, this fails loudly.
        with TestClient(app) as client:
            res = client.get("/v1/config/capabilities")
        self.assertIn("streaming_envelope", res.json()["capabilities"])

    def test_capabilities_response_is_byte_stable_across_calls(self):
        """The endpoint should return identical bytes on repeated calls
        with the same registry — required for HTTP caching and log
        diffing."""
        with TestClient(app) as client:
            r1 = client.get("/v1/config/capabilities")
            r2 = client.get("/v1/config/capabilities")
        self.assertEqual(r1.content, r2.content)


if __name__ == "__main__":
    unittest.main()
