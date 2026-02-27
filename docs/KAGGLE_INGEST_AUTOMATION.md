# Kaggle Ingest Automation

This project now includes an automated pipeline that:

1. Downloads Kaggle CSVs
2. Normalizes them into `backend/raw_data/`
3. Rebuilds deterministic cache files in `backend/app/data/kaggle_cache/`
4. Runs mapping guardrails via `preprocess_kaggle.py`
5. Opens a PR when cache files changed

## Workflow

- File: `.github/workflows/kaggle-ingest.yml`
- Trigger:
  - Scheduled: every Monday at 03:00 UTC
  - Manual: `workflow_dispatch`

## Required GitHub Secrets

- `KAGGLE_USERNAME`
- `KAGGLE_KEY`

Without these secrets, the workflow will fail at download step.

## Optional GitHub Variable

- `KAGGLE_DATASET_SLUG` (format: `owner/name`)

Priority order for dataset slug:

1. Manual input from `workflow_dispatch`
2. Repo variable `KAGGLE_DATASET_SLUG`
3. Default in workflow: `itachi9604/disease-symptom-description-dataset`

## Local Equivalent

From `backend/`:

```bash
python scripts/fetch_kaggle_dataset.py --dataset-slug owner/name
python scripts/preprocess_kaggle.py
```

## Notes

- Only cache files under `backend/app/data/kaggle_cache/` are included in auto PRs.
- Validation reports are still generated under `backend/reports/` but are ignored by git.
