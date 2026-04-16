"""Test configuration: set required environment variables before any app imports."""

from __future__ import annotations

import os

# db.py raises RuntimeError at import time when these are missing.
# Set stubs so the module loads without hitting a real Supabase instance.
os.environ.setdefault("SUPABASE_URL", "https://fake-test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-test-key")
os.environ.setdefault("ADMIN_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("IP_HASH_SALT", "test-salt-for-ci")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("RESEND_API_KEY", "")
os.environ.setdefault("SEND_SUMMARY_EMAIL", "0")

# Force in-memory rate limiting in tests: disable Redis so setUp/tearDown
# can reliably clear _SEND_SUMMARY_BUCKETS / _BUCKETS between test methods.
# Without this, a live Redis instance (if present in the dev environment)
# would be used and bucket clearing via module-level dicts would have no effect.
os.environ["REDIS_URL"] = ""

# Raise the general triage/feedback rate limit high enough that the full
# test suite never exhausts it (no tests check for 429 on those endpoints).
# The send-summary limit stays at its default (5) because dedicated rate-limit
# tests rely on it and use setUp/tearDown to manage the bucket themselves.
os.environ.setdefault("RATE_LIMIT_MAX_REQ", "1000")
