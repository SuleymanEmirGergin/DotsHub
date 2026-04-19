"""Branch coverage for app.middleware.security_headers.

Three branches to exercise:
  - `app.state.app_env == "production"` → all five headers set.
  - any other value ("development", "staging", arbitrary) → untouched.
  - attribute missing entirely → `getattr` default kicks in →
    treated as "development" → untouched.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security_headers import SecurityHeadersMiddleware


SECURITY_HEADERS = [
    "X-Content-Type-Options",
    "X-Frame-Options",
    "X-XSS-Protection",
    "Referrer-Policy",
    "Strict-Transport-Security",
]


def _build_app(app_env):
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    if app_env is not None:
        app.state.app_env = app_env

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


def test_production_sets_all_security_headers():
    client = TestClient(_build_app("production"))
    r = client.get("/ping")
    assert r.status_code == 200
    for h in SECURITY_HEADERS:
        assert h in r.headers, f"{h} missing in prod response"
    # Spot-check a couple of values so a silent downgrade surfaces.
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "max-age=31536000" in r.headers["Strict-Transport-Security"]


def test_non_production_env_does_not_set_security_headers():
    client = TestClient(_build_app("development"))
    r = client.get("/ping")
    assert r.status_code == 200
    for h in SECURITY_HEADERS:
        assert h not in r.headers, f"{h} leaked in dev response"


def test_staging_env_also_skipped():
    # Explicit check that "production" is the only env that opts in —
    # anything else (staging, test, arbitrary) stays bare.
    client = TestClient(_build_app("staging"))
    r = client.get("/ping")
    for h in SECURITY_HEADERS:
        assert h not in r.headers


def test_missing_app_env_defaults_to_development():
    # `getattr(request.app.state, "app_env", None) or "development"` —
    # the middleware never raises even when main.py forgot to set it.
    client = TestClient(_build_app(None))
    r = client.get("/ping")
    assert r.status_code == 200
    for h in SECURITY_HEADERS:
        assert h not in r.headers
