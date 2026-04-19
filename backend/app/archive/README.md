# Archived modules

Modules kept in the tree for historical reference but no longer
imported anywhere in the live app. They do NOT run in production;
`app.main` does not include any router or class from this folder.

## Why archived, not deleted

1. Pragmatic: if a future feature turns out to need the experimental
   orchestrator path or the v2 question selector's heuristic, we'd
   rather rediscover them via git than reinvent.
2. Docstring / decision references in the main tree still point
   here (e.g. `top_conditions_filter.py` mentions
   `orchestrator_v5.build_result` as the original integration
   target). Breaking those references would make the comments
   worse, not better.

## What's here

- **`question_selector_v2.py`** — first-pass question-selection
  heuristic. Superseded by `question_selector_v3.py` (live path).
  No imports found anywhere in the backend as of 2026-04-18 audit.
- **`orchestrator_v5.py`** — experimental orchestrator that was
  the first place to wire `emergency_router.evaluate_emergency`.
  Superseded by `triage_engine.run_orchestrator_turn` (live path,
  wired in RC #1b). Imported only by `api_v5.py`, also archived.
- **`api_v5.py`** — the `/v1` API façade that fronts
  `orchestrator_v5`. Never mounted in `main.py`. Safe to archive.

## Policy

Don't import FROM this folder into live code. If something here
becomes useful again, promote it back to `app/` with tests and
update this README.
