"""Tests for triage_engine._blend_candidates_with_embedding.

Verifies the composite score formula and dedup behavior. Stubs the
embedding retriever so no real model is loaded.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from app import triage_engine as te


@pytest.fixture
def stub_embedding(monkeypatch):
    """Patch embedding_retriever.retrieve to return a fixed list."""
    fake = MagicMock()

    def _set_top(items: List[Dict[str, Any]]):
        fake.retrieve = MagicMock(return_value=items)

    fake.set_top = _set_top
    monkeypatch.setattr(
        "app.agents.embedding_retriever.embedding_retriever", fake
    )
    return fake


def test_blend_combines_scores_with_agreement_bonus(stub_embedding):
    stub_embedding.set_top([
        {"disease_label": "Migraine", "score": 0.86},
        {"disease_label": "Jaundice", "score": 0.84},
    ])
    jaccard = [
        {"disease_label": "Migraine", "score_0_1": 0.30},
    ]
    result = te._blend_candidates_with_embedding(
        jaccard_candidates=jaccard,
        input_text="sabah baş ağrısı",
        user_canonicals_tr=["baş ağrısı"],
        top_n=5,
    )
    labels = [c["disease_label"] for c in result]
    assert "Migraine" in labels
    assert "Jaundice" in labels
    # Migraine has both signals → 0.5*0.30 + 0.5*0.86 + 0.10 = 0.68
    migraine = next(c for c in result if c["disease_label"] == "Migraine")
    assert migraine["score_0_1"] == pytest.approx(0.68, abs=1e-3)
    # Jaundice has only embedding → 0.5*0 + 0.5*0.84 = 0.42
    jaundice = next(c for c in result if c["disease_label"] == "Jaundice")
    assert jaundice["score_0_1"] == pytest.approx(0.42, abs=1e-3)
    # Migraine should rank higher
    assert result[0]["disease_label"] == "Migraine"


def test_blend_score_capped_at_1(stub_embedding):
    stub_embedding.set_top([{"disease_label": "X", "score": 0.99}])
    jaccard = [{"disease_label": "X", "score_0_1": 0.99}]
    result = te._blend_candidates_with_embedding(jaccard, "x", ["x"], top_n=1)
    assert result[0]["score_0_1"] <= 1.0


def test_blend_falls_back_to_jaccard_when_no_query(stub_embedding):
    """No text and no canonicals → embedding skipped, returns jaccard as-is."""
    jaccard = [{"disease_label": "X", "score_0_1": 0.5}]
    result = te._blend_candidates_with_embedding(jaccard, "", [], top_n=5)
    assert result == jaccard
    stub_embedding.retrieve.assert_not_called() if hasattr(stub_embedding, "retrieve") else None


def test_blend_falls_back_when_embedding_empty(stub_embedding):
    stub_embedding.set_top([])
    jaccard = [{"disease_label": "X", "score_0_1": 0.4}]
    result = te._blend_candidates_with_embedding(jaccard, "x", ["x"], top_n=5)
    assert len(result) == 1
    assert result[0]["disease_label"] == "X"


def test_blend_handles_embedding_exception(stub_embedding):
    stub_embedding.retrieve = MagicMock(side_effect=RuntimeError("model down"))
    jaccard = [{"disease_label": "X", "score_0_1": 0.4}]
    result = te._blend_candidates_with_embedding(jaccard, "x", ["x"], top_n=5)
    # Falls back to jaccard
    assert result[0]["disease_label"] == "X"


def test_blend_top_n_truncation(stub_embedding):
    stub_embedding.set_top([
        {"disease_label": f"D{i}", "score": 0.9 - 0.05 * i}
        for i in range(10)
    ])
    result = te._blend_candidates_with_embedding(
        jaccard_candidates=[],
        input_text="x",
        user_canonicals_tr=["x"],
        top_n=3,
    )
    assert len(result) == 3
    # Already in descending order
    scores = [c["score_0_1"] for c in result]
    assert scores == sorted(scores, reverse=True)
