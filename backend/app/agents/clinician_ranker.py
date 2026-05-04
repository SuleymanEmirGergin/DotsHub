"""Phase-2 LLM-as-clinician constrained reranker.

Takes a *closed set* of disease candidates (union of Jaccard + embedding
top-K) and asks the LLM to:
  1. Rank them by likelihood given the conversation so far.
  2. For each, list 1-3 ayırt edici features that are still uncertain
     (these feed Phase-3 information-gain question selection).

Hard constraint: LLM may only choose from the supplied disease_labels.
JSON-schema-validated; on any failure the agent returns empty so callers
fall back to deterministic ranking.

Always-on in production: the rerank step is part of the standard turn
pipeline. Failures (Wiro down, JSON malformed, timeout) gracefully fall
back to the blended candidate ranking.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent
from app.agents.embedding_retriever import embedding_retriever

logger = logging.getLogger(__name__)

# Clinician rerank is closed-set + JSON-shape-validated → it doesn't need
# the strongest LLM. A faster model (gpt-5-mini) cuts end-to-end latency
# from ~25s to ~8-12s without measurable quality loss in our smoke tests.
# Override via CLINICIAN_LLM_MODEL when calibrating against larger models.
_CLINICIAN_DEFAULT_MODEL = os.getenv("CLINICIAN_LLM_MODEL", "gpt-5-mini")


SYSTEM_PROMPT_TR = """Sen kıdemli bir Türk hekim yardımcısısın. Görevin: hastanın anlattıklarını ve verilen KAPALI hastalık listesini değerlendirip, listeyi olasılığa göre yeniden sıralamak.

KESİN KURALLAR:
- Yalnızca sana verilen `candidates` listesindeki `disease_label` değerleri arasından seçim yap. Listede olmayan bir hastalığı ASLA önerme.
- Tanı koymuyorsun. Çıktı sadece sıralama + her aday için ayırt edici eksik bilgi.
- Çıktıyı geçerli JSON olarak ver. Açıklama, markdown, kod bloğu yazma.

Çıktı şeması:
{
  "ranked": [
    {
      "disease_label": "<verilen listeden>",
      "confidence_0_1": <0..1 arası ondalık>,
      "reasoning_tr": "<1 cümle: neden bu sıra>",
      "missing_key_features_tr": ["<en fazla 3 ayırt edici eksik bulgu, kısa>"]
    }
  ]
}

