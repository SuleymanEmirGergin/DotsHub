"""Unit tests for embedding_retriever (Phase 1).

Stubs out `sentence_transformers.SentenceTransformer` so tests run
offline — no model download, no torch import, sub-second.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _reset_embedding_module_state():
    """After each test, force a fresh module reload with NO patches so the
    singleton goes back to its real-corpus state. Without this, later
    tests in the suite (e.g. test_golden_flows) inherit a stub-loaded
    singleton and produce wrong rankings."""
    yield
    import importlib
    import app.agents.embedding_retriever as er_mod
    importlib.reload(er_mod)


@pytest.fixture
def stub_paths(tmp_path: Path):
    """Provide a temp corpus + cache dir; tests use these post-reload."""
    corpus = {
        "version": "1.0",
        "language": "tr-TR",
        "content_hash": "test_hash_abc",
        "items": [
            {
                "disease_label": "Migraine",
                "tr_label": "Migren",
                "specialty_id": "neurology",
                "specialty_tr": "Nöroloji",
                "text": "Migren. Tek taraflı zonklayıcı baş ağrısı, ışığa hassasiyet, bulantı.",
            },
            {
                "disease_label": "Common Cold",
                "tr_label": "ÜSYE",
                "specialty_id": "ent",
                "specialty_tr": "KBB",
                "text": "ÜSYE. Burun akıntısı, hapşırma, boğaz ağrısı, hafif ateş.",
            },
            {
                "disease_label": "Acne",
                "tr_label": "Akne",
                "specialty_id": "dermatology",
                "specialty_tr": "Dermatoloji",
                "text": "Akne. Yüzde sivilce ve siyah noktalar; ergenlikte sık.",
            },
        ],
    }
    corpus_path = tmp_path / "disease_corpus.json"
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    cache_dir = tmp_path / "embedding_cache"
    cache_dir.mkdir()
    return corpus_path, cache_dir


@pytest.fixture
def stub_model(monkeypatch):
    """Replace SentenceTransformer with a deterministic fake.

    The fake assigns each known string a unique unit vector so cosine
    similarity is exactly 1.0 for matches and ~0 for non-matches.
    """
    class _FakeST:
        def __init__(self, *_args, **_kwargs):
            # Map fragments to one-hot directions in 4D.
            self._key_to_axis = {
                "migren": 0,        # passages indexed for migraine
                "üsye": 1,
                "akne": 2,
                "default": 3,
            }

        def encode(self, texts, normalize_embeddings=True, **_kwargs):
            arr = []
            for t in texts:
                tl = t.lower()
                if "migren" in tl or "baş ağrı" in tl or "zonklayıcı" in tl:
                    axis = 0
                elif "üsye" in tl or "burun akıntı" in tl or "hapşırma" in tl:
                    axis = 1
                elif "akne" in tl or "sivilce" in tl:
                    axis = 2
                else:
                    axis = 3
                vec = [0.0, 0.0, 0.0, 0.0]
                vec[axis] = 1.0
                arr.append(vec)
            return np.array(arr, dtype=np.float32)

    # Patch the import inside the module's _load_model_only path.
    import sys
    import types

    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeST)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    return _FakeST


def _fresh_retriever(stub_paths, monkeypatch):
    """Reload module then patch its constants so the singleton uses stub paths."""
    import importlib
    import app.agents.embedding_retriever as er_mod
    importlib.reload(er_mod)
    corpus_path, cache_dir = stub_paths
    monkeypatch.setattr(er_mod, "_CORPUS_PATH", corpus_path)
    monkeypatch.setattr(er_mod, "_CACHE_DIR", cache_dir)
    return er_mod.embedding_retriever


def test_retriever_loads_corpus_and_embeds(stub_paths, stub_model, monkeypatch):
    er = _fresh_retriever(stub_paths, monkeypatch)
    assert er.ensure_loaded() is True
    assert er.is_loaded


def test_migraine_query_ranks_migren_first(stub_paths, stub_model, monkeypatch):
    er = _fresh_retriever(stub_paths, monkeypatch)
    er.ensure_loaded()
    out = er.retrieve("Sabahları başım çok ağrıyor, zonklayıcı", top_k=3)
    assert out[0]["disease_label"] == "Migraine"
    assert out[0]["tr_label"] == "Migren"
    assert out[0]["score"] == pytest.approx(1.0, abs=1e-3)


def test_skin_query_ranks_acne_first(stub_paths, stub_model, monkeypatch):
    er = _fresh_retriever(stub_paths, monkeypatch)
    out = er.retrieve("Yüzümde sivilce var, akne", top_k=3)
    assert out[0]["disease_label"] == "Acne"


def test_empty_query_returns_empty(stub_paths, stub_model, monkeypatch):
    er = _fresh_retriever(stub_paths, monkeypatch)
    assert er.retrieve("", top_k=5) == []
    assert er.retrieve("   ", top_k=5) == []


def test_get_item_lookup(stub_paths, stub_model, monkeypatch):
    er = _fresh_retriever(stub_paths, monkeypatch)
    er.ensure_loaded()
    item = er.get_item("Migraine")
    assert item is not None
    assert item["tr_label"] == "Migren"
    assert er.get_item("DoesNotExist") is None


def test_top_k_capped_at_corpus_size(stub_paths, stub_model, monkeypatch):
    er = _fresh_retriever(stub_paths, monkeypatch)
    out = er.retrieve("Migren baş ağrısı", top_k=99)
    assert len(out) == 3  # corpus has 3 items
    assert [r["rank"] for r in out] == [1, 2, 3]


def test_cache_is_reused_on_second_load(stub_paths, stub_model, monkeypatch, tmp_path):
    """Second load should hit the .npy cache rather than re-encoding."""
    er = _fresh_retriever(stub_paths, monkeypatch)
    er.ensure_loaded()
    cache_files = list((tmp_path / "embedding_cache").glob("*.npy"))
    assert len(cache_files) == 1

    # Force a second load via reload — cache should be reused (no error).
    er2 = _fresh_retriever(stub_paths, monkeypatch)
    er2.ensure_loaded()
    assert er2.is_loaded
