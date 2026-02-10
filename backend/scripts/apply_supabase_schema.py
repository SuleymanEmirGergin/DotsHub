"""Apply SQL schema migrations directly to Supabase Postgres."""

from __future__ import annotations

import asyncio
import argparse
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
import os


async def apply_sql(db_url: str, sql_text: str) -> None:
    conn = await asyncpg.connect(dsn=db_url)
    try:
        await conn.execute(sql_text)
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Supabase schema SQL file.")
    parser.add_argument(
        "--sql",
        default="sql/20260210_supabase_triage_schema.sql",
        help="Path to SQL file, relative to backend/ root.",
    )
    args = parser.parse_args()

    backend_root = Path(__file__).resolve().parents[1]
    load_dotenv(backend_root / ".env")

    db_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("SUPABASE_DB_URL is missing in environment/.env", file=sys.stderr)
        return 1

    sql_path = (backend_root / args.sql).resolve()
    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 1

    sql_text = sql_path.read_text(encoding="utf-8")

    print(f"Applying schema: {sql_path}")
    try:
        asyncio.run(apply_sql(db_url, sql_text))
    except Exception as exc:
        print(f"Schema apply failed: {exc}", file=sys.stderr)
        return 1

    print("Schema applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
