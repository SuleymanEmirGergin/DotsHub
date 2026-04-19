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
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

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
