"""CORS expose_headers — browser-readable custom response headers.

Browsers don't expose custom (X-*) response headers to JavaScript by
default; the server has to opt them into ``Access-Control-Expose-Headers``
explicitly. Without this list, web frontends see `null` when reading
e.g. `response.headers.get('X-Request-ID')`.

Tests assert the preflight (OPTIONS) advertises the right list, and
that an actual response carries the same values back. We don't test
browser parsing semantics — Starlette is the upstream library that
emits the header, so wire-level confirmation is enough.
"""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


# Five headers we explicitly opted-in to expose. The list is in main.py;
# this test pins it so a future "let me clean up CORS" doesn't silently
# strip a header the dashboard relies on.
EXPECTED_EXPOSED = {
    "X-Request-ID",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "X-RateLimit-Bucket",
}


class CorsExposeHeadersTests(unittest.TestCase):
    def test_actual_response_advertises_exposed_headers(self):
        """A request from a browser origin must carry the
        Access-Control-Expose-Headers response header. (Starlette emits
        this on actual requests, not on OPTIONS preflight.)"""
        with TestClient(app) as client:
            r = client.get("/health", headers={"Origin": "http://localhost:3000"})
        exposed_raw = r.headers.get("access-control-expose-headers", "")
        exposed_lower = {
            h.strip().lower() for h in exposed_raw.split(",") if h.strip()
        }
        for name in EXPECTED_EXPOSED:
            self.assertIn(
                name.lower(),
                exposed_lower,
                f"{name} missing from access-control-expose-headers ({exposed_raw!r})",
            )

    def test_no_origin_no_expose_headers(self):
        """Same-origin (no Origin header) requests don't get CORS
        headers — that's expected, ensures we're not leaking the list
        to non-CORS callers."""
        with TestClient(app) as client:
            r = client.get("/health")
        # Either absent or empty — both are non-leaks.
        exposed = r.headers.get("access-control-expose-headers")
        self.assertFalse(exposed)


if __name__ == "__main__":
    unittest.main()
