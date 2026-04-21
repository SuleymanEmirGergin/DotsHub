"""Prometheus metrics — custom counters/histograms + /metrics endpoint.

Design:

- HTTP request count, latency histogram, and in-flight gauge are
  provided by `prometheus-fastapi-instrumentator`'s default
  instrumentation — see `setup_metrics(app)` below.
- Custom domain metrics (capability-gate strips, triage envelopes,
  confidence distribution, rate-limit outcomes) are defined at module
  scope so `Counter.inc()` / `Histogram.observe()` is cheap
  (module-level singletons, no per-request allocation).

Wiring:
- `main.py` calls `setup_metrics(app)` after FastAPI() construction
  — mounts /metrics via the instrumentator.
- `version_gating.py::CapabilityGateMiddleware` increments
  `capability_gate_filtered_total` + `capability_gate_bytes_saved_total`
  + `triage_envelope_total` when it actually strips a response.
- `rate_limit.py::check_*_rate_limit*` each increment
  `rate_limit_hits_total{bucket, outcome}` on every call.
- `triage_engine.py` (future) can observe `confidence_score` when a
  RESULT envelope is emitted.

If `SENTRY_DSN` / Prometheus target isn't configured at runtime, the
counters still accumulate locally — scrapers just never pick them up.
No branching on "is monitoring enabled" in the hot paths.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram

if TYPE_CHECKING:
    from fastapi import FastAPI


# ─── Custom domain metrics ──────────────────────────────────────────

# Counter — number of responses where the capability gate middleware
# stripped at least one gated field. High cardinality risk is bounded:
# envelope_type has 4 values (RESULT/EMERGENCY/QUESTION/ERROR) and
# caps_missing is the SORTED comma-joined set — finite (2^N for N
# known capabilities, currently N=2 → 3 non-full sets).
capability_gate_filtered_total = Counter(
    "capability_gate_filtered_total",
    "Responses where the capability gate stripped at least one field.",
    labelnames=("envelope_type", "caps_missing"),
)

# Counter — total bytes removed from response bodies by the capability
# gate. Lets ops see the aggregate bandwidth saved by old-client
# clipping.
capability_gate_bytes_saved_total = Counter(
    "capability_gate_bytes_saved_total",
    "Total response bytes removed by capability gate stripping.",
)

# Counter — triage envelope emissions by type. Drift-watch for
# EMERGENCY spike (likely real signal) or QUESTION stall (UX bug).
triage_envelope_total = Counter(
    "triage_envelope_total",
    "Triage envelope emissions (sampled at the capability-gate middleware).",
    labelnames=("envelope_type",),
)

# Counter — rate-limit decisions grouped by bucket + outcome. Sum
# tells you total traffic to that bucket; the denied fraction is the
# throttling pressure.
rate_limit_hits_total = Counter(
    "rate_limit_hits_total",
    "Rate-limit check decisions.",
    labelnames=("bucket", "outcome"),
)

# Histogram — confidence score distribution (0-1). Flat distribution
# is unhealthy (uncertain triage); sharp peak at 0.5 suggests a scoring
# plateau (tuning target). 10-bucket coarse grid by design.
confidence_score = Histogram(
    "confidence_score",
    "Confidence score on RESULT envelopes.",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Counter — LLM NLU call outcomes. The in-memory rolling window in
# `services/llm_nlu::_health_monitor_observe` is what drives the
# webhook alert (latency-critical path). Without a Prometheus-side
# view we had no long-term success-rate history in Grafana — this
# counter closes that gap. Webhook remains the low-latency paging
# channel; Grafana reads from here for trend lines and a formal
# rule-based alert (see config/grafana/alerts/backend-health.yaml
# `LLMNluSuccessRateLow`).
#
# Label cardinality (bounded):
#   - `success` ∈ {"true", "false"} — 2 values (stringified bool so
#     labels stay consistent with Prometheus conventions).
#   - `error_type` is the short string the LLM client tags on
#     failures: "timeout" / "rate_limit" / "http_error" /
#     "schema_error" / "provider_error" / "" (for success). Bounded
#     to ~6 values by the existing client-side classification in
#     services/llm_nlu.py.
llm_nlu_calls_total = Counter(
    "llm_nlu_calls_total",
    "LLM NLU call outcomes (success/failure with classified error type).",
    labelnames=("success", "error_type"),
)

# Counter — Supabase DB call outcomes. Counts each invocation of a
# Supabase wrapper in app/db.py + opt-in callers via
# `_timed_supabase`. Closes the gap called out in Session 11's
# OBSERVABILITY.md "latency proxy" commentary — `TriageEndpointLatencyRegression`
# has been a stand-in for Supabase health since we lacked native
# DB metrics. This counter + the histogram below replace the proxy
# for the high-volume write paths (session upsert, event insert,
# feedback insert). Admin / read paths stay on the proxy for now
# and can migrate incrementally without a schema change.
#
# Label cardinality (bounded):
#   - `operation` ∈ a small enumerated set of names we wrap with
#     `_timed_supabase`. Adding a new operation is additive and
#     visible in the code diff — no unbounded label risk.
#   - `outcome` ∈ {"success", "error"} — 2 values.
supabase_db_calls_total = Counter(
    "supabase_db_calls_total",
    "Supabase client call outcomes (success / error) keyed by operation name.",
    labelnames=("operation", "outcome"),
)

# Histogram — Supabase DB call latency. Bucket layout covers the
# realistic range (sub-second happy path, multi-second degradation,
# 5s+ incident territory). Tail beyond 5s is truncated into the
# implicit `+Inf` bucket — if that bucket fills, Supabase is dead
# and the rate / error alerts have already fired.
supabase_db_latency_seconds = Histogram(
    "supabase_db_latency_seconds",
    "Supabase client call latency (seconds) keyed by operation name.",
    labelnames=("operation",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)


# ─── Setup ─────────────────────────────────────────────────────────

def setup_metrics(app: "FastAPI") -> None:
    """Mount /metrics and register default HTTP instrumentation.

    Uses `prometheus-fastapi-instrumentator` for the standard HTTP
    series (requests_total, request_duration_seconds, inflight).
    Custom metrics above are registered on the default
    prometheus_client registry at import time, so the same /metrics
    scrape returns both.
    """
    # Lazy import so test environments that don't install the package
    # can still import the custom counters by name.
    from prometheus_fastapi_instrumentator import Instrumentator

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        # Don't instrument /metrics or /health — pure noise + infinite
        # self-scrape feedback loop.
        excluded_handlers=["/metrics", "/health"],
    )
    instrumentator.instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
        tags=["Monitoring"],
    )
