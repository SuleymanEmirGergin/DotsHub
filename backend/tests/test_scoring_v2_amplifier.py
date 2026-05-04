"""Targeted tests for the rank-1 amplifier in scoring_v2.compute_specialty_prior.

The amplifier exists to prevent a single Layer B keyword match from
out-voting a confident Layer A signal (the "bulantı routes migraine to
GI" bug). Tests pin the boundary cases.
"""
from __future__ import annotations

import pytest

from app.scoring_v2 import compute_specialty_prior, merge_final_specialty_scores


D2S = [
    {"disease_label": "Migraine", "specialty_id": "neurology", "confidence": 1.0},
    {"disease_label": "Jaundice", "specialty_id": "internal_gi", "confidence": 0.85},
    {"disease_label": "Hemoroid", "specialty_id": "internal_gi", "confidence": 0.9},
]


def test_strong_rank1_drives_specialty():
    """Migraine with score 0.66 must give neurology a prior large enough
    to outweigh internal_gi's combined contribution from Jaundice +
    Hemoroid."""
    candidates = [
        {"disease_label": "Migraine", "score_0_1": 0.66},
        {"disease_label": "Jaundice", "score_0_1": 0.42},
        {"disease_label": "Hemoroid", "score_0_1": 0.42},
    ]
    prior = compute_specialty_prior(candidates, D2S)
    assert prior["neurology"] > prior["internal_gi"]


def test_weak_rank1_does_not_get_boost():
    """A rank-1 below 0.5 falls through the boost branch — no amplification."""
    candidates = [
        {"disease_label": "Migraine", "score_0_1": 0.30},
        {"disease_label": "Jaundice", "score_0_1": 0.42},
    ]
    prior_with_weak_top = compute_specialty_prior(candidates, D2S)

    # Compare against the formula without the boost: 0.30 * 1.0 = 0.30
    assert prior_with_weak_top["neurology"] == 0.30


def test_rank1_at_threshold_gets_boost():
    """Boundary: score == 0.5 triggers the boost (>=, not >)."""
    candidates = [{"disease_label": "Migraine", "score_0_1": 0.5}]
    prior = compute_specialty_prior(candidates, D2S)
    # 1.0 + 12.0 * 0.5 = 7.0 → 0.5 * 1.0 * 7.0 = 3.5
    assert prior["neurology"] == 3.5


def test_high_rank1_yields_large_prior():
    """Migraine at 0.85: prior_value = 0.85 * 1.0 * (1 + 12*0.85) = 9.52."""
    candidates = [{"disease_label": "Migraine", "score_0_1": 0.85}]
    prior = compute_specialty_prior(candidates, D2S)
    assert prior["neurology"] == pytest.approx(9.52, abs=1e-3)


def test_lower_ranks_unaffected():
    """Only rank-1 gets amplified; rank-2+ contribute as base."""
    candidates = [
        {"disease_label": "Hemoroid", "score_0_1": 0.40},   # rank 1, below threshold
        {"disease_label": "Migraine", "score_0_1": 0.85},   # rank 2 — no boost despite high score
    ]
    prior = compute_specialty_prior(candidates, D2S)
    # rank-2 Migraine: 0.85 * 1.0 = 0.85 (no boost)
    assert prior["neurology"] == 0.85


def test_unknown_disease_routes_to_fallback_with_boost():
    """An unmapped rank-1 with score >= 0.5 still boosts the fallback specialty."""
    candidates = [{"disease_label": "Unknown", "score_0_1": 0.7}]
    prior = compute_specialty_prior(candidates, D2S)
    # Fallback: 0.7 * 0.3 * (1 + 12*0.7) = 0.7 * 0.3 * 9.4 = 1.974
    assert prior["internal_gi"] == pytest.approx(1.974, abs=1e-3)


def test_full_merge_routes_migraine_correctly():
    """End-to-end: with realistic Layer B noise, neurology must win."""
    candidates = [
        {"disease_label": "Migraine", "score_0_1": 0.66},
        {"disease_label": "Jaundice", "score_0_1": 0.42},
        {"disease_label": "Hemoroid", "score_0_1": 0.42},
    ]
    prior = compute_specialty_prior(candidates, D2S)
    # Layer B got "bulantı" (+3.0) for internal_gi, nothing for neurology.
    rules = {"internal_gi": 3.0, "neurology": 0.0}
    merged = merge_final_specialty_scores(rules, prior)
    assert merged[0]["id"] == "neurology"
