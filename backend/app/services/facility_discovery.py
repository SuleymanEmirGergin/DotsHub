"""Facility discovery service backed by OpenStreetMap Nominatim."""

from __future__ import annotations

import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_TAGS = ["hospital", "clinic"]
DEFAULT_CITY = "Istanbul"
DISCLAIMER_TR = "Bu liste bilgilendirme amaclidir. Tibbi yonlendirme degildir."
USER_AGENT = "dotshub-pre-triage/1.0"


@lru_cache(maxsize=1)
def _load_specialty_facility_map() -> Dict[str, List[str]]:
    repo_root = Path(__file__).resolve().parents[3]
    map_path = repo_root / "config" / "specialty_facility_map.json"
    try:
        with map_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return {str(k): [str(t) for t in v] for k, v in raw.items() if isinstance(v, list)}
    except Exception as e:
        logger.warning("Failed to load specialty facility map: %s", e)
    return {}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    )
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _query_nominatim(client: httpx.Client, q: str, limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    try:
        resp = client.get(
            NOMINATIM_URL,
            params={
                "q": q,
                "format": "jsonv2",
                "limit": limit,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()
        return (data if isinstance(data, list) else [], False)
    except Exception as e:
        logger.info("Nominatim unavailable, facility discovery skipped (%s): %s", q, e)
        return [], True


def _parse_coord(row: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    try:
        return float(row.get("lat")), float(row.get("lon"))
    except Exception:
        return None


def discover_facilities(
    city: str,
    specialty_key: str,
    limit: int = 5,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Dict[str, Any]:
    if not settings.FACILITY_DISCOVERY_ENABLED:
        return {
            "specialty_id": str(specialty_key or ""),
            "city": city or DEFAULT_CITY,
            "items": [],
            "disclaimer": DISCLAIMER_TR,
        }

    specialty_key = str(specialty_key or "").strip()
    if not specialty_key:
        return {
            "specialty_id": "",
            "city": city or DEFAULT_CITY,
            "items": [],
            "disclaimer": DISCLAIMER_TR,
        }

    specialty_map = _load_specialty_facility_map()
    tags = specialty_map.get(specialty_key, DEFAULT_TAGS)
    city = city or DEFAULT_CITY

    city_center: Optional[Tuple[float, float]] = None
    if lat is not None and lon is not None:
        try:
            city_center = (float(lat), float(lon))
        except (TypeError, ValueError):
            pass
    items: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    with httpx.Client(
        timeout=settings.FACILITY_DISCOVERY_TIMEOUT_SECONDS,
        trust_env=False,
    ) as client:
        if city_center is None:
            city_rows, city_query_failed = _query_nominatim(client, q=city, limit=1)
            if city_query_failed:
                return {
                    "specialty_id": specialty_key,
                    "city": city,
                    "items": [],
                    "disclaimer": DISCLAIMER_TR,
                }
            if city_rows:
                city_center = _parse_coord(city_rows[0])

        for tag in tags:
            q = f"{specialty_key} {tag} {city}"
            rows, query_failed = _query_nominatim(client, q=q, limit=limit)
            if query_failed:
                break
            for row in rows:
                display = str(row.get("display_name", "")).strip()
                if not display:
                    continue

                haystack = (
                    f"{row.get('class', '')} {row.get('type', '')} {display}"
                ).lower()
                if tag.lower() not in haystack:
                    continue

                name = str(row.get("name") or display.split(",")[0]).strip()
                if not name:
                    continue

                dedupe_key = f"{name.lower()}|{display.lower()}"
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)

                row_type = str(row.get("type") or row.get("class") or tag).lower()
                coords = _parse_coord(row)
                item: Dict[str, Any] = {
                    "name": name,
                    "type": row_type,
                    "address": display,
                }
                if coords:
                    item["lat"] = coords[0]
                    item["lon"] = coords[1]
                if city_center and coords:
                    dist = _haversine_km(city_center[0], city_center[1], coords[0], coords[1])
                    item["distance_km"] = round(dist, 1)

                items.append(item)
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break

    if items and any("distance_km" in i for i in items):
        items.sort(key=lambda i: i.get("distance_km", 10**9))

    return {
        "specialty_id": specialty_key,
        "city": city,
        "items": items[:limit],
        "disclaimer": DISCLAIMER_TR,
    }
