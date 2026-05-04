"""Pre-build the disease corpus embedding cache.

Two-step:
  1. Regenerate `app/data/disease_corpus.json` from source files.
  2. Force `embedding_retriever.ensure_loaded()` so the .npy cache is
     written to disk (under app/data/embedding_cache/).

Run from the backend/ directory:
    python scripts/precompute_embeddings.py

Used in Dockerfile builder stage so the runtime image ships with both
the corpus JSON *and* the encoded .npy matrix — no model load and no
encoding work happens on the first request.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("precompute_embeddings")

# Make `app.*` importable when run from the backend/ root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    # Step 1: rebuild corpus JSON.
    from scripts import build_disease_corpus
    rc = build_disease_corpus.main()
    if rc != 0:
        logger.error("Corpus build failed (rc=%s)", rc)
        return rc

    # Step 2: force-load retriever to encode + cache.
    from app.agents.embedding_retriever import embedding_retriever
    ok = embedding_retriever.ensure_loaded()
    if not ok:
        logger.error("Embedding retriever failed to load")
        return 1

    cache_dir = ROOT / "app" / "data" / "embedding_cache"
    cached = list(cache_dir.glob("*.npy")) if cache_dir.exists() else []
    logger.info("Pre-build complete. Cache files: %s", [p.name for p in cached])
    return 0


if __name__ == "__main__":
    sys.exit(main())
