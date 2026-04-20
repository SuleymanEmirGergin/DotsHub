"""Observability integrations — Sentry (errors), Prometheus (metrics)."""
from app.observability.metrics import (
    capability_gate_bytes_saved_total,
    capability_gate_filtered_total,
    confidence_score,
    rate_limit_hits_total,
    setup_metrics,
    triage_envelope_total,
)
from app.observability.sentry_init import before_send, init_sentry

__all__ = [
    "before_send",
    "capability_gate_bytes_saved_total",
    "capability_gate_filtered_total",
    "confidence_score",
    "init_sentry",
    "rate_limit_hits_total",
    "setup_metrics",
    "triage_envelope_total",
]
