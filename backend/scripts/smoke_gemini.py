#!/usr/bin/env python3
"""Smoke-test gemini_llm.generate() against the real Wiro endpoint.

Run this locally (or from a one-off CI job) BEFORE flipping
WIRO_GEMINI_LLM_ENABLED=1 in production. The script:

  1. Reads WIRO_API_KEY + WIRO_API_SECRET from env or the project
     .env file (same auto-discovery as fetch_wiro_schemas.ps1).
  2. Force-enables WIRO_GEMINI_LLM_ENABLED on the local settings
     instance (process-scoped — does NOT persist anywhere).
  3. Sends a minimal text-only prompt that any healthy gemini-3-pro
     deployment must answer in <30s.
  4. Reports OK/FAIL with the response (or error class + message)
     and exits 0/1 accordingly so a CI invocation surfaces the
     status correctly.

What this verifies (and what it doesn't):
    + WIRO_API_KEY/SECRET are valid for signature auth on the new
      AI surface (older API-key-only setups would 401 here).
    + gemini-3-pro task model is reachable + the wrapper's submit/
      poll/extract path works end-to-end.
    + The default text prompt produces a non-empty response.
    - NOT covered: long-context (262K tokens), multimodal (input_files),
      thinking_level=high. Add specific cases as needed before each
      production rollout that uses those features.

Usage::

    cd backend
    python scripts/smoke_gemini.py
    # exit 0 = success, prompt + response printed
    # exit 1 = failure, error class + message printed

Operator runbook reference: docs/runbooks/PRODUCTION_GEMINI_ROLLOUT.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


_SMOKE_PROMPT = (
    "Tek cümleyle, ne yaptığını söyle: 'Saç ekimi sonrası 7 gün "
    "süreyle başlık takılması gerektiği' bilgisini hastaya nasıl "
    "iletirsin?"
)


def _load_env_from_dotenv() -> None:
    """Light-touch .env loader. Only sets missing keys — running this
    script from a shell that already has WIRO_API_* exported wins."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def main() -> int:
    _load_env_from_dotenv()

    if not os.environ.get("WIRO_API_KEY"):
        print(
            "ERROR: WIRO_API_KEY missing from env / .env. "
            "Set it before running the smoke test.",
            file=sys.stderr,
        )
        return 1
    if not os.environ.get("WIRO_API_SECRET"):
        print(
            "ERROR: WIRO_API_SECRET missing from env / .env. "
            "The new gemini-3-pro model surface requires HMAC "
            "signature auth (legacy API-key-only mode is rejected).",
            file=sys.stderr,
        )
        return 1

    # Process-scoped flag flip — does not touch .env, does not
    # affect other shells / pods.
    os.environ["WIRO_GEMINI_LLM_ENABLED"] = "1"
    # Conftest stubs would rewrite Supabase URLs; we explicitly set
    # them so the wrapper can import without DB-init complaints.
    os.environ.setdefault("SUPABASE_URL", "http://supabase.smoke.local")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "smoke-stub")

    # Lazy import after env is set — settings is loaded at first
    # access by Pydantic BaseSettings, so we want WIRO_GEMINI_LLM_
    # ENABLED already in os.environ.
    from app.services.ai import gemini_llm

    if not gemini_llm.is_enabled():
        print(
            "ERROR: gemini_llm.is_enabled() returned False after the "
            "env flip. Check that WIRO_GEMINI_LLM_ENABLED is read by "
            "Pydantic BaseSettings as a bool and not a string.",
            file=sys.stderr,
        )
        return 1

    print(f"[smoke] prompt: {_SMOKE_PROMPT}\n")
    try:
        result = gemini_llm.generate(
            prompt=_SMOKE_PROMPT,
            thinking_level="low",       # cheapest path
            temperature=0.3,            # low creativity for clinical
            max_output_tokens=256,
            timeout=60.0,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            f"FAIL: gemini_llm.generate raised {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    if not result:
        print(
            "FAIL: gemini_llm.generate returned None. "
            "Likely WiroAuthError (check WIRO_API_SECRET) or task_error "
            "(check Wiro panel for the latest task status).",
            file=sys.stderr,
        )
        return 1

    print(f"[smoke] response (length={len(result)}):\n{result}\n")
    print("OK: gemini-3-pro returned a non-empty response.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
