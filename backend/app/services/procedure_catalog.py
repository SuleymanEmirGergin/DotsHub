"""Procedure catalog loader.

Reads ``app/data/procedures.json`` once at import time and exposes
lookup helpers. Catalog data is read-only at runtime; the JSON file is
the source of truth and can be edited directly without code changes.

Locale handling
    `name(procedure_id, locale)` falls back to Turkish then English if
    the requested locale is missing. Synonyms follow the same rule.

Why a dedicated module
    procedure_intent (synonym matching), the quote engine (price
    band + duration), and itinerary generation all read the catalog.
    Centralising the load means JSON parse errors surface once at
    import, not on every endpoint call.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "procedures.json"


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    """Parse procedures.json once; raise loudly if the file is missing
    or malformed — silent-pass would let a corrupted catalog ship to
    production without anyone noticing."""
    with _DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "procedures" not in data:
        raise ValueError(
            f"procedures.json: expected top-level 'procedures' key, got {list(data)}"
        )
    return data


def all_procedures() -> list[dict[str, Any]]:
    """Return every procedure in the catalog. Order matches JSON file."""
    return list(_load_raw()["procedures"])


def get_procedure(procedure_id: str) -> Optional[dict[str, Any]]:
    """Return one procedure by id, or None if unknown."""
    for p in all_procedures():
        if p.get("id") == procedure_id:
            return p
    return None


def procedure_ids() -> set[str]:
    """Return the full set of valid procedure ids — useful for input
    validation in route handlers."""
    return {p["id"] for p in all_procedures()}


def _locale_short(locale: Optional[str]) -> str:
    """Normalise a BCP-47 locale to its language subtag.

    "tr-TR" → "tr"; "en-US" → "en"; None → "tr" (default).
    """
    if not locale:
        return "tr"
    return locale.split("-")[0].split("_")[0].lower()


def name(procedure_id: str, locale: str | None) -> str:
    """Return the localised procedure name. Falls back to 'tr' then
    'en' then the procedure id itself if no name is registered."""
    p = get_procedure(procedure_id)
    if p is None:
        return procedure_id
    names = p.get("name", {})
    short = _locale_short(locale)
    return names.get(short) or names.get("tr") or names.get("en") or procedure_id


def synonyms(locale: str | None) -> Iterable[tuple[str, str]]:
    """Yield ``(synonym, procedure_id)`` pairs for the given locale.

    Useful for building a flat keyword index in the intent extractor.
    Synonyms are stored case-insensitively here — the extractor
    normalises user input the same way.
    """
    short = _locale_short(locale)
    for p in all_procedures():
        for syn in p.get("synonyms", {}).get(short, []):
            yield syn.lower(), p["id"]
