# Candidate Generator Specification (Layer A)

## Overview

The **Candidate Generator** (Layer A) uses **weighted Jaccard similarity** to produce a ranked list of disease candidates based on the user's reported symptoms. It operates entirely on deterministic data — no LLM is involved.

## Data Sources

| File | Content |
|------|---------|
| `kaggle_cache/disease_symptoms.json` | Disease → symptom list matrix (~40 diseases, ~130 symptoms) |
| `kaggle_cache/symptom_severity.json` | Symptom → weight (1–7 scale) |
| `kaggle_cache/kaggle_to_canonical.json` | Kaggle symptom names → Turkish canonical names |
| `candidate_generator.json` | Algorithm parameters (top_k, min_score, weights) |

## Algorithm

### Input

- `canonical_symptoms_user`: Set of Turkish canonical symptom names from the Symptom Interpreter + user confirmations.

### Step 1: Map to Kaggle Space

User's canonical Turkish symptoms are reverse-mapped to Kaggle symptom names using `kaggle_to_canonical.json`:

```
"baş ağrısı" → ["headache"]
"öksürük" → ["cough", "phlegm", "mucoid_sputum", "rusty_sputum", "blood_in_sputum"]
```

### Step 2: Weighted Jaccard Similarity

For each disease `D` in the database:

```
U = user's Kaggle symptoms (after reverse mapping)
D_syms = disease's symptom set

intersection = U ∩ D_syms
union = U ∪ D_syms

w(s) = default_weight + severity(s) × severity_multiplier
     = 1.0 + severity(s) × 0.25

score = Σ w(s) for s in intersection
        ─────────────────────────────
        Σ w(s) for s in union
```

### Step 3: Filter & Rank

1. Filter: `score >= min_score_to_include` (default: 0.05)
2. Sort: `score` descending, then `disease_label` alphabetical (deterministic tie-break)
3. Return top `top_k` (default: 5)

### Output

```json
[
  {
    "disease_label": "Migraine",
    "score_0_1": 0.42,
    "matched_symptoms": ["headache", "nausea", "vomiting"],
    "missing_symptoms": ["blurred_and_distorted_vision", "stiff_neck"]
  }
]
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `top_k` | 5 | Maximum candidates to return |
| `min_score_to_include` | 0.05 | Minimum Jaccard score threshold |
| `default_symptom_weight` | 1.0 | Base weight for each symptom |
| `severity_weight_multiplier` | 0.25 | How much severity adds to weight |

## Severity Weighting

The severity from `Symptom-severity.csv` (scale 1–7) boosts the importance of clinically significant symptoms:

- `headache` (severity 3): w = 1.0 + 3×0.25 = **1.75**
- `chest_pain` (severity 6): w = 1.0 + 6×0.25 = **2.5**
- `altered_sensorium` (severity 7): w = 1.0 + 7×0.25 = **2.75**

This means matching or missing a high-severity symptom has more impact on the score.

## Integration

The Candidate Generator is called after the Symptom Interpreter in every orchestrator cycle. Its output feeds into:

1. **Final Decision Engine** — to compute specialty priors from disease rankings
2. **Question Selector** — to identify discriminative symptoms for the next question
