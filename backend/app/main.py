"""FastAPI application entry point.

Thin app factory: build FastAPI(), then delegate to app.setup.* for
lifespan / middleware / routes / health. The split lives there so a
change to (e.g.) rate-limit middleware doesn't make engineers scroll
through unrelated lifespan + observer + route-include code.

History: this file used to be 570 lines of mixed concerns. Session 17
R6 extracted middleware → app/setup/middleware.py, routes →
app/setup/routes.py, /health → app/setup/health.py, lifespan →
app/setup/lifespan.py. main.py is now a wiring sheet.
"""
import logging

from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.observability import init_sentry, setup_metrics

setup_logging()
logger = logging.getLogger(__name__)

# Sentry init BEFORE FastAPI() so the SDK can hook into the ASGI
# lifecycle via the Starlette integration. No-op when SENTRY_DSN is
# unset. See app/observability/sentry_init.py for the before_send PII
# scrubber.
init_sentry()

from app.setup import (
    lifespan,
    register_health,
    register_middlewares,
    register_routes,
)


app = FastAPI(
    title="Dotshub - Ön-Triyaj Asistanı API",
    description="Agentic AI tabanlı akıllı ön-triyaj sistemi (V4 — unified triage turn)",
    version="4.0.0",
    lifespan=lifespan,
)

# Prometheus /metrics + default HTTP histograms. Custom counters
# (capability gate strips, rate-limit decisions, envelope type counts,
# health-tourism funnel) register at module-import time via
# app.observability.metrics — same /metrics scrape returns both.
setup_metrics(app)

register_middlewares(app)
register_routes(app)
register_health(app)
