"""Optional explanation layer (B9) — natural language specialty justification.

Generates a 1–2 sentence Turkish explanation of why a specialty was recommended,
using the LLM. The explanation is PURELY cosmetic — it does NOT change any score,
canonical, or routing decision.

Gated by LLM_EXPLAIN_ENABLED feature flag.

Usage::

    explanation = generate_explanation(
        specialty_id="kardiyoloji",
        specialty_name_tr="Kardiyoloji",
        canonicals=["göğüs ağrısı", "çarpıntı"],
    )
    # Returns: "Göğüs ağrısı ve çarpıntı belirtileriniz nedeniyle Kardiyoloji önerilmiştir."
    # or "" on failure / flag off.
"""

from __future__ import annotations

import json
import logging
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a medical assistant that explains triage results to Turkish-speaking patients.
Write 1–2 short, clear sentences in Turkish explaining why the given specialty was recommended
based on the listed symptoms. Use plain language — avoid medical jargon.
Return only the explanation text, no JSON, no preamble."""

_USER_TEMPLATE = """\
Recommended specialty: {specialty_name_tr}
Detected symptoms: {symptom_list}

Explain in 1-2 Turkish sentences why this specialty was recommended."""


def generate_explanation(
    specialty_id: str,
    specialty_name_tr: str,
    canonicals: List[str],
) -> str:
    """Generate a natural-language explanation for the specialty recommendation.

    Returns an empty string if LLM_EXPLAIN_ENABLED is False, canonicals is empty,
    or the LLM call fails.  Never raises.
    """
    if not settings.LLM_EXPLAIN_ENABLED:
        return ""

    if not canonicals:
        return ""

    symptom_list = ", ".join(canonicals)
    user = _USER_TEMPLATE.format(
        specialty_name_tr=specialty_name_tr,
        symptom_list=symptom_list,
    )

    try:
        from app.services.llm_nlu_client import get_nlu_client

        client = get_nlu_client()
        raw, _, _ = client.call(_SYSTEM_PROMPT, user)
        explanation = raw.strip()

        # Sanity check: explanation should be non-empty and reasonably short
        if explanation and len(explanation) < 500:
            return explanation

        logger.warning("LLM explanation too long or empty (%d chars)", len(explanation))
        return ""

    except Exception as exc:
        logger.warning("LLM explanation failed (specialty=%s): %s", specialty_id, exc)
        return ""
