# Kaggle Disease Description — TR Translation (Open Decision)

**Status:** Open product decision, tracked as Session Z bakiye item.
**Touches:** `backend/app/data/kaggle_cache/disease_descriptions.json`,
`backend/app/triage_engine.py::_lookup_disease_description`,
`backend/app/data/kaggle_condition_meta.json` (B3 addition).

## The gap

B3 added `kaggle_condition_meta.json` with `disease_description_tr` for
~29 Kaggle labels — but the underlying Kaggle matrix ships
`disease_descriptions.json` with **English** text for all ~41 labels.
When a label is not in B3's curated meta, the UI falls back to the
English Kaggle description. Mobile and dashboard both render it as-is.

Examples in production today:
- Heart attack → "A heart attack occurs when the flow of blood to
  the heart is severely reduced or blocked…" (EN)
- Fungal infection → already has TR meta ✅

## Three options

### A) Manual TR backfill — curation-heavy, deterministic

Extend `kaggle_condition_meta.json` from 29 → 41 labels. Each new
entry gets 2-3 sentences of reviewable TR prose. Same pattern as the
existing curated entries.

- Cost: ~1 hour of clinical authoring + review.
- Deterministic output — same text for every user, every session.
- No runtime dependency on LLM. Safe when LLM provider is down.
- Downside: static; doesn't adapt to tenant or patient context.

### B) LLM on-demand translation — runtime-heavy, flexible

Add a one-shot LLM call during triage turn assembly (after label
override, before payload build) that translates the EN description
to TR when no curated meta is present. Cache the translation keyed by
label in a small Supabase table or in-memory LRU.

- Cost: ~2 hours of code (client + cache + prompt + test mocks).
- First request per label is slow; cache amortizes.
- Can personalize (tenant language, reading level).
- Downside: cost per translation, occasional LLM downtime, harder
  to review clinically.

### C) Hybrid — manual for the top N, LLM for the tail

Author TR for the 10-15 most-common labels (already done in B3 for
the top 29). Let the LLM handle rare tail labels with a visible
caution footer in the UI ("Bu açıklama otomatik çevrildi").

- Cost: B3 already covers the expensive part; remaining 12 labels
  can take the LLM path.
- Balances deterministic quality on hot labels with coverage on tail.
- Downside: two render paths to maintain; footer adds UI complexity.

## My recommendation

**Option A** for round 1 — it's small, cheap, reviewable, and doesn't
add a new runtime dependency. B3 is already 70% of the way there;
finishing the backfill is less work than Option B's client + cache.
Revisit Option B/C only if the catalog grows beyond ~100 labels or
multi-tenant wording needs diverge.

## If Option A is chosen — 12 labels that still need TR

The unmerged set (present in Kaggle but not in
`kaggle_condition_meta.json`):

- Paralysis (brain hemorrhage)  — already routes through EMERGENCY
  override; safe to leave English as fallback.
- Heart attack                  — same (EMERGENCY-only).
- Osteoarthristis               — typo in Kaggle; already overridden
  to Turkish label but no description.
- (vertigo) Paroymsal Positional Vertigo → already in meta.
- Plus ~8 less-common labels in `disease_descriptions.json` that
  aren't in `disease_label_overrides.json` either.

First step if we proceed: grep for labels present in
`kaggle_cache/disease_descriptions.json` but missing from both
`disease_label_overrides.json` overrides AND
`kaggle_condition_meta.json` conditions. That diff is the backfill
list.

## Decision marker

When this is resolved, delete this file or reduce it to a one-line
link in `docs/CONDITION_HYPOTHESIS_LAYER_C2.md`'s follow-up section.
