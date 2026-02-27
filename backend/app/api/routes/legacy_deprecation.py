"""Helpers for legacy route deprecation metadata and observability."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Response

DEPRECATION_HEADER_VALUE = "true"
SUNSET_HEADER_VALUE = "Tue, 30 Jun 2026 23:59:59 GMT"
SUCCESSOR_LINK_HEADER_VALUE = '<docs/openapi_orchestrator.yaml>; rel="successor-version"'


def apply_legacy_deprecation_headers(response: Response) -> None:
    """Attach standard deprecation headers to legacy route responses."""
    response.headers["Deprecation"] = DEPRECATION_HEADER_VALUE
    response.headers["Sunset"] = SUNSET_HEADER_VALUE
    response.headers["Link"] = SUCCESSOR_LINK_HEADER_VALUE


def log_legacy_route_hit(
    logger: logging.Logger,
    route: str,
    session_id: Optional[str] = None,
) -> None:
    """Emit a structured log line for legacy route traffic tracking."""
    logger.info(
        "legacy_route_hit route=%s session_id=%s",
        route,
        session_id or "-",
    )
