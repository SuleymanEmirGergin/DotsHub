"""kristaller486/dots-ocr-1-5 multi-document OCR wrapper via Wiro.ai.

Handles patient-uploaded medical documents (lab results, prescriptions,
prior surgery records, dental panoramic scans). Output is JSON-shaped
layout when ``promptMode`` is layout-aware; plain text when it is just
``prompt_ocr``.

Schema (from /v1/Tool/Detail):
  - inputDocumentMultiple (multifileinput) — repeated-key files. Each
    document becomes its own ``inputDocumentMultiple=...`` part.
  - promptMode (selectwithcover, required) — layout style enum:
      prompt_layout_all_en | prompt_layout_only_en | prompt_ocr |
      prompt_web_parsing | prompt_scene_spotting
  - prompt (textarea, optional) — custom prompt; some modes use it
  - minPixels / maxPixels (number, optional)

Privacy
    Documents are uploaded to Wiro as-is. **Caller is responsible** for
    consent + redaction of irrelevant PII; we cannot inspect file
    contents pre-upload (image bytes / PDF). The free-text ``prompt``
    is redacted via PII helpers, but the documents themselves are not.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional, Tuple

from app.core.config import settings
from app.pii import redact_pii
from app.services.ai.wiro_client import (
    WiroAuthError,
    WiroTaskError,
    WiroTaskResult,
    WiroTimeout,
    fetch_output_text,
    run_with_repeated_inputs,
)

logger = logging.getLogger(__name__)


SUPPORTED_PROMPT_MODES = frozenset(
    {
        "prompt_layout_all_en",
        "prompt_layout_only_en",
        "prompt_ocr",
        "prompt_web_parsing",
        "prompt_scene_spotting",
    }
)

# Wiro's per-call cap isn't documented for this model; we apply our own
# generous cap so a misuse (e.g. forwarding 1000 photos of a chart book)
# fails locally with a clear log line rather than running up cost.
_MAX_DOCUMENTS = 50


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_DOTS_OCR_ENABLED", False))


def extract(
    *,
    documents: Iterable[Tuple[str, bytes, str]],
    prompt_mode: str = "prompt_ocr",
    prompt: Optional[str] = None,
    min_pixels: Optional[int] = None,
    max_pixels: Optional[int] = None,
    timeout: float = 120.0,
) -> Optional[str]:
    """Extract text/layout from one or more documents.

    Args:
        documents: iterable of (filename, content_bytes, content_type).
            Each becomes a multipart part under ``inputDocumentMultiple``.
        prompt_mode: see SUPPORTED_PROMPT_MODES. Default ``prompt_ocr``
            (plain text extraction). Use ``prompt_layout_all_en`` for
            JSON-shaped output with regions / boxes / classes.
        prompt: optional custom prompt steering. Some modes accept it.
            Redacted before transmission.
        min_pixels / max_pixels: optional input image scaling clamps.

    Returns ``None`` on any failure path (feature flag off, no docs,
    bad mode, auth missing, task error, empty output).
    """
    if not is_enabled():
        return None
    if prompt_mode not in SUPPORTED_PROMPT_MODES:
        logger.warning("dots_ocr.unsupported_prompt_mode: %s", prompt_mode)
        return None

    docs_list = list(documents or [])
    if not docs_list:
        return None
    if len(docs_list) > _MAX_DOCUMENTS:
        logger.warning(
            "dots_ocr.too_many_documents: %d (max %d)",
            len(docs_list),
            _MAX_DOCUMENTS,
        )
        return None

    fields: dict = {"promptMode": prompt_mode}
    if prompt and prompt.strip():
        fields["prompt"] = redact_pii(prompt)
    if min_pixels is not None:
        fields["minPixels"] = int(min_pixels)
    if max_pixels is not None:
        fields["maxPixels"] = int(max_pixels)

    multipart_files: list[tuple[str, tuple[str, bytes, str]]] = [
        ("inputDocumentMultiple", (filename, content, content_type))
        for filename, content, content_type in docs_list
    ]

    try:
        result = run_with_repeated_inputs(
            settings.WIRO_DOTS_OCR_MODEL,
            fields=fields,
            multipart_files=multipart_files,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("dots_ocr.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("dots_ocr.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("dots_ocr.unexpected: %s", exc)
        return None

    return _extract_text(result)


def _extract_text(result: WiroTaskResult) -> Optional[str]:
    """OCR output may be inline (small responses) or in a JSON file
    referenced by outputs[].url. Probe inline first."""
    for key in ("output", "text", "result", "ocr", "layout"):
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
            logger.info("dots_ocr.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
