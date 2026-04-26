#!/usr/bin/env python3
"""Seed the `health_tourism_clinics` Supabase table from clinics.json.

Idempotent: an existing row with the same `id` is updated, not
duplicated. Run once on a fresh project, and again whenever
clinics.json changes if you want the database to reflect the JSON
file (production deployments will eventually edit the database
directly and stop running this script).

Usage:
    python scripts/seed_health_tourism_clinics.py
        [--dry-run]   show planned upserts without writing
        [--source PATH]   override the JSON path

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in env. Bails out
with exit 2 when those are missing, so a misconfigured CI step fails
loudly instead of silently no-op'ing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = REPO_ROOT / "app" / "data" / "clinics.json"


def _load_clinics(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("clinics", []))


def _to_row(clinic: dict[str, Any]) -> dict[str, Any]:
    """Map a clinics.json entry to a row matching the SQL schema.

    Unknown fields land in `metadata` so adding a new key to the JSON
    file doesn't break the seeder; the column is jsonb so we don't
    need to ALTER TABLE for v0 prototyping.
    """
    known = {
        "id", "name", "city", "country", "lat", "lon",
        "certifications", "languages", "procedures_offered",
        "package_features", "specialties_strength",
        "price_modifier", "years_experience", "before_after_count",
        "average_rating_5", "consult_response_hours",
    }
    metadata = {k: v for k, v in clinic.items() if k not in known}
    return {
        "id": clinic["id"],
        "name": clinic["name"],
        "city": clinic.get("city", ""),
        "country": clinic.get("country", "TR"),
        "lat": clinic.get("lat"),
        "lon": clinic.get("lon"),
        "certifications": clinic.get("certifications", []),
        "languages": clinic.get("languages", []),
        "procedures_offered": clinic.get("procedures_offered", []),
        "package_features": clinic.get("package_features", []),
        "specialties_strength": clinic.get("specialties_strength", []),
        "price_modifier": float(clinic.get("price_modifier", 1.0)),
        "years_experience": int(clinic.get("years_experience", 0)),
        "before_after_count": int(clinic.get("before_after_count", 0)),
        "average_rating_5": float(clinic.get("average_rating_5", 0.0)),
        "consult_response_hours": int(clinic.get("consult_response_hours", 24)),
        "is_active": True,
        "metadata": metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned upserts; do not write to Supabase.")
    parser.add_argument("--source", default=str(DEFAULT_JSON),
                        help=f"JSON source path (default: {DEFAULT_JSON})")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"[seed-clinics] source not found: {source_path}", file=sys.stderr)
        return 2

    clinics = _load_clinics(source_path)
    if not clinics:
        print("[seed-clinics] source has 0 clinics; nothing to do",
              file=sys.stderr)
        return 1

    rows = [_to_row(c) for c in clinics]

    if args.dry_run:
        print(f"[seed-clinics] DRY RUN — would upsert {len(rows)} rows:")
        for r in rows:
            print(f"  - {r['id']:40s} {r['city']:12s} "
                  f"({len(r['procedures_offered'])} procedures, "
                  f"{len(r['languages'])} languages)")
        return 0

    # Lazy import — keeps --dry-run and --help working without
    # requiring supabase or env vars in the dev shell.
    sys.path.insert(0, str(REPO_ROOT))
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print(
            "[seed-clinics] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing — "
            "set both before running without --dry-run.",
            file=sys.stderr,
        )
        return 2
    from app.supabase_client import get_supabase
    sb = get_supabase()

    res = sb.table("health_tourism_clinics").upsert(rows, on_conflict="id").execute()
    written = len(getattr(res, "data", []) or [])
    print(f"[seed-clinics] upserted {written}/{len(rows)} rows")
    return 0 if written == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
