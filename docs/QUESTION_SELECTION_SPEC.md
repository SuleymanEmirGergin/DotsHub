# Question Selection Specification

## Overview

The **Question Selector** is a deterministic engine that chooses the most discriminative next question to ask the user. It analyzes the current disease candidate list to find symptoms that best differentiate between remaining candidates.

The LLM-based Question Generator is used as a **fallback** only when the deterministic selector cannot find a suitable question.

## Algorithm

### Input

- `disease_candidates`: Ranked list from Candidate Generator (Layer A)
  - Each candidate has `matched_symptoms` and `missing_symptoms`
- `known_symptoms`: Set of canonical symptoms already confirmed/denied
- `asked_symptoms`: Set of canonical symptoms already asked about

### Step 1: Collect Candidate Symptoms

For each disease candidate, collect all symptoms (matched + missing) in Kaggle space. Count how many candidates share each symptom.

### Step 2: Filter

Remove symptoms that:
- Have no canonical Turkish mapping
- Are already in `known_symptoms` or `asked_symptoms`
- Have no question template in the question bank

### Step 3: Compute Discriminative Score

For each remaining symptom:

```
count = number of candidates that include this symptom
C = total number of candidates

disc(s) = 1.0 - |count / C - 0.5|
```

**Interpretation:**
- `disc(s) = 1.0` when `count = C/2` — the symptom divides candidates perfectly in half
- `disc(s) = 0.5` when `count = 0` or `count = C` — the symptom provides no discrimination

### Step 4: Select Best

1. Group by canonical symptom (keep highest disc_score per canonical)
2. Sort: `disc_score` descending, then `canonical_symptom` alphabetical (deterministic)
3. Return the top entry with its question template

### Step 5: Fallback

If no suitable question is found (empty candidates, no bank entries, or fewer than 2 candidates):
- Return `None`
- Orchestrator triggers the LLM Question Generator as fallback

### Output

```json
{
  "canonical_symptom": "bulantı",
  "question_tr": "Mide bulantısı var mı?",
  "answer_type": "yes_no"
}
```

Or `None` → LLM fallback.

## Question Bank

The question bank (`symptom_question_bank_tr.json`) contains ~56 deterministic question templates:

```json
{
  "canonical_symptom": "bulantı",
  "question_tr": "Mide bulantısı var mı?",
  "answer_type": "yes_no"
}
```

Each entry maps a canonical symptom to a Turkish yes/no question. The bank covers the most common symptoms across the disease database.

## Example

Given 5 disease candidates where:
- 3/5 have `nausea` → disc = 1.0 - |3/5 - 0.5| = 1.0 - 0.1 = **0.9**
- 1/5 have `chest_pain` → disc = 1.0 - |1/5 - 0.5| = 1.0 - 0.3 = **0.7**
- 5/5 have `headache` → disc = 1.0 - |5/5 - 0.5| = 1.0 - 0.5 = **0.5**

The selector picks `nausea` (disc=0.9) because it best discriminates between candidates.

## Properties

- **Deterministic**: Same candidates always produce the same question
- **Information-theoretic**: Maximizes information gain per question
- **Efficient**: No LLM call needed for most questions
- **Graceful degradation**: Falls back to LLM when bank is exhausted
