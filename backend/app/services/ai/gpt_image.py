"""OpenAI gpt-image-2 image gen/edit/inpaint wrapper via Wiro.ai.

Like nano-banana-pro but adds an inpainting path: pass an image AND a
mask to constrain edits to the masked region. ``generate()`` returns
``Optional[list[str]]`` — list of CDN URLs or None on failure.

Use case beyond plain gen: localised cosmetic mockups (e.g. "whiten
only the teeth, leave the rest of the photo identical"). Same legal
caveat as nano-banana — generated images are illustrative only, not
medical predictions.

Schema (from /v1/Tool/Detail):
  - prompt (textarea, required)
  - inputImage (combinefileinput, optional) — base image for edits
  - inputImageMask (combinefileinput, optional) — mask for inpainting
  - size (select, required) — "auto" | "1:1" | "3:2" | "2:3"
  - quality (select, required) — "low" | "medium" | "high"
  - samples (number, required) — how many images to generate
  - background (select) — "auto" | "opaque"
  - outputFormat (select) — "png" | "jpeg" | "webp"
  - outputCompression (number) — JPEG/WEBP compression
  - moderation (select) — "auto" | "low"
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


SUPPORTED_SIZES = frozenset({"auto", "1:1", "3:2", "2:3"})
SUPPORTED_QUALITIES = frozenset({"low", "medium", "high"})
SUPPORTED_BACKGROUNDS = frozenset({"auto", "opaque"})
SUPPORTED_OUTPUT_FORMATS = frozenset({"png", "jpeg", "webp"})
SUPPORTED_MODERATIONS = frozenset({"auto", "low"})


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_GPT_IMAGE_ENABLED", False))


def generate(
    *,
    prompt: str,
    input_image_bytes: Optional[bytes] = None,
    input_image_url: Optional[str] = None,
    input_image_filename: str = "img.jpg",
    input_image_content_type: str = "image/jpeg",
    input_image_mask_bytes: Optional[bytes] = None,
    input_image_mask_url: Optional[str] = None,
    input_image_mask_filename: str = "mask.png",
    input_image_mask_content_type: str = "image/png",
    size: str = "auto",
    quality: str = "medium",
    samples: int = 1,
    background: str = "auto",
    output_format: str = "png",
    output_compression: Optional[int] = None,
    moderation: str = "auto",
    timeout: float = 120.0,
) -> Optional[list[str]]:
    """Generate / edit / inpaint images. Returns CDN URLs or None.

    Args:
        prompt: required, redacted before transmission.
        input_image_*: optional source for edits/inpainting.
        input_image_mask_*: optional white=editable / black=keep mask
            for inpainting. Masking only matters when an input image is
            also provided.
        size: see SUPPORTED_SIZES. Default "auto" — let the model pick
            based on the prompt.
        quality: see SUPPORTED_QUALITIES. Default "medium" — balance
            cost and visual quality.
        samples: 1-N images per call. Wiro charges per sample.
        background: "opaque" forces flat-fill bg; "auto" preserves
            transparency where appropriate.
        output_format: PNG (lossless), JPEG/WEBP (smaller).
        output_compression: 0-100 for JPEG/WEBP. None = model default.
        moderation: "auto" = OpenAI's default; "low" relaxes some
            checks (use only when content is plainly safe).
    """
    if not is_enabled():
        return None
    if not prompt or not prompt.strip():
        return None
    if size not in SUPPORTED_SIZES:
        logger.warning("gpt_image.unsupported_size: %s", size)
        return None
    if quality not in SUPPORTED_QUALITIES:
        logger.warning("gpt_image.unsupported_quality: %s", quality)
        return None
    if not isinstance(samples, int) or samples < 1:
        logger.warning("gpt_image.invalid_samples: %r", samples)
        return None
    if background not in SUPPORTED_BACKGROUNDS:
        logger.warning("gpt_image.unsupported_background: %s", background)
        return None
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        logger.warning("gpt_image.unsupported_output_format: %s", output_format)
        return None
    if moderation not in SUPPORTED_MODERATIONS:
        logger.warning("gpt_image.unsupported_moderation: %s", moderation)
        return None

    fields: dict = {
        "prompt": redact_pii(prompt),
        "size": size,
        "quality": quality,
        "samples": samples,
        "background": background,
        "outputFormat": output_format,
        "moderation": moderation,
    }
    if output_compression is not None:
        fields["outputCompression"] = int(output_compression)

    files: dict = {}
    if input_image_bytes:
        files["inputImage"] = (
            input_image_filename,
            input_image_bytes,
            input_image_content_type,
        )
    elif input_image_url:
        fields["inputImage"] = input_image_url

    if input_image_mask_bytes:
        files["inputImageMask"] = (
            input_image_mask_filename,
            input_image_mask_bytes,
            input_image_mask_content_type,
        )
    elif input_image_mask_url:
        fields["inputImageMask"] = input_image_mask_url

    try:
        result = run(
            settings.WIRO_GPT_IMAGE_MODEL,
            fields=fields,
            files=files or None,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("gpt_image.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("gpt_image.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("gpt_image.unexpected: %s", exc)
        return None

    urls = extract_output_urls(result)
    return urls or None
