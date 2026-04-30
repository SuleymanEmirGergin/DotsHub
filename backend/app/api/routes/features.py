"""Client startup feature-flag + version-gate endpoint.

`GET /v1/config/features` is the first API call every mobile build
makes. Three jobs:

1. Return the UI-gating flags (`llm_nlu_enabled`,
   `llm_explain_enabled`) the app uses before rendering the triage
   flow (KVKK/AI consent banner visibility, explain surface).
2. Return the `client_version` block the mobile `useVersionGate` hook
   (`mobile/src/hooks/useVersionGate.ts`) compares against
   `Constants.expoConfig.version` to decide warn vs block vs silent.
   The three-field contract — `min` / `latest` / `mode` — lets ops
   ship "warn" for a week, read the logs, then flip to "block"
   without a client release.
3. Return the `consent` block: privacy-notice version + per-type
   consent versions. The mobile intro screen reads these and
   compares against the latest stored value in `consent_records`
   for the device — a mismatch forces re-acceptance without a
   mobile release. Source of truth lives in `app/core/config.py`
   (`PRIVACY_NOTICE_VERSION`, `CONSENT_VERSION_*`).

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
        # Voice intake (Wiro whisper-large-v3-turbo-turkish). Mobile
        # uses this to gate the MicButton — when false, the UI hides
        # the mic and falls back to typed input only. Backend still
        # rejects with 403 ASR_DISABLED if a request slips through.
        "asr_enabled": settings.LLM_ASR_ENABLED,
        "client_version": {
            "min": settings.MIN_CLIENT_VERSION,
            "latest": settings.LATEST_CLIENT_VERSION,
            "mode": settings.CLIENT_VERSION_ENFORCEMENT,
            "update_url_ios": settings.CLIENT_VERSION_UPDATE_URL_IOS or None,
            "update_url_android": settings.CLIENT_VERSION_UPDATE_URL_ANDROID or None,
        },
        "consent": {
            "notice_version": settings.PRIVACY_NOTICE_VERSION,
            "versions": {
                "terms_general": settings.CONSENT_VERSION_TERMS_GENERAL,
                "health_data_processing": settings.CONSENT_VERSION_HEALTH_DATA,
                "push_notifications": settings.CONSENT_VERSION_PUSH_NOTIFICATIONS,
                "summary_email": settings.CONSENT_VERSION_SUMMARY_EMAIL,
            },
        },
    }
