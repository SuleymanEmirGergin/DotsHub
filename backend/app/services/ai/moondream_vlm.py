"""Moondream3-Preview VLM (visual question answering) wrapper via Wiro.ai.

Differs from CogVLM2 caption in two ways that matter for our flow:

  1. **Image, not video** — single image input (``inputImage``).
     Faster, cheaper, simpler for the patient (a selfie / smile photo
     replaces a video clip). Most pre-quote visual signals don't
     need motion.
  2. **Direct Q&A with optional reasoning trace** — instead of
     "describe this", we ask a focused question and (optionally) get
     the model's reasoning. The ``reasoning`` flag is on by default
     for clinical use because the operator review pipeline benefits
     from seeing why the model said what it did (audit trail).

Use cases:
  - Hair-loss Norwood-stage estimate from a single scalp photo
  - Smile-line / dental issue assessment from a single grin photo
  - Skin condition triage from a close-up
  - Structured "answer in JSON" prompts to extract specific fields
    (e.g. "List all visible accessories", "Estimate Norwood stage")

PII redaction applies to the prompt before submit. The image itself
is uploaded as-is; consent gating is the caller's responsibility.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.pii import redact_pii
from app.services.ai.wiro_client import (
    WiroAuthError,
    WiroTaskError,
    WiroTaskResult,
    WiroTimeout,
    fetch_output_text,
    run,
)

logger = logging.getLogger(__name__)


# Pre-tuned prompt presets aligned with the same set in
# cogvlm_caption.HEALTH_TOURISM_PROMPTS but rewritten for the
# image-only Q&A surface (Moondream returns better answers when the
# question is direct rather than descriptive).
HEALTH_TOURISM_PROMPTS = {
    "hair_loss_norwood": (
        "Estimate the Norwood scale stage (1-7) of the patient's "
        "visible hair loss in this image. Identify the affected "
        "areas (crown, temples, hairline). If unclear or the image "
        "does not show the scalp, answer 'unclear'. Respond as JSON "
        '{"norwood_stage": <int|"unclear">, "affected_areas": [<str>]}.'
    ),
    "smile_dental": (
        "List visible dental issues in this image: alignment problems, "
        "discoloration, missing teeth, visible damage. If no issues "
        "visible, answer 'none'. Respond as JSON "
        '{"issues": [<str>], "candidate_for": [<"veneers"|"whitening"|"alignment"|...>]}.'
    ),
    "skin_dermatology": (
        "Identify visible skin conditions in this image: location, "
        "lesion type (papules, pustules, scars, pigmentation), "
        "approximate severity (mild/moderate/severe). Do not "
        "diagnose. Respond as JSON "
        '{"observations": [{"location": <str>, "type": <str>, "severity": <str>}]}.'
    ),
    "rhinoplasty_profile": (
        "Describe the visible profile of the patient's nose: "
        "estimated length, bridge, tip projection, deviation, "
        "presence of dorsal hump. Respond as JSON "
        '{"length": <str>, "bridge": <str>, "tip_projection": <str>, "deviation": <str>, "dorsal_hump": <bool>}.'
    ),
    "general": "Describe the relevant clinical features visible in this image.",
}


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_MOONDREAM_VLM_ENABLED", False))


def query(
    *,
    image_bytes: Optional[bytes] = None,
    image_url: Optional[str] = None,
    image_filename: str = "image.jpg",
    image_content_type: str = "image/jpeg",
    prompt: str = HEALTH_TOURISM_PROMPTS["general"],
    reasoning: bool = True,
    temperature: float = 0.7,
    top_p: float = 0.95,
    timeout: float = 60.0,
) -> Optional[str]:
    """Ask Moondream a question about an image. Returns text answer
    (often JSON when the prompt asks for it) or None on failure.

    Provide either ``image_bytes`` (multipart upload — preferred for
    patient photos that should never hit a public URL) OR ``image_url``
    (Wiro fetches it).

    Args:
        image_bytes: raw image bytes
        image_url: alternative: HTTPS URL Wiro fetches
        prompt: what to ask. Default is generic — pass one of
            HEALTH_TOURISM_PROMPTS for steered Q&A.
        reasoning: include the model's reasoning trace in the answer.
            Default True — costs more output tokens but gives the
            audit trail clinical reviewers expect. Set False for
            lean text-only output paths.
        temperature: 0.0-2.0. Default 0.7 matches Moondream's docs.
        top_p: nucleus sampling. 0.95 = balanced.
        timeout: poll deadline. Moondream is fast (~6s typical) but
            queue + image preprocess can push 30-60s.
    """
    if not is_enabled():
        return None
    if not image_bytes and not image_url:
        return None
    if not prompt or not prompt.strip():
        return None

    safe_prompt = redact_pii(prompt)

    fields: dict = {
        "prompt": safe_prompt,
        # Wiro CLI flag passthrough — empty string means "off",
        # "--reasoning" means "on" per the docs example. We pass the
        # explicit flag string so the worker enables it.
        "reasoning": "--reasoning" if reasoning else "",
        "temperature": temperature,
        "top_p": top_p,
    }
    files: dict = {}
    if image_bytes:
        files["inputImage"] = (image_filename, image_bytes, image_content_type)
    else:
        # URL-only path: Moondream's docs show ``-F "inputImage=URL"``
        # — i.e. the URL is the form field VALUE (text field), not a
        # file part. Different multipart shape than Whisper / CogVLM
        # because Moondream's upstream uses a single ``inputImage``
        # field that accepts either a file ref or a URL string.
        fields["inputImage"] = image_url

    try:
        result = run(
            settings.WIRO_MOONDREAM_VLM_MODEL,
            fields=fields,
            files=files or None,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("moondream_vlm.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("moondream_vlm.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("moondream_vlm.unexpected: %s", exc)
        return None

    return _extract_answer(result)


def _extract_answer(result: WiroTaskResult) -> Optional[str]:
    """Moondream returns the answer either inline (small responses)
    or as a text/JSON file URL (larger answers with reasoning trace).
    Probe inline first; CDN fetch as fallback."""
    for key in ("answer", "output", "text", "result", "response"):
        val = (result.parameters or {}).get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    for output in result.outputs:
        url = output.get("url")
        if not url:
            continue
        try:
            text = fetch_output_text(url)
        except Exception as exc:  # noqa: BLE001
            logger.info("moondream_vlm.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
