# Final Decision Engine Specification (A+B Merge)

## Overview

The **Final Decision Engine** merges two independent scoring signals into a unified specialty ranking:

- **Layer A** (disease candidates): Disease → specialty mapping with prior points
- **Layer B** (rules scorer): Keyword/phrase-based specialty scoring

The result is a deterministic, explainable specialty recommendation.

## Algorithm

### Input

1. `rules_scores`: From Specialty Scorer (Layer B)
   - Per-specialty: `{score, keyword_score, phrase_score, ...}`

2. `disease_candidates`: From Candidate Generator (Layer A)
   - Ranked list: `[{disease_label, score_0_1, ...}]`

### Step 1: Compute Specialty Priors (from Layer A)

Each disease candidate is mapped to a specialty via `disease_to_specialty.json`.
Points are awarded based on rank:

| Rank | Points |
|------|--------|
| 1 | 4 |
| 2 | 3 |
| 3 | 2 |
| 4 | 1 |
| 5 | 1 |

```
prior_value = rank_points × mapping_confidence

specialty_prior_score[specialty_id] += prior_value
```

**Example:**
- Rank 1: Migraine (specialty: neurology, confidence: 0.9) → neurology gets 4 × 0.9 = 3.6
- Rank 2: GERD (specialty: internal_gi, confidence: 0.9) → internal_gi gets 3 × 0.9 = 2.7

### Step 2: Merge Scores

```
final_score[specialty_id] = rules_score[specialty_id] + specialty_prior_score[specialty_id]
```

### Step 3: Deterministic Tie-Breaking

When multiple specialties have the same `final_score`, tie-break order:

1. `final_score` — descending (higher wins)
2. `keyword_score` — descending (more keyword matches wins)
3. `specialty_id` — alphabetical ascending (deterministic last resort)

### Output

```json
{
  "neurology": {
    "final_score": 12.6,
    "rules_score": 9.0,
    "prior_score": 3.6,
    "keyword_score": 6.0,
    "specialty_tr": "Nöroloji"
  },
  "internal_gi": {
    "final_score": 5.7,
    "rules_score": 3.0,
    "prior_score": 2.7,
    "keyword_score": 3.0,
    "specialty_tr": "Dahiliye (gerekirse Gastroenteroloji)"
  }
}
```

## Disease-to-Specialty Mapping

The `disease_to_specialty.json` file maps ~40 Kaggle disease labels to our 11 specialty IDs:

| Specialty ID | Example Diseases |
|-------------|-----------------|
| `neurology` | Migraine, Paralysis, Vertigo |
| `cardiology` | Heart attack, Hypertension, Varicose veins |
| `internal_gi` | GERD, Diabetes, Hepatitis A-E, Jaundice |
| `pulmonology` | Bronchial Asthma, Pneumonia, Tuberculosis |
| `dermatology` | Fungal infection, Acne, Psoriasis, Chicken pox |
| `orthopedics_rheum` | Arthritis, Cervical spondylosis, Osteoarthritis |
| `ent` | Common Cold |
| `urology_internal` | Urinary tract infection |

Each mapping includes a `confidence` (0.0–1.0) reflecting how strongly the disease maps to a single specialty.

## Properties

- **Deterministic**: Same inputs always produce the same output
- **Explainable**: Each score component (rules vs. prior) is visible
- **Robust**: Either layer can operate independently — if Layer A has no data, Layer B rules still work; if rules find nothing, disease priors still inform routing
