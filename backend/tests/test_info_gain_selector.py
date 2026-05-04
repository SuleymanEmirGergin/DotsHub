"""Unit tests for info_gain_selector (Phase 3).

Stubs disease_symptoms, kaggle_to_canonical, and the question bank so
the selector runs against deterministic fixtures.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def stub_data(tmp_path: Path, monkeypatch):
    """Drop minimal Kaggle cache + question bank files into a tmp tree."""
    data_dir = tmp_path / "data"
    cache_dir = data_dir / "kaggle_cache"
    cache_dir.mkdir(parents=True)

    # 4 diseases with symptom sets that admit a clean 50/50 split:
    #   - "fever" present in 2/4
    #   - "headache" present in 2/4 (different two)
    disease_symptoms = {
        "Flu":      ["fever_en", "headache_en", "cough_en"],
        "Migraine": ["headache_en", "nausea_en"],
        "Cold":     ["cough_en", "sore_throat_en"],
        "Pneumonia":["fever_en", "cough_en", "shortness_of_breath_en"],
    }
    (cache_dir / "disease_symptoms.json").write_text(
        json.dumps(disease_symptoms), encoding="utf-8"
    )

    kaggle_to_canonical = {
        "fever_en": "ateş",
        "headache_en": "baş ağrısı",
        "cough_en": "öksürük",
        "nausea_en": "bulantı",
        "sore_throat_en": "boğaz ağrısı",
        "shortness_of_breath_en": "nefes darlığı",
    }
    (cache_dir / "kaggle_to_canonical.json").write_text(
        json.dumps(kaggle_to_canonical), encoding="utf-8"
    )

    question_bank = {
        "questions": [
            {"canonical_symptom": "ateş",
             "question_tr": "Ateşiniz var mı?",
             "answer_type": "yes_no"},
            {"canonical_symptom": "baş ağrısı",
             "question_tr": "Baş ağrınız var mı?",
             "answer_type": "yes_no"},
            {"canonical_symptom": "öksürük",
             "question_tr": "Öksürüğünüz var mı?",
             "answer_type": "yes_no"},
            {"canonical_symptom": "bulantı",
             "question_tr": "Bulantınız var mı?",
             "answer_type": "yes_no"},
            {"canonical_symptom": "boğaz ağrısı",
             "question_tr": "Boğaz ağrınız var mı?",
             "answer_type": "yes_no"},
        ]
    }
    (data_dir / "symptom_question_bank_tr.json").write_text(
        json.dumps(question_bank, ensure_ascii=False), encoding="utf-8"
    )

    import app.agents.info_gain_selector as ig_mod
    monkeypatch.setattr(ig_mod, "_DATA_DIR", data_dir)
    monkeypatch.setattr(ig_mod, "_CACHE_DIR", cache_dir)
    importlib.reload(ig_mod)
    return ig_mod.info_gain_selector


def test_selector_loads(stub_data):
    assert stub_data.is_loaded


def test_picks_max_information_gain_symptom(stub_data):
    """With equal weights, fever splits 2/2 — same as cough but cough is
    in 3/4. fever (2/4) gives the highest gain in this fixture."""
    weights = [
        ("Flu", 1.0),
        ("Migraine", 1.0),
        ("Cold", 1.0),
        ("Pneumonia", 1.0),
    ]
    pick = stub_data.select(
        candidate_weights=weights,
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    assert pick is not None
    # Best split is the one closest to 50/50 weighted; fever is exactly 50/50.
    assert pick["split"]["yes_mass"] == pytest.approx(0.5, abs=0.05)
    assert pick["info_gain"] > 0
    assert pick["question_tr"]


def test_skips_already_asked(stub_data):
    weights = [("Flu", 1.0), ("Migraine", 1.0), ("Cold", 1.0), ("Pneumonia", 1.0)]
    # Block fever — should pick something else.
    pick = stub_data.select(
        candidate_weights=weights,
        already_asked_canonical={"ateş"},
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    assert pick is not None
    assert pick["canonical_symptom"] != "ateş"


def test_returns_none_when_no_useful_split(stub_data):
    """A single candidate has no symptom that *splits* it — every
    symptom is either present in 100% or 0% of candidates."""
    pick = stub_data.select(
        candidate_weights=[("Flu", 1.0)],
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    assert pick is None


def test_returns_none_for_empty_candidates(stub_data):
    pick = stub_data.select(
        candidate_weights=[],
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    assert pick is None


def test_normalizes_weights(stub_data):
    """Same relative weights at different scales should yield the same pick."""
    pick_a = stub_data.select(
        candidate_weights=[("Flu", 0.1), ("Migraine", 0.1), ("Cold", 0.1), ("Pneumonia", 0.1)],
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    pick_b = stub_data.select(
        candidate_weights=[("Flu", 10.0), ("Migraine", 10.0), ("Cold", 10.0), ("Pneumonia", 10.0)],
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    assert pick_a["canonical_symptom"] == pick_b["canonical_symptom"]


def test_dominant_candidate_has_low_gain(stub_data):
    """When one candidate dominates (~95% weight), no symptom can yield
    high information gain because the prior is already near-certain."""
    pick_dom = stub_data.select(
        candidate_weights=[("Flu", 0.95), ("Migraine", 0.02), ("Cold", 0.02), ("Pneumonia", 0.01)],
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    pick_uniform = stub_data.select(
        candidate_weights=[("Flu", 1.0), ("Migraine", 1.0), ("Cold", 1.0), ("Pneumonia", 1.0)],
        already_asked_canonical=set(),
        confirmed_present=set(),
        confirmed_absent=set(),
    )
    if pick_dom and pick_uniform:
        assert pick_dom["info_gain"] < pick_uniform["info_gain"]
