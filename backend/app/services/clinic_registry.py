"""Clinic registry loader.

Reads ``app/data/clinics.json`` once at import time. Production
deployments will eventually move this to a Supabase table — the
loader's narrow public API (``all_clinics``, ``clinics_for_procedure``,
``get_clinic``) is the only surface the rest of the codebase depends
on, so swapping the storage backend later is a 1-file change.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "clinics.json"


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "clinics" not in data:
        raise ValueError(
            f"clinics.json: expected top-level 'clinics' key, got {list(data)}"
        )
    return data


def all_clinics() -> list[dict[str, Any]]:
    return list(_load_raw()["clinics"])


def get_clinic(clinic_id: str) -> Optional[dict[str, Any]]:
    for c in all_clinics():
        if c.get("id") == clinic_id:
            return c
    return None


def clinics_for_procedure(procedure_id: str) -> list[dict[str, Any]]:
    """Return every clinic whose ``procedures_offered`` contains the id."""
    return [
        c for c in all_clinics()
        if procedure_id in c.get("procedures_offered", [])
    ]


def maps_url(clinic: dict[str, Any]) -> Optional[str]:
    """Build a Google Maps URL from clinic lat/lon. None if no coordinates."""
    lat, lon = clinic.get("lat"), clinic.get("lon")
    if lat is None or lon is None:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
