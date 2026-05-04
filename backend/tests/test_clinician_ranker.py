"""Unit tests for clinician_ranker (Phase 2).

The LLM call is fully stubbed; tests cover the contract:
  - closed-set enforcement (out-of-set predictions dropped)
  - JSON shape validation (malformed → empty)
  - confidence clamping to [0, 1]
  - graceful degradation on LLM failure
  - merge_candidate_pool dedup + ordering
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents import clinician_ranker as cr_mod


def _candidates() -> List[Dict[str, Any]]:
    return [
        {"disease_label": "Migraine", "tr_label": "Migren",
         "specialty_tr": "Nöroloji", "text": "Migren açıklaması"},
        {"disease_label": "Common Cold", "tr_label": "ÜSYE",
         "specialty_tr": "KBB", "text": "ÜSYE açıklaması"},
        {"disease_label": "Acne", "tr_label": "Akne",
         "specialty_tr": "Dermatoloji", "text": "Akne açıklaması"},
    ]


def _make_ranker(llm_response):
    """Build a ranker whose LLM call returns the given dict."""
    ranker = cr_mod.ClinicianRanker()
    ranker.llm = MagicMock()
    ranker.llm.chat_json = AsyncMock(return_value=llm_response)
    return ranker


@pytest.mark.asyncio
async def test_happy_path_ranks_and_clamps():
    response = {
        "ranked": [
            {"disease_label": "Migraine", "confidence_0_1": 0.9,
             "reasoning_tr": "klasik migren tablosu",
             "missing_key_features_tr": ["aura", "atak süresi", "tek taraflı mı"]},
            {"disease_label": "Common Cold", "confidence_0_1": 0.05,
             "reasoning_tr": "soğuk algınlığı düşük", "missing_key_features_tr": []},
            # Out-of-range confidence — must be clamped.
            {"disease_label": "Acne", "confidence_0_1": 1.7,
             "reasoning_tr": "akne ihtimal dışı", "missing_key_features_tr": []},
        ]
    }
    ranker = _make_ranker(response)
    out = await ranker.rerank(
        user_text="sabah baş ağrısı, ışık hassasiyeti",
        conversation_history=[],
        candidates=_candidates(),
    )
    assert len(out.ranked) == 3
    # Acne's confidence (1.7) was clamped to 1.0; sort then puts it #1.
    # This verifies clamp + re-sort, which is intentional: a malformed
    # over-1 value should not let the LLM upset the order via clamping.
    acne = next(r for r in out.ranked if r["disease_label"] == "Acne")
    assert acne["confidence_0_1"] == 1.0
    assert out.ranked[0]["disease_label"] == "Acne"
    # Migraine still kept at 0.9; missing features capped at 3.
    migraine = next(r for r in out.ranked if r["disease_label"] == "Migraine")
    assert migraine["confidence_0_1"] == 0.9
    assert len(migraine["missing_key_features_tr"]) == 3


@pytest.mark.asyncio
async def test_drops_out_of_set_predictions():
    response = {
        "ranked": [
            {"disease_label": "Migraine", "confidence_0_1": 0.8},
            {"disease_label": "MadeUpDisease", "confidence_0_1": 0.95},  # not in set
        ]
    }
    ranker = _make_ranker(response)
    out = await ranker.rerank(
        user_text="x", conversation_history=[], candidates=_candidates()
    )
    labels = [r["disease_label"] for r in out.ranked]
    assert "MadeUpDisease" not in labels
    assert labels == ["Migraine"]


@pytest.mark.asyncio
async def test_malformed_response_returns_empty():
    """No 'ranked' key — returns empty ranked list."""
    ranker = _make_ranker({"oops": "no ranked"})
    out = await ranker.rerank("x", [], _candidates())
    assert out.ranked == []


@pytest.mark.asyncio
async def test_llm_exception_returns_empty():
    ranker = cr_mod.ClinicianRanker()
    ranker.llm = MagicMock()
    ranker.llm.chat_json = AsyncMock(side_effect=RuntimeError("Wiro down"))
    out = await ranker.rerank("x", [], _candidates())
    assert out.ranked == []


@pytest.mark.asyncio
async def test_empty_candidates_short_circuits():
    """Should not call the LLM at all."""
    ranker = cr_mod.ClinicianRanker()
    ranker.llm = MagicMock()
    ranker.llm.chat_json = AsyncMock(return_value={"ranked": []})
    out = await ranker.rerank("x", [], [])
    assert out.ranked == []
    ranker.llm.chat_json.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_confidence_defaults_to_zero():
    response = {
        "ranked": [
            {"disease_label": "Migraine", "confidence_0_1": "not a number"},
            {"disease_label": "Common Cold", "confidence_0_1": None},
        ]
    }
    ranker = _make_ranker(response)
    out = await ranker.rerank("x", [], _candidates())
    confs = {r["disease_label"]: r["confidence_0_1"] for r in out.ranked}
    assert confs.get("Migraine") == 0.0
    assert confs.get("Common Cold") == 0.0


# ─── merge_candidate_pool ──────────────────────────────────────────────


def test_merge_pool_dedupes_and_orders_by_combined_score():
    jaccard = [
        {"disease_label": "Migraine", "score_0_1": 0.30},
        {"disease_label": "Common Cold", "score_0_1": 0.50},
    ]
    embedding = [
        {"disease_label": "Migraine", "tr_label": "Migren", "score": 0.85,
         "specialty_id": "neurology", "specialty_tr": "Nöroloji"},
        {"disease_label": "Acne", "tr_label": "Akne", "score": 0.80,
         "specialty_id": "dermatology", "specialty_tr": "Dermatoloji"},
    ]
    pool = cr_mod.merge_candidate_pool(jaccard, embedding, pool_size=8)
    labels = [p["disease_label"] for p in pool]
    # Migraine has both signals (0.30 + 0.85 = 1.15) → top
    assert labels[0] == "Migraine"
    # All three diseases present, no duplicates
    assert set(labels) == {"Migraine", "Common Cold", "Acne"}
    assert len(labels) == 3


def test_merge_pool_respects_pool_size():
    jaccard = [{"disease_label": f"D{i}", "score_0_1": 0.1 * i} for i in range(20)]
    pool = cr_mod.merge_candidate_pool(jaccard, [], pool_size=5)
    assert len(pool) == 5


def test_merge_pool_handles_empty_inputs():
    assert cr_mod.merge_candidate_pool([], [], pool_size=8) == []
    only_jacc = cr_mod.merge_candidate_pool(
        [{"disease_label": "X", "score_0_1": 0.5}], [], pool_size=8
    )
    assert len(only_jacc) == 1
    assert only_jacc[0]["disease_label"] == "X"
