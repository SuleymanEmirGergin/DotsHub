"""Operator-only image generation endpoint.

POST /v1/admin/image/generate -- gated by ``x-admin-key`` header
matching ``ADMIN_API_KEY``. Generates clinic / marketing / before-after
illustration mockups via either ``nano_banana_image`` (Google) or
``gpt_image`` (OpenAI). NOT for patient-facing medical visualizations
(legal: KVKK + sağlık reklam mevzuatı).

The endpoint is sync — Wiro's image-gen task takes 10-60s and the
operator dashboard expects to render the result inline (no polling).
We keep the timeout generous (120s default at the wrapper layer).

Why a dedicated admin endpoint instead of leaving the wrappers
internal-only: the dashboard needs an HTTP surface to call. Exposing
``app/services/ai/nano_banana_image.py`` etc. directly via a generic
``/v1/ai/*`` route would be a credit-burning unauth surface; the
admin gate keeps cost contained while we figure out the dashboard's
quota / approval flow.

Reference images are accepted as URL only (no multipart upload yet).
The full upload pipeline (B-track) will land in a separate session;
URL-only is sufficient for the operator-side use case where source
images live in the clinic-asset bucket already.
"""
from __future__ import annotations

import logging
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.admin_auth import require_admin_key
from app.services.ai import gpt_image, nano_banana_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/image", tags=["Admin Image"])


def require_admin(x_admin_key: str | None = Header(default=None)):
    return require_admin_key(x_admin_key)


# ─── Request / Response models ──────────────────────────────────────


class ImageGenerateRequest(BaseModel):
    """Operator request for an image generation.

    Provider-specific fields are optional — the wrapper applies its
    own defaults when None. Validation enforces Pydantic enums for
    the small select-set fields (size, quality, aspect_ratio) so a
    typo fails locally with a 422 instead of round-tripping a Wiro
    400.
    """

    provider: Literal["nano_banana", "gpt_image"]
    prompt: str = Field(..., min_length=1, max_length=4000)
    reference_image_url: Optional[str] = None

    # nano_banana-only knobs (ignored for gpt_image)
    aspect_ratio: Optional[
        Literal[
            "", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
            "9:16", "16:9", "21:9",
        ]
    ] = None
    resolution: Optional[Literal["1K", "2K", "4K"]] = None
    safety_setting: Optional[
        Literal[
            "BLOCK_LOW_AND_ABOVE",
            "BLOCK_MEDIUM_AND_ABOVE",
            "BLOCK_ONLY_HIGH",
            "BLOCK_NONE",
            "OFF",
        ]
    ] = None

    # gpt_image-only knobs (ignored for nano_banana)
    size: Optional[Literal["auto", "1:1", "3:2", "2:3"]] = None
    quality: Optional[Literal["low", "medium", "high"]] = None
    samples: Optional[int] = Field(default=None, ge=1, le=10)
    output_format: Optional[Literal["png", "jpeg", "webp"]] = None
    output_compression: Optional[int] = Field(default=None, ge=0, le=100)


class ImageGenerateResponse(BaseModel):
    """One row per generated image. ``urls`` carry CDN paths returned
    by Wiro; the operator dashboard fetches them directly. ``elapsed_ms``
    is wall-clock end-to-end including poll latency."""

    urls: list[str]
    provider_used: str
    elapsed_ms: int


# ─── Route handler ──────────────────────────────────────────────────


@router.post("/generate", response_model=ImageGenerateResponse)
def generate_image(
    request: ImageGenerateRequest, admin=Depends(require_admin),  # noqa: ARG001
):
    """Dispatch to the requested provider. Returns ``ImageGenerateResponse``.

    Status codes:
      - 200: provider returned at least one URL.
      - 401: missing / invalid x-admin-key (raised by require_admin).
      - 422: Pydantic validation (bad provider name, out-of-range
        samples, prompt too long, etc.).
      - 503: provider's feature flag is off (operator hasn't enabled
        the wrapper yet).
      - 502: provider returned None — Wiro task failed / auth missing /
        empty output. Operator should check Sentry and llm_calls log
        for the underlying cause.
    """
    t_start = time.perf_counter()

    if request.provider == "nano_banana":
        if not nano_banana_image.is_enabled():
            raise HTTPException(
                status_code=503,
                detail=(
                    "nano_banana_image is disabled "
                    "(WIRO_NANO_BANANA_IMAGE_ENABLED=False)"
                ),
            )
        kwargs: dict = {"prompt": request.prompt}
        if request.reference_image_url is not None:
            kwargs["reference_image_url"] = request.reference_image_url
        if request.aspect_ratio is not None:
            kwargs["aspect_ratio"] = request.aspect_ratio
        if request.resolution is not None:
            kwargs["resolution"] = request.resolution
        if request.safety_setting is not None:
            kwargs["safety_setting"] = request.safety_setting
        urls = nano_banana_image.generate(**kwargs)
        provider_used = "nano_banana"
    else:  # gpt_image (Pydantic literal already enforced this)
        if not gpt_image.is_enabled():
            raise HTTPException(
                status_code=503,
                detail="gpt_image is disabled (WIRO_GPT_IMAGE_ENABLED=False)",
            )
        kwargs = {"prompt": request.prompt}
        if request.reference_image_url is not None:
            kwargs["input_image_url"] = request.reference_image_url
        if request.size is not None:
            kwargs["size"] = request.size
        if request.quality is not None:
            kwargs["quality"] = request.quality
        if request.samples is not None:
            kwargs["samples"] = request.samples
        if request.output_format is not None:
            kwargs["output_format"] = request.output_format
        if request.output_compression is not None:
            kwargs["output_compression"] = request.output_compression
        urls = gpt_image.generate(**kwargs)
        provider_used = "gpt_image"

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    if not urls:
        # Wrapper returns None on auth missing / task error / timeout /
        # empty output. The dashboard needs a non-200 here to skip
        # rendering an empty result; 502 fits because the upstream
        # (Wiro) failed to deliver.
        logger.warning(
            "admin_image.generate_returned_none provider=%s elapsed_ms=%d",
            provider_used, elapsed_ms,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                f"{provider_used} returned no images. "
                "Check Sentry breadcrumbs and llm_calls for root cause."
            ),
        )

    return ImageGenerateResponse(
        urls=urls,
        provider_used=provider_used,
        elapsed_ms=elapsed_ms,
    )
