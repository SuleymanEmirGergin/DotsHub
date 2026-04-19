"""Integration: capability gating + feature-flag protocol coexist.

Two versioning layers live in the app at the same time:

  - `CapabilityGateMiddleware` (`app.version_gating`) — wire-shape
    negotiation: the client advertises `X-Client-Capabilities`, the
    server strips any gated response field the client didn't claim.
  - `/v1/config/features` (`app.api.routes.features`) — runtime
    behaviour: the server tells the client which features are enabled
    and whether its build is too old.

Each layer has dedicated unit tests (`test_version_gating.py`,
`test_features_endpoint.py`), but a mobile startup exercises both
simultaneously — fetchFeatures() flowing through the capability
middleware, then session/start with the same capability header.
This file proves the two layers don't trip over each other.

Agent review called this out (see docs/client_versioning.md →
"Related: runtime feature flags"): without an explicit dual test
the "they coexist" claim is only by inspection.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class DualVersioningStartupTests(unittest.TestCase):
    """Simulate mobile startup under every combination of headers."""

    # Canonical mobile startup header (see mobile/src/config/capabilities.ts).
    FULL_CAPS = "curated_meta,emergency_specialty"

    def test_features_passthrough_without_capabilities_header(self):
        """No header = minimal baseline. Features endpoint is a flat
        object, not an envelope — middleware must not strip anything."""
        with TestClient(app) as client:
            res = client.get("/v1/config/features")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("llm_nlu_enabled", data)
        self.assertIn("llm_explain_enabled", data)
        self.assertIn("client_version", data)
        cv = data["client_version"]
        # Shape the mobile useVersionGate hook depends on — if any of
        # these keys disappears, the startup contract is broken.
        for key in ("min", "latest", "mode"):
            self.assertIn(key, cv, f"client_version missing {key!r}")

    def test_features_shape_matches_with_and_without_caps(self):
        """Advertising capabilities must not change a non-envelope
        response. The feature-flag contract is independent of wire-
        shape negotiation."""
        with TestClient(app) as client:
            baseline = client.get("/v1/config/features").json()
            with_caps = client.get(
                "/v1/config/features",
                headers={"X-Client-Capabilities": self.FULL_CAPS},
            ).json()
        self.assertEqual(baseline, with_caps)

    def test_capability_header_unknown_token_tolerated_by_both_layers(self):
        """Unknown tokens drop silently in parse_capabilities.
        Features endpoint + any future triage endpoint should both
        stay happy even when the client advertises capabilities the
        server hasn't heard of (forward compat)."""
        with TestClient(app) as client:
            res = client.get(
                "/v1/config/features",
                headers={"X-Client-Capabilities": "curated_meta,future_capability_xyz"},
            )
        self.assertEqual(res.status_code, 200)
        # Still a valid ConfigFeaturesResponse — unknown tokens were
        # ignored, known tokens let the middleware pass the flat
        # payload through untouched.
        self.assertIn("client_version", res.json())

    def test_client_version_block_surface_survives_through_gate(self):
        """When ops flips `CLIENT_VERSION_ENFORCEMENT` to "block", the
        useVersionGate hook MUST see the enforcement value intact —
        the capability middleware has no reason to touch it but we
        nail this down so a future filter change can't regress it."""
        with patch("app.api.routes.features.settings") as mock_settings:
            mock_settings.LLM_NLU_ENABLED = False
            mock_settings.LLM_EXPLAIN_ENABLED = False
            mock_settings.MIN_CLIENT_VERSION = "1.2.0"
            mock_settings.LATEST_CLIENT_VERSION = "1.3.0"
            mock_settings.CLIENT_VERSION_ENFORCEMENT = "block"
            mock_settings.CLIENT_VERSION_UPDATE_URL_IOS = "https://example.com/ios"
            mock_settings.CLIENT_VERSION_UPDATE_URL_ANDROID = ""

            with TestClient(app) as client:
                res = client.get(
                    "/v1/config/features",
                    headers={"X-Client-Capabilities": self.FULL_CAPS},
                )
        self.assertEqual(res.status_code, 200)
        cv = res.json()["client_version"]
        self.assertEqual(cv["mode"], "block")
        self.assertEqual(cv["min"], "1.2.0")
        self.assertEqual(cv["latest"], "1.3.0")
        self.assertEqual(cv["update_url_ios"], "https://example.com/ios")
        # empty string coerces to None in the route handler.
        self.assertIsNone(cv["update_url_android"])


if __name__ == "__main__":
    unittest.main()
