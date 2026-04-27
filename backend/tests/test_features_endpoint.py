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

    def test_returns_consent_block(self):
        """Mobile intro reads notice_version + versions to detect stale
        consent and force re-acceptance without a client release."""
        with TestClient(app) as client:
            res = client.get("/v1/config/features")
        data = res.json()
        self.assertIn("consent", data)
        consent = data["consent"]
        self.assertIn("notice_version", consent)
        self.assertIn("versions", consent)
        # The four whitelisted consent_types from app.api.routes.consent
        # MUST all be carried — a mismatch with that whitelist would
        # let the mobile app reference a type the backend rejects.
        for consent_type in (
            "terms_general",
            "health_data_processing",
            "push_notifications",
            "summary_email",
        ):
            self.assertIn(consent_type, consent["versions"])
            # Versions are short strings (e.g. "v1.0"), not None.
            self.assertIsInstance(consent["versions"][consent_type], str)
            self.assertTrue(consent["versions"][consent_type])

    def test_consent_version_settings_override_surface(self):
        """A bump to CONSENT_VERSION_HEALTH_DATA in settings is reflected
        in the /features payload — the mechanism mobile uses to detect
        stale consent and re-prompt the user."""
        with patch("app.main.settings.CONSENT_VERSION_HEALTH_DATA", "v2.0"):
            with patch("app.main.settings.PRIVACY_NOTICE_VERSION", "v0.3"):
                with TestClient(app) as client:
                    res = client.get("/v1/config/features")
        data = res.json()
        self.assertEqual(
            data["consent"]["versions"]["health_data_processing"], "v2.0"
        )
        self.assertEqual(data["consent"]["notice_version"], "v0.3")


if __name__ == "__main__":
    unittest.main()
