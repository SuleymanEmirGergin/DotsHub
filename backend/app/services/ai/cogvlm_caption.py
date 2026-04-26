"""CogVLM2-LLaMA3-caption video-to-text wrapper via Wiro.ai.

Vision-language model that captions video clips. The patient input
flow looks like:
  - Patient self-records a short clip (face / scalp / smile / area
    of concern) on their phone
  - Backend pipes the clip through this caption model with a domain-
    specific prompt ("Describe visible hair density on the crown")
  - Caption text feeds into procedure_intent for classification, OR
    directly into the quote engine as supporting context for the
    consulting clinic

Until we have a dedicated hair-loss / dermatology classifier (Wiro
doesn't host one yet — discuss open-source GitHub alternatives in
next session), this VLM is our pragmatic Tier-1 visual assessment
path: a single-frame video acts as an image, and the text caption
is a structured proxy for what a domain classifier would output.

Multipart input: video bytes OR video URL. Free-text prompt steers
caption quality — generic prompts get generic captions.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.pii import redact_pii
from app.services.ai.wiro_client import (
    WiroTaskError,
    WiroTaskResult,
    WiroTimeout,
    fetch_output_text,
    run,
)

logger = logging.getLogger(__name__)


# Domain-tuned prompt presets. Pass via ``prompt=`` to caption() when
# the use case is specific; the model returns markedly better
# captions for steered prompts than for the default
# "describe this video".
HEALTH_TOURISM_PROMPTS = {
    "hair_loss": (
        "Describe the visible hair density on the patient's scalp, the "
        "extent of any visible hair loss area (crown, temples, hairline), "
        "and the apparent Norwood-scale stage. Note any visible scarring "
        "or irregularities. Be concise and clinical, not cosmetic."
    ),
    "smile_dental": (
        "Describe the patient's visible teeth: alignment, color, gaps, "
        "any visible damage or staining, and the overall smile line. "
        "Note whether veneers, whitening, or alignment treatment may "
        "be relevant. Be concise and clinical."
    ),
    "skin_dermatology": (
        "Describe any visible skin condition: location, color, lesion "
        "type (papules, pustules, scars, pigmentation), and approximate "
        "extent. Do not diagnose. Be concise and clinical."
    ),
    "rhinoplasty_assessment": (
        "Describe the visible profile of the patient's nose: length, "
        "bridge, tip projection, deviation, and any prominent dorsal "
        "hump. Be concise and clinical, not aesthetic."
    ),
    "general": "Please describe this video in detail.",
}


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_COGVLM_CAPTION_ENABLED", False))


def caption(
    *,
    video_bytes: Optional[bytes] = None,
    video_url: Optional[str] = None,
    video_filename: str = "video.mp4",
    video_content_type: str = "video/mp4",
    prompt: str = HEALTH_TOURISM_PROMPTS["general"],
    num_beams: int = 1,
    temperature: float = 0.1,
    timeout: float = 60.0,
) -> Optional[str]:
    """Generate a caption for a video clip.

    Args:
        video_bytes: raw video file content (preferred — keeps patient
            video off public URLs)
        video_url: alternative: Wiro fetches from this URL
        prompt: what to describe. Default is generic; use one of
            HEALTH_TOURISM_PROMPTS for steered captions.
        num_beams: beam search width. 1 = greedy (fast); higher
            values (3-5) give better quality at proportional cost.
        temperature: 0=deterministic, higher=more varied. We default
            low (0.1) for clinical descriptions where we want
            consistency across re-runs.
        timeout: poll deadline. Wiro lists 1s processing, but queue +
            video preprocessing typically pushes total to 30-60s.

    Returns:
        Caption text or None on failure / disabled / no input.
    """
    if not is_enabled():
        return None
    if not video_bytes and not video_url:
        return None

    safe_prompt = redact_pii(prompt) if prompt else HEALTH_TOURISM_PROMPTS["general"]

    fields: dict = {
        "prompt": safe_prompt,
        "numBeams": num_beams,
        "temperature": temperature,
    }
    files: dict = {}
    if video_bytes:
        files["inputVideo"] = (video_filename, video_bytes, video_content_type)
        fields["inputVideoUrl"] = ""
    else:
        fields["inputVideoUrl"] = video_url
        # Same multipart-shape constraint as Whisper — keep the file
        # slot present even when URL is the source.
        files["inputVideo"] = ("", b"", "application/octet-stream")

    try:
        result = run(
            settings.WIRO_COGVLM_CAPTION_MODEL,
            fields=fields,
            files=files,
            timeout=timeout,
        )
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("cogvlm_caption.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("cogvlm_caption.unexpected: %s", exc)
        return None

    return _extract_caption(result)


def _extract_caption(result: WiroTaskResult) -> Optional[str]:
    """Caption may be inline in parameters or written to an output
    file. Probe inline first."""
    for key in ("caption", "output", "text", "result", "description"):
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
            logger.info("cogvlm_caption.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