`ranked` listesi `candidates`'taki tüm öğeleri içermelidir; sıralama olasılığa göredir.
`confidence_0_1` toplamı 1 olmak zorunda değil ama tutarlı olmalı (en yüksek üstte).
`missing_key_features_tr` öğeleri kısa Türkçe ifade olsun (örn. "ateş", "ışığa hassasiyet", "ağrı süresi 24 saatten uzun mu").
"""


@dataclass
class ClinicianRanking:
    ranked: List[Dict[str, Any]]  # [{disease_label, confidence_0_1, reasoning_tr, missing_key_features_tr}]
    raw: Optional[Dict[str, Any]] = None


class ClinicianRanker(BaseAgent):
    name = "ClinicianRanker"
    system_prompt = SYSTEM_PROMPT_TR

    def __init__(self, llm=None) -> None:
        super().__init__(llm=llm)
        # Override the inherited LLM client's model so the clinician
        # specifically uses CLINICIAN_LLM_MODEL (defaults to gpt-5-mini)
        # without affecting other agents that share the singleton client.
        try:
            from app.core.llm_client import LLMClient
            self.llm = LLMClient(model=_CLINICIAN_DEFAULT_MODEL)
        except Exception as exc:
            logger.warning(
                f"[ClinicianRanker] could not pin model {_CLINICIAN_DEFAULT_MODEL!r}: {exc}"
            )

    async def rerank(
        self,
        user_text: str,
        conversation_history: List[Dict[str, str]],
        candidates: List[Dict[str, Any]],
    ) -> ClinicianRanking:
        """Return reranked closed-set candidates, or empty on any failure.

        `candidates` items must include at least: disease_label, tr_label, text
        (the text is what was indexed for embedding — short TR description +
        canonical symptoms + specialty). text may be empty if unavailable.
        """
        if not candidates:
            return ClinicianRanking(ranked=[])

        allowed_labels = {c["disease_label"] for c in candidates}

        payload = {
            "user_text": user_text or "",
            "conversation_history": conversation_history or [],
            "candidates": [
                {
                    "disease_label": c["disease_label"],
                    "tr_label": c.get("tr_label", c["disease_label"]),
                    "text": c.get("text", ""),
                    "specialty_tr": c.get("specialty_tr", ""),
                }
                for c in candidates
            ],
        }

        # Lazy import metrics so test envs without prometheus_client still work.
        try:
            from app.observability.metrics import (
                clinician_rerank_total,
                clinician_rerank_seconds,
            )
        except Exception:
            clinician_rerank_total = None
            clinician_rerank_seconds = None

        import time
        t0 = time.perf_counter()

        try:
            user_msg = json.dumps(payload, ensure_ascii=False)
            raw = await self.llm.chat_json(system=self.system_prompt, user=user_msg)
        except Exception as e:
            logger.warning(f"[ClinicianRanker] LLM call failed: {e}")
            if clinician_rerank_total is not None:
                clinician_rerank_total.labels(outcome="error").inc()
            if clinician_rerank_seconds is not None:
                clinician_rerank_seconds.observe(time.perf_counter() - t0)
            return ClinicianRanking(ranked=[])

        if not isinstance(raw, dict) or "ranked" not in raw:
            logger.warning(f"[ClinicianRanker] malformed LLM output (missing 'ranked'): {raw}")
            return ClinicianRanking(ranked=[], raw=raw)

        cleaned: List[Dict[str, Any]] = []
        for item in raw.get("ranked", []):
            if not isinstance(item, dict):
                continue
            label = item.get("disease_label")
            if label not in allowed_labels:
                logger.info(f"[ClinicianRanker] dropping out-of-set label: {label!r}")
                continue
            try:
                conf = float(item.get("confidence_0_1", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            features = item.get("missing_key_features_tr") or []
            if not isinstance(features, list):
                features = []
            features = [str(f).strip() for f in features if str(f).strip()][:3]
            cleaned.append({
                "disease_label": label,
                "confidence_0_1": conf,
                "reasoning_tr": str(item.get("reasoning_tr", "")).strip(),
                "missing_key_features_tr": features,
            })

        cleaned.sort(key=lambda x: -x["confidence_0_1"])
        if clinician_rerank_total is not None:
            clinician_rerank_total.labels(
                outcome="ranked" if cleaned else "empty"
            ).inc()
        if clinician_rerank_seconds is not None:
            clinician_rerank_seconds.observe(time.perf_counter() - t0)
        return ClinicianRanking(ranked=cleaned, raw=raw)


clinician_ranker = ClinicianRanker()


def merge_candidate_pool(
    jaccard_candidates: List[Dict[str, Any]],
    embedding_candidates: List[Dict[str, Any]],
    pool_size: int = 8,
) -> List[Dict[str, Any]]:
    """Build a deduped candidate pool for the clinician.

    Inputs:
      jaccard_candidates: legacy candidate_generator output (list of dicts
        with 'disease_label' + 'score_0_1').
      embedding_candidates: embedding_retriever.retrieve() output.
    Output items always include {disease_label, tr_label, specialty_tr, text}.
    """
    pool: Dict[str, Dict[str, Any]] = {}

    for c in jaccard_candidates or []:
        label = c.get("disease_label")
        if not label:
            continue
        meta = embedding_retriever.get_item(label) or {}
        pool[label] = {
            "disease_label": label,
            "tr_label": meta.get("tr_label") or c.get("tr_label") or label,
            "specialty_id": meta.get("specialty_id", ""),
            "specialty_tr": meta.get("specialty_tr", ""),
            "text": meta.get("text", ""),
            "_jaccard_score": float(c.get("score_0_1", 0.0)),
        }

    for r in embedding_candidates or []:
        label = r.get("disease_label")
        if not label:
            continue
        if label not in pool:
            pool[label] = {
                "disease_label": label,
                "tr_label": r.get("tr_label", label),
                "specialty_id": r.get("specialty_id", ""),
                "specialty_tr": r.get("specialty_tr", ""),
                "text": r.get("text", ""),
                "_embedding_score": float(r.get("score", 0.0)),
            }
        else:
            pool[label]["_embedding_score"] = float(r.get("score", 0.0))

    items = list(pool.values())
    items.sort(
        key=lambda x: -(
            x.get("_embedding_score", 0.0) + x.get("_jaccard_score", 0.0)
        )
    )
    return items[:pool_size]
