"""Health-tourism route package.

The original `app/api/routes/quote.py` grew to ~650 lines with three
endpoints. We split it by endpoint so each file is self-contained and
the test layout (one test file per endpoint) mirrors the route
layout.

Public API: `router` aggregates the three sub-routers. main.py
includes it once with `prefix="/v1"`.

Layout:
    _shared.py    — disclaimers, make_meta, bump_*_metric helpers,
                    _resolve_procedure_id, _parse_arrival_date,
                    _dispatch_and_record (lead bg task)
    quote.py      — POST /v1/quote
    itinerary.py  — POST /v1/quote/itinerary
    lead.py       — POST /v1/quote/lead
"""
from fastapi import APIRouter

from . import itinerary, lead, quote

router = APIRouter()
router.include_router(quote.router)
router.include_router(itinerary.router)
router.include_router(lead.router)

__all__ = ["router"]
