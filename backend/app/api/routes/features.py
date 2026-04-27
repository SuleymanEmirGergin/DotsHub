"""Client startup feature-flag + version-gate endpoint.

`GET /v1/config/features` is the first API call every mobile build
makes. Two jobs:

1. Return the UI-gating flags (`llm_nlu_enabled`,
   `llm_explain_enabled`) the app uses before rendering the triage
   flow (KVKK/AI consent banner visibility, explain surface).
2. Return the `client_version` block the mobile `useVersionGate` hook
   (`mobile/src/hooks/useVersionGate.ts`) compares against
   `Constants.expoConfig.version` to decide warn vs block vs silent.
   The three-field contract — `min` / `latest` / `mode` — lets ops
   ship "warn" for a week, read the logs, then flip to "block"
   without a client release.

Kept separate from the triage capability header (`X-Client-
Capabilities`) protocol: capabilities describe wire-shape parsing,
this endpoint describes runtime behaviour. See
`docs/client_versioning.md` → "Related: runtime feature flags".

The response shape is locked down by
`backend/tests/test_features_endpoint.py` — the safety-critical CI
gate treats `app.core.config` as 100%-branch to keep the contract
from silently drifting.

`GET /v1/config/capabilities` is the discovery counterpart for the
capability-gating protocol: it returns the canonical token list the
server understands so mobile builds can detect drift at runtime
(client log + ops alert) instead of relying solely on the CI-time
`scripts/check_capability_drift.cjs` check.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.version_gating import KNOWN_CAPABILITIES

router = APIRouter()


@router.get("/config/features")
async def features() -> dict:
    return {
        "llm_nlu_enabled": settings.LLM_NLU_ENABLED,
        "llm_explain_enabled": settings.LLM_EXPLAIN_ENABLED,
        "client_version": {
            "min": settings.MIN_CLIENT_VERSION,
            "latest": settings.LATEST_CLIENT_VERSION,
            "mode": settings.CLIENT_VERSION_ENFORCEMENT,
            "update_url_ios": settings.CLIENT_VERSION_UPDATE_URL_IOS or None,
            "update_url_android": settings.CLIENT_VERSION_UPDATE_URL_ANDROID or None,
        },
    }


@router.get("/config/capabilities")
async def capabilities() -> dict:
    """Return the server's canonical capability registry.

    The list is sorted so the response body is byte-stable across
    requests (cache-friendly, easier to diff in client logs).
    """
    return {
        "capabilities": sorted(KNOWN_CAPABILITIES),
        "count": len(KNOWN_CAPABILITIES),
    }
