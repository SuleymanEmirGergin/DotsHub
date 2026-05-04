"""Embedding-based disease candidate retriever (Phase 1, shadow mode).

Loads `disease_corpus.json` at startup, embeds each item's `text` with
`intfloat/multilingual-e5-base`, caches the matrix to disk, and exposes
cosine retrieval.

E5 protocol: prefix passages with "passage: " and queries with "query: ".

Runs in shadow mode — orchestrator logs results next to Jaccard output;
no behavior change yet.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CORPUS_PATH = _DATA_DIR / "disease_corpus.json"
_CACHE_DIR = _DATA_DIR / "embedding_cache"
_MODEL_NAME = "intfloat/multilingual-e5-base"
_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


class EmbeddingRetriever:
    """Cosine retrieval over disease corpus using multilingual-e5-base.

    Lazy-loaded: model and embeddings are computed on first use to avoid
    blocking app startup. Use `ensure_loaded()` to warm up explicitly.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._load_failed = False
        self._model = None
        self._items: List[Dict[str, Any]] = []
        self._matrix = None  # np.ndarray, shape (N, dim), L2-normalized

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def ensure_loaded(self) -> bool:
        """Load model + embeddings (idempotent). Returns True on success."""
        if self._loaded:
            return True
        if self._load_failed:
            return False
        with self._lock:
            if self._loaded:
                return True
            if self._load_failed:
                return False
            try:
                self._do_load()
                self._loaded = True
                return True
            except Exception as e:
                self._load_failed = True
                logger.warning(f"[EmbeddingRetriever] load failed: {e}", exc_info=True)
                return False

    def _do_load(self) -> None:
        import numpy as np

        corpus = self._read_corpus()
        if not corpus:
            raise RuntimeError("disease_corpus.json missing or empty — run build_disease_corpus.py")

        self._items = corpus["items"]
        content_hash = corpus.get("content_hash", "nohash")
        cache_path = _CACHE_DIR / f"e5_base_{content_hash}.npy"

        if cache_path.exists():
            try:
                self._matrix = np.load(cache_path)
                if self._matrix.shape[0] == len(self._items):
                    self._load_model_only()
                    logger.info(
                        f"[EmbeddingRetriever] loaded {len(self._items)} items "
                        f"from cache ({cache_path.name})"
                    )
                    return
                logger.warning(
                    f"[EmbeddingRetriever] cache row count mismatch "
                    f"({self._matrix.shape[0]} vs {len(self._items)}); rebuilding"
                )
            except Exception as e:
                logger.warning(f"[EmbeddingRetriever] cache read failed ({e}); rebuilding")

        self._load_model_only()
        passages = [_PASSAGE_PREFIX + it["text"] for it in self._items]
        logger.info(f"[EmbeddingRetriever] embedding {len(passages)} passages...")
        self._matrix = self._model.encode(
            passages,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, self._matrix)
        logger.info(f"[EmbeddingRetriever] cached to {cache_path.name}")

    def _load_model_only(self) -> None:
        from sentence_transformers import SentenceTransformer

        if self._model is None:
            logger.info(f"[EmbeddingRetriever] loading model {_MODEL_NAME}...")
            self._model = SentenceTransformer(_MODEL_NAME)

    def _read_corpus(self) -> Optional[Dict[str, Any]]:
        if not _CORPUS_PATH.exists():
            return None
        with open(_CORPUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def retrieve(self, text: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """Return top_k disease candidates by cosine similarity to `text`.

        Returns: [{"disease_label", "tr_label", "specialty_id", "specialty_tr",
                   "score", "rank"}], score in [0, 1] (higher = closer).
        Returns [] if retriever isn't loaded or text is empty.
        """
        if not text or not text.strip():
            return []
        if not self.ensure_loaded():
            return []

        import numpy as np

        q = self._model.encode(
            [_QUERY_PREFIX + text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        sims = self._matrix @ q  # cosine since both are L2-normalized
        if top_k >= len(sims):
            order = np.argsort(-sims)
        else:
            part = np.argpartition(-sims, top_k)[:top_k]
            order = part[np.argsort(-sims[part])]

        out: List[Dict[str, Any]] = []
        for rank, idx in enumerate(order[:top_k], start=1):
            it = self._items[int(idx)]
            out.append({
                "disease_label": it["disease_label"],
                "tr_label": it.get("tr_label", it["disease_label"]),
                "specialty_id": it.get("specialty_id", ""),
                "specialty_tr": it.get("specialty_tr", ""),
                "text": it.get("text", ""),
                "score": float(sims[int(idx)]),
                "rank": rank,
            })
        return out

    def get_item(self, disease_label: str) -> Optional[Dict[str, Any]]:
        """Look up corpus item by EN disease_label (source-of-truth key)."""
        if not self._loaded:
            return None
        for it in self._items:
            if it["disease_label"] == disease_label:
                return it
        return None


embedding_retriever = EmbeddingRetriever()
