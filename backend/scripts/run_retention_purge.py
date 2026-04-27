"""Run the Supabase retention purge function.

KVKK Md.7 / GDPR Art.5(1)(e). Calls the Postgres function
`public.app_retention_purge(...)` defined in
`backend/sql/20260427_retention_purge.sql` with windows from
`backend/app/core/config.py:RETENTION_DAYS_*`.

Designed for two scheduling targets:
  - GitHub Actions cron (default: prints to stdout, exit code reflects
    success/failure for CI alerting).
  - Manual ad-hoc invocation from an operator's machine.

If you'd rather run the purge inside Postgres (no external dependency),
schedule the SQL function directly via pg_cron — see RETENTION_POLICY.md
option A. This script exists for environments where pg_cron isn't
available or where ops prefers GH Actions audit log over Postgres
cron.job_run_details.

Exit codes:
    0  success (printed JSON summary on stdout)
    1  config / connection error (no purge attempted)
    2  RPC raised — Supabase returned an error

Usage:
    python backend/scripts/run_retention_purge.py
    python backend/scripts/run_retention_purge.py --dry-run
    python backend/scripts/run_retention_purge.py --tombstone-days 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows that would be affected without deleting.",
    )
    # Window overrides — default to None so we can fall back to
    # config.py values, and pass through explicit overrides to the SQL
    # function. SQL-side defaults match config.py defaults so omitting
    # all flags is the production-safe call.
    p.add_argument("--tombstone-days", type=int, default=None)
    p.add_argument("--purge-days", type=int, default=None)
    p.add_argument("--events-days", type=int, default=None)
    p.add_argument("--llm-calls-days", type=int, default=None)
    p.add_argument("--feedback-days", type=int, default=None)
    p.add_argument("--push-tokens-days", type=int, default=None)
    return p


def _resolve_windows(args: argparse.Namespace) -> Dict[str, int]:
    """CLI args > config.py defaults. Returns the kwargs for RPC."""
    # Lazy import: the script can be invoked in CI environments that
    # haven't pip-installed the full backend tree yet (e.g. a slim
    # actions runner). Importing inside the function lets `--help`
    # work without dependencies.
    from app.core.config import settings

    cfg = {
        "tombstone_days": args.tombstone_days
        if args.tombstone_days is not None
        else settings.RETENTION_DAYS_SESSIONS_TOMBSTONE,
        "purge_days": args.purge_days
        if args.purge_days is not None
        else settings.RETENTION_DAYS_SESSIONS_PURGE,
        "events_days": args.events_days
        if args.events_days is not None
        else settings.RETENTION_DAYS_EVENTS,
        "llm_calls_days": args.llm_calls_days
        if args.llm_calls_days is not None
        else settings.RETENTION_DAYS_LLM_CALLS,
        "feedback_days": args.feedback_days
        if args.feedback_days is not None
        else settings.RETENTION_DAYS_FEEDBACK,
        "push_tokens_days": args.push_tokens_days
        if args.push_tokens_days is not None
        else settings.RETENTION_DAYS_PUSH_TOKENS,
    }
    return cfg


def main() -> int:
    args = _build_parser().parse_args()

    if not os.environ.get("SUPABASE_URL") or not os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    ):
        print(
            "error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set",
            file=sys.stderr,
        )
        return 1

    try:
        kwargs = _resolve_windows(args)
        from app.db import supabase  # type: ignore[import-not-found]
    except Exception as exc:
        print(f"error: config/import failed: {exc}", file=sys.stderr)
        return 1

    rpc_args: Dict[str, Any] = {**kwargs, "dry_run": args.dry_run}

    try:
        resp = supabase.rpc("app_retention_purge", rpc_args).execute()
    except Exception as exc:
        print(f"error: RPC raised: {exc}", file=sys.stderr)
        return 2

    rows = getattr(resp, "data", None) or []
    summary = rows[0] if rows else {}

    print(json.dumps({"ok": True, "summary": summary, "args": rpc_args}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
