# Branch Protection Checklist

Use this checklist when configuring protection rules for `main`.

## Required Branch Protection Settings

- Require a pull request before merging
- Require approvals: minimum `1`
- Dismiss stale pull request approvals when new commits are pushed
- Require conversation resolution before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict direct pushes to `main`
- Include administrators (recommended)

## Required Status Checks

Mark these checks as required in branch protection:

- `golden-flow-regression / golden-flow-regression` (from `backend-regression.yml`)
- `dashboard-quality / dashboard-quality` (from `dashboard-quality.yml`)

## Optional but Recommended Checks

- `supabase-db-smoke / supabase-db-smoke`
- `guardrail / guardrail`

## Rollout Steps

1. Merge the workflow files to `main`.
2. Run each workflow at least once on `main` so GitHub registers check names.
3. Open repository settings: `Settings -> Branches -> Branch protection rules`.
4. Edit rule for `main` and enable the required checks above.
5. Verify by opening a draft PR and checking that merge is blocked until checks pass.
