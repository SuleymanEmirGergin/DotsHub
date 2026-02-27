"""GET /v1/facilities — standalone facility discovery endpoint."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.services.facility_discovery import discover_facilities, DEFAULT_CITY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/facilities",
    summary="List facilities by specialty and optional location",
    description="Returns nearby health facilities for a given specialty. Optional lat/lon for distance sorting. Shown in OpenAPI under tag 'Facilities'.",
    tags=["Facilities"],
)
def get_facilities(
    specialty: str = Query(..., description="Specialty key (e.g. neurology, cardiology)"),
    city: Optional[str] = Query(None, description="City name; default Istanbul"),
    lat: Optional[float] = Query(None, description="User latitude for distance sorting"),
    lon: Optional[float] = Query(None, description="User longitude for distance sorting"),
    limit: int = Query(5, ge=1, le=20, description="Max number of facilities"),
):
    try:
        result = discover_facilities(
            city=city or DEFAULT_CITY,
            specialty_key=specialty,
            limit=limit,
            lat=lat,
            lon=lon,
        )
        return result
    except Exception as e:
        logger.warning("Facility discovery failed: %s", e)
        return {
            "specialty_id": specialty,
            "city": city or DEFAULT_CITY,
            "items": [],
            "disclaimer": "Bu liste bilgilendirme amaclidir. Tibbi yonlendirme degildir.",
        }
