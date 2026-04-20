"""Prometheus metrics wiring — /metrics endpoint + counter behaviour.

Contract:
  - `setup_metrics(app)` mounts `/metrics` and returns 200 on scrape.
  - Default HTTP series (from prometheus-fastapi-instrumentator) ship
    out of the box.
  - Custom counters/histograms declared in `app.observability.metrics`
    appear in the scrape text once a single label combination has been
    touched (prometheus_client lazily materialises labelled children).
  - The helper functions in version_gating + rate_limit actually
    increment their counters end-to-end, so the wiring we documented in
    metrics.py's docstring ("mounted via setup_metrics…") is not just
    aspirational.

The scrape format (text/plain with # HELP + # TYPE lines + metric
samples) is defined by prometheus_client — we only assert on substring
presence, not exact bytes, so prometheus library upgrades don't flap
this test.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability import (
    capability_gate_bytes_saved_total,
    capability_gate_filtered_total,
    confidence_score,
    rate_limit_hits_total,
    setup_metrics,
    triage_envelope_total,
)


def _app_with_metrics() -> FastAPI:
    app = FastAPI()
    setup_metrics(app)

    @app.get("/dummy")
    async def _dummy() -> dict[str, bool]:
        return {"ok": True}

    return app


# ─── /metrics endpoint ─────────────────────────────────────────────

def test_metrics_endpoint_returns_200():
    """`setup_metrics(app)` mounts a working /metrics scrape target."""
    app = _app_with_metrics()
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    # Content-type is prometheus exposition format (text/plain with
    # version=0.0.4) — a stable contract across prometheus_client 0.x
    # versions. Partial-match only so a minor-version bump doesn't
    # flap the test.
    assert r.headers["content-type"].startswith("text/plain")


def test_metrics_endpoint_exposes_default_http_series():
    """`prometheus-fastapi-instrumentator` ships the HTTP series."""
    app = _app_with_metrics()
    c = TestClient(app)
    # Make one request so the instrumentator gets a sample to record.
    c.get("/dummy")
    r = c.get("/metrics")
    # `http_request_duration_seconds` is the default histogram name.
    assert "http_request_duration_seconds" in r.text


def test_metrics_endpoint_ignores_self_scrape():
    """/metrics and /health are excluded from instrumentation so the
    scraper can't produce an infinite feedback loop."""
    app = _app_with_metrics()
    c = TestClient(app)
    # Scrape once to produce samples. The scrape itself must not show
    # up as a `/metrics` handler row (excluded_handlers).
    c.get("/metrics")
    r = c.get("/metrics")
    # The scraped text will include `handler="/dummy"` once we've hit
    # it, but never `handler="/metrics"` because it's excluded. Guard
    # strictly: if the framework changes defaults, this test catches
    # the regression.
    assert 'handler="/metrics"' not in r.text


# ─── Custom counters exposed on scrape ─────────────────────────────

def test_custom_counters_appear_on_scrape_after_inc():
    """Custom counters register onto the default prometheus_client
    registry at import time, so the same /metrics scrape returns both
    the default HTTP series and our domain metrics once we touch a
    label combination."""
    app = _app_with_metrics()
    c = TestClient(app)
    triage_envelope_total.labels(envelope_type="RESULT").inc()
    capability_gate_filtered_total.labels(
        envelope_type="RESULT",
        caps_missing="curated_meta",
    ).inc()
    capability_gate_bytes_saved_total.inc(128)
    rate_limit_hits_total.labels(bucket="default", outcome="allowed").inc()
    confidence_score.observe(0.72)

    r = c.get("/metrics")
    text = r.text
    assert "triage_envelope_total" in text
    assert "capability_gate_filtered_total" in text
    assert "capability_gate_bytes_saved_total" in text
    assert "rate_limit_hits_total" in text
    # Histogram produces `<name>_bucket`, `<name>_sum`, `<name>_count`.
    assert "confidence_score_bucket" in text


# ─── End-to-end: helpers actually increment the counters ───────────

def test_rate_limit_helper_bumps_counter():
    """check_rate_limit() flows through _inc_rate_limit() to the
    default-bucket counter. Regression guard for the wire-up."""
    from app import rate_limit as rl

    rl._BUCKETS.clear()

    key = "metrics-test-key"
    before = rate_limit_hits_total.labels(
        bucket="default", outcome="allowed",
    )._value.get()
    allowed, _, _ = rl.check_rate_limit(key)
    after = rate_limit_hits_total.labels(
        bucket="default", outcome="allowed",
    )._value.get()

    assert allowed is True
    assert after == before + 1.0

    rl._BUCKETS.clear()


def test_capability_gate_helpers_bump_counters():
    """_inc_triage_envelope + _inc_gate_counters land on the right
    counters with the right labels. The middleware-level test suite
    already covers the strip path; this zooms in on the helpers so a
    label-typo regression surfaces even without the FastAPI harness."""
    from app.version_gating import _inc_gate_counters, _inc_triage_envelope

    env_before = triage_envelope_total.labels(
        envelope_type="EMERGENCY",
    )._value.get()
    _inc_triage_envelope("EMERGENCY")
    env_after = triage_envelope_total.labels(
        envelope_type="EMERGENCY",
    )._value.get()
    assert env_after == env_before + 1.0

    gate_before = capability_gate_filtered_total.labels(
        envelope_type="EMERGENCY",
        caps_missing="curated_meta,emergency_specialty",
    )._value.get()
    bytes_before = capability_gate_bytes_saved_total._value.get()
    _inc_gate_counters(
        "EMERGENCY",
        frozenset({"curated_meta", "emergency_specialty"}),
        bytes_saved=256,
    )
    gate_after = capability_gate_filtered_total.labels(
        envelope_type="EMERGENCY",
        caps_missing="curated_meta,emergency_specialty",
    )._value.get()
    bytes_after = capability_gate_bytes_saved_total._value.get()
    assert gate_after == gate_before + 1.0
    assert bytes_after == bytes_before + 256.0
