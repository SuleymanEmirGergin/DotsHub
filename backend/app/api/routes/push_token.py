"""
Push token registration — mobile app registers Expo Push Token with backend.

POST /v1/triage/push-token   — register / update token
DELETE /v1/triage/push-token — unregister (deactivate) token
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["Triage"])
_PROD_ENVS = {"production", "prod"}
_PUSH_TOKEN_FAILURE_COUNTS: dict[str, int] = {"register": 0, "unregister": 0}


class PushTokenRequest(BaseModel):
    expo_push_token: str = Field(..., min_length=10, max_length=256)
    device_id: str = Field(..., min_length=1, max_length=128)
    platform: str = Field(default="unknown", max_length=20)
    locale: str = Field(default="tr-TR", max_length=10)


class PushTokenResponse(BaseModel):
    ok: bool = True


def _is_fail_open_mode() -> bool:
    return str(settings.APP_ENV or "").strip().lower() not in _PROD_ENVS


def _handle_push_persist_error(action: Literal["register", "unregister"], device_id: str, exc: Exception) -> None:
    _PUSH_TOKEN_FAILURE_COUNTS[action] = _PUSH_TOKEN_FAILURE_COUNTS.get(action, 0) + 1
    fail_open = _is_fail_open_mode()
    logger.warning(
        "push_token.persist_failed",
        extra={
            "metric_name": "push_token_persist_fail_total",
            "metric_value": 1,
            "action": action,
            "device_id": device_id,
            "app_env": settings.APP_ENV,
            "fail_open": fail_open,
            "failure_count": _PUSH_TOKEN_FAILURE_COUNTS[action],
            "error": str(exc),
        },
    )
    if fail_open:
        return
    raise HTTPException(
        status_code=503,
        detail={
            "code": "PUSH_TOKEN_PERSIST_FAILED",
            "message": "Push token could not be persisted",
            "action": action,
        },
    )


@router.post("/push-token", response_model=PushTokenResponse)
async def register_push_token(body: PushTokenRequest) -> PushTokenResponse:
    """Register or update an Expo Push Token for a device."""
    logger.info(
        "push_token.register",
        extra={
            "device_id": body.device_id,
            "token_prefix": body.expo_push_token[:20] + "...",
            "platform": body.platform,
        },
    )
    try:
        from app.push import register_token

        register_token(
            device_id=body.device_id,
            expo_token=body.expo_push_token,
            platform=body.platform,
            locale=body.locale,
        )
    except Exception as exc:
        _handle_push_persist_error("register", body.device_id, exc)
    return PushTokenResponse(ok=True)


class PushTokenDeleteRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=128)


@router.delete("/push-token", response_model=PushTokenResponse)
async def unregister_push_token(body: PushTokenDeleteRequest) -> PushTokenResponse:
    """Mark a device's push token as inactive."""
    logger.info("push_token.unregister", extra={"device_id": body.device_id})
    try:
        from app.push import unregister_token

        unregister_token(device_id=body.device_id)
    except Exception as exc:
        _handle_push_persist_error("unregister", body.device_id, exc)
    return PushTokenResponse(ok=True)
