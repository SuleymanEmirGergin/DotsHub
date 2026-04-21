# Runbook: Kaggle Refresh Workflow Failed

## Quick checklist (alert → green)

- [ ] Open the failing workflow run
      (`.github/workflows/kaggle-ingest.yml`) and find the step that
      went red
- [ ] Match the step to one of the failure modes below
- [ ] Decide: wait / patch the dataset slug / pin an older Kaggle
      revision / bump a guardrail threshold
- [ ] Re-run the workflow (`workflow_dispatch`); if the fix lands in
      cache files, the next automatic Monday run will confirm
- [ ] Post-incident note in `docs/incidents/` if user-visible impact

## Scope

This runbook covers the `Kaggle Ingest` workflow and nothing else.
The workflow only touches `backend/app/data/kaggle_cache/*.json` +
produces a PR — it does not deploy anything. A failure here blocks
the weekly cache refresh until resolved, but does NOT affect
production traffic: the backend keeps serving with the last-merged
cache until the next PR lands.

## Severity

- **P3** by default: production is unaffected, next week's refresh
  can be delayed without observable harm.
- **P2** if the Kaggle dataset changed in a way that breaks the
  golden-flow gate — the workflow correctly refuses to open the PR,
  but the data pipeline drifts from upstream until a human decides
  whether to accept the break (bump thresholds) or pin the previous
  revision.
- **P1** only if the *previous* merged cache contains a regression
  that's slipping through to prod (rare — golden flows catch this
  on every PR, not just the Kaggle PR). Treat as a corpus incident,
  not a refresh incident, and see `docs/runbooks/LLM_PROVIDER_DOWN.md`
  for precedent on emergency override decisions.

## Failure mode: `Fetch Kaggle dataset` step

Exit non-zero on the `fetch_kaggle_dataset.py` line.

Most common causes:

- **Kaggle credentials rotated.** `KAGGLE_USERNAME` / `KAGGLE_KEY`
  repo secrets are stale. Error usually includes `403 Forbidden` or
  `Unauthorized`. Fix: rotate the secret from Kaggle account
  settings → API → *Create New Token*, paste the new
  `username`/`key` into the repo secrets.
- **Dataset slug typo / moved dataset.** The default slug
  (`itachi9604/disease-symptom-description-dataset`) has been stable
  for years but Kaggle occasionally renames. Fix: open the dataset
  on kaggle.com, copy the canonical `owner/name`, and either
  override via `workflow_dispatch` input or update the
  `KAGGLE_DATASET_SLUG` repo variable.
- **Kaggle outage.** Check <https://status.kaggle.com>. Re-run the
  workflow when recovered.

## Failure mode: `Validate kaggle mapping quality` step

Exit non-zero on `validate_kaggle_mapping.py`.

This means the new dataset passed the fetch/preprocess pipeline
but `kaggle_mapping_guardrails.json` thresholds flag it as risky.
The step prints the specific violations — typically one of:

- **`min_total_symptoms` below floor** — a disease has fewer
  symptoms than we trust for Jaccard scoring.
- **`min_non_null_ratio_critical`** — too many symptoms lack a
  Turkish canonical mapping, which would make the new disease
  unreachable from user text.
- **`max_en_symptoms_per_canonical_warning`** — multiple English
  symptoms collapse onto one Turkish canonical.

**Triage path:**

1. Read the report JSON in `backend/reports/` (uploaded as a
   workflow artifact) to see which disease/symptom tripped which
   rule.
2. If the Kaggle dataset legitimately added a new disease we want
   to support: update `synonyms_tr.json` / `specialty_keywords_tr.json`
   / `kaggle_condition_meta.json` to give the new disease a Turkish
   surface, land those changes first, then re-run the workflow.
3. If the violation is an artefact of a bad upstream revision:
   pin the previous Kaggle revision (via `workflow_dispatch` input
   with the older slug if Kaggle kept it, or freeze by committing
   the current cache as the canonical state and disabling the
   schedule temporarily).

## Failure mode: `Run golden flow suite against new cache`

Exit non-zero on `test_golden_flows.py`.

The highest-stakes failure: the upstream data changed in a way
that breaks one of our safety-critical fixtures (e.g. chest pain
no longer routes to cardiology because Heart attack's symptom
profile shifted).

**Triage path:**

1. The step prints the failing assertion(s) — usually
   `final_type != EMERGENCY` or `recommended_specialty` mismatch.
2. If the failure is legit (the new data is better and the fixture
   was over-fit): update the fixture + add a note in the session
   commit explaining the judgement.
3. If the failure is a regression (Kaggle data got noisier): do
   NOT merge the refresh. Either:
   a) Pin the previous revision (see fetch-step runbook above) and
      let the next scheduled run try a fresh revision.
   b) Add a compensating synonym / keyword in our layer that
      restores the expected behaviour, commit that separately,
      then re-run the refresh workflow.

## Failure mode: `Capture real_corpus value` step

This step is INTENTIONALLY tolerant — the `|| true` means a
non-zero exit from `test_real_corpus.py` doesn't fail the workflow;
we still want the PR to open so a human can review the cache diff
even when the new data drops below the real_corpus threshold.

If the PR body shows a large negative delta (e.g. −10 points),
treat it like a guardrail failure:

- Do NOT merge the auto-PR blindly.
- Triage the top failing scenarios (listed in the job log); they
  will frequently cluster on a single disease that got noisier
  symptoms.
- Either: patch the cache (commit a manual override of the
  offending disease's symptom list) or pin the previous Kaggle
  revision as above.

## Failure mode: `Create pull request` step

Usually a token/permissions issue with `peter-evans/create-pull-request`.
Check:

- Settings → Actions → General → *Workflow permissions* — must be
  `Read and write`.
- The `automation/kaggle-cache-refresh` branch from a prior run may
  be stuck open; delete it manually and re-trigger.

## Graceful no-op path (not a failure)

The workflow skips PR creation entirely when the 4 cache files
are byte-identical to the prior snapshot. You'll see a
`::notice::` in the summary; this is the correct behaviour, NOT a
failure — the upstream dataset hadn't changed since the last
merged refresh.

## Post-incident checklist

- [ ] **Timeline**: scheduled run time, alert time, merge / skip
      time (UTC)
- [ ] **Root cause**: one-line summary (auth / data drift / slug
      change / network)
- [ ] **Action items**: bumped guardrail? new synonym? slug pin?
      none?
- [ ] Close the workflow run's failure annotation in GitHub
