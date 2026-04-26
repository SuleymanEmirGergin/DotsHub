"""Google nano-banana-pro image gen/edit wrapper via Wiro.ai.

Image-out wrapper — different shape from the text-out services in this
package. ``generate()`` returns ``Optional[list[str]]``: a list of CDN
URLs for the generated images, or ``None`` on any failure.

Use cases for this in a health-tourism platform:
  - Marketing collateral (clinic listings, hero images for procedures)
  - Generic illustrative renders (e.g. "modern dental clinic interior")
  - Before/after style reference mockups for the operator dashboard

NOT for patient-facing medical visualizations: a generated image is
not a medical mockup, and presenting it as such would be misleading
(and a regulatory issue under KVKK / Türkiye sağlık reklam mevzuatı).

Schema (from /v1/Tool/Detail):
  - prompt (textarea, required)
  - inputImage (combinefileinput, optional) — reference for image-edit
  - aspectRatio (select) — "" (match input) | "1:1" .. "21:9"
  - resolution (select) — "1K" | "2K" | "4K"
  - safetySetting (select) — BLOCK_LOW_AND_ABOVE .. OFF
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.pii import redact_pii
from app.services.ai.wiro_client import (
    WiroAuthError,
    WiroTaskError,
    WiroTimeout,
    extract_output_urls,
    run,
)

logger = logging.getLogger(__name__)


SUPPORTED_ASPECT_RATIOS = frozenset(
    {"", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
)
SUPPORTED_RESOLUTIONS = frozenset({"1K", "2K", "4K"})
SUPPORTED_SAFETY_SETTINGS = frozenset(
    {
        "BLOCK_LOW_AND_ABOVE",
        "BLOCK_MEDIUM_AND_ABOVE",
        "BLOCK_ONLY_HIGH",
        "BLOCK_NONE",
        "OFF",
    }
)


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", False))


def generate(
    *,
    prompt: str,
    reference_image_bytes: Optional[bytes] = None,
    reference_image_url: Optional[str] = None,
    reference_image_filename: str = "ref.jpg",
    reference_image_content_type: str = "image/jpeg",
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    safety_setting: str = "BLOCK_MEDIUM_AND_ABOVE",
    timeout: float = 90.0,
) -> Optional[list[str]]:
    """Generate images. Returns a list of CDN URLs or None on failure.

    Args:
        prompt: required, redacted before transmission.
        reference_image_bytes / reference_image_url: optional reference
            for image-edit mode. ``aspect_ratio=""`` (match-input) is
            valid only when a reference is provided.
        aspect_ratio: see SUPPORTED_ASPECT_RATIOS. Default "1:1".
        resolution: see SUPPORTED_RESOLUTIONS. Default "1K" (cheapest).
        safety_setting: see SUPPORTED_SAFETY_SETTINGS. Default
            BLOCK_MEDIUM_AND_ABOVE — sane production default.

    Returns ``None`` on:
      - feature flag off
      - empty / whitespace prompt
      - unsupported enum value (aspect_ratio / resolution / safety_setting)
      - "" aspect_ratio without a reference image (Wiro would reject)
      - WIRO_API_SECRET missing
      - submit/poll raised
      - extraction yielded no URLs
    """
    if not is_enabled():
        return None
    if not prompt or not prompt.strip():
        return None
    if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        logger.warning("nano_banana_image.unsupported_aspect_ratio: %s", aspect_ratio)
        return None
    if resolution not in SUPPORTED_RESOLUTIONS:
        logger.warning("nano_banana_image.unsupported_resolution: %s", resolution)
        return None
    if safety_setting not in SUPPORTED_SAFETY_SETTINGS:
        logger.warning("nano_banana_image.unsupported_safety: %s", safety_setting)
        return None
    has_reference = bool(reference_image_bytes) or bool(reference_image_url)
    if aspect_ratio == "" and not has_reference:
        logger.warning(
            "nano_banana_image.match_input_aspect_without_reference: rejecting locally"
        )
        return None

    fields: dict = {
        "prompt": redact_pii(prompt),
        "aspectRatio": aspect_ratio,
        "resolution": resolution,
        "safetySetting": safety_setting,
    }
    files: dict = {}
    if reference_image_bytes:
        files["inputImage"] = (
            reference_image_filename,
            reference_image_bytes,
            reference_image_content_type,
        )
    elif reference_image_url:
        # combinefileinput URL mode: URL goes in the field VALUE, no
        # multipart file part. Same shape as moondream's image_url.
        fields["inputImage"] = reference_image_url

    try:
        result = run(
            settings.WIRO_NANO_BANANA_IMAGE_MODEL,
            fields=fields,
            files=files or None,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("nano_banana_image.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("nano_banana_image.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("nano_banana_image.unexpected: %s", exc)
        return None

    urls = extract_output_urls(result)
    return urls or None
