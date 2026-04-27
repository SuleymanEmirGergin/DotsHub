"""Itinerary engine — generate a day-by-day plan for a procedure visit.

Single public entry point: ``generate(procedure_id, clinic_id, arrival_date,
locale)`` returns an ``Itinerary`` instance. The route handler shapes
that into an ``ITINERARY`` envelope.

Data sources
    procedures.json + clinics.json (existing) for procedure metadata
    and clinic info; itinerary_activities.json (i18n labels per activity);
    itinerary_templates.json (per-category schedules). Three files
    instead of one bloats the JSON tree slightly but keeps each
    concern editable in isolation — adding a new language to copy
    doesn't touch templates, adding a new category schedule doesn't
    touch labels.

Why deterministic templates, not LLM-generated
    Same reason quote_engine is rule-driven: predictable, auditable,
    multilingual without translation drift, and a clinical reviewer
    can read the template and sign off. LLM-generated copy would
    change between runs, which makes it impossible to put on a quote
    PDF that the patient takes to a doctor.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple, Optional

from app.services import clinic_registry, procedure_catalog

logger = logging.getLogger(__name__)

_ACTIVITIES_PATH = Path(__file__).resolve().parents[1] / "data" / "itinerary_activities.json"
_TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "data" / "itinerary_templates.json"


# ─── Loaders ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_activities() -> dict[str, Any]:
    with _ACTIVITIES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("activities") or {}


@lru_cache(maxsize=1)
def _load_templates() -> dict[str, Any]:
    with _TEMPLATES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("templates") or {}


def _locale_short(locale: Optional[str]) -> str:
    return (locale or "tr").split("-")[0].split("_")[0].lower()


def _activity_label(activity_id: str, locale: Optional[str]) -> str:
    activity = _load_activities().get(activity_id)
    if not activity:
        return activity_id
    labels = activity.get("label", {})
    short = _locale_short(locale)
    return labels.get(short) or labels.get("tr") or labels.get("en") or activity_id


# ─── Public types ────────────────────────────────────────────────────


class ItineraryItem(NamedTuple):
    day_offset: int
    date_iso: str
    activity_id: str
    label: str
    location: str
    duration_hours: float


class Itinerary(NamedTuple):
    procedure_id: str
    procedure_name: str
    clinic_id: str
    clinic_name: str
    clinic_city: str
    arrival_date_iso: str
    departure_date_iso: str
    total_days: int
    items: list[ItineraryItem]
    pre_op_requirements: list[str]
    post_op_no_fly_days: int
    post_op_followup_window_days: int


# ─── Engine ──────────────────────────────────────────────────────────


def _category_template(category: str) -> list[dict[str, Any]]:
    """Look up the per-category template; fall back to 'generic' so
    the engine still produces a useful skeleton when a new procedure
    category lands without a custom template."""
    templates = _load_templates()
    return templates.get(category) or templates.get("generic") or []


def _last_day_offset(template: list[dict[str, Any]]) -> int:
    if not template:
        return 0
    return max(item["day_offset"] for item in template)


def generate(
    procedure_id: str,
    clinic_id: str,
    arrival_date: date,
    locale: Optional[str] = None,
) -> Optional[Itinerary]:
    """Build an itinerary or return None if procedure / clinic unknown
    or the clinic doesn't offer the procedure.

    Date arithmetic is naive — we assume travel + activity windows are
    inclusive of weekends. A scheduler that respects clinic working
    days (e.g. Sundays in TR may be closed for elective procedures)
    is a future enhancement; the v0 itinerary is presented as
    'illustrative timeline', not a binding booking calendar.
    """
    procedure = procedure_catalog.get_procedure(procedure_id)
    clinic = clinic_registry.get_clinic(clinic_id)
    if procedure is None or clinic is None:
        return None
    if procedure_id not in clinic.get("procedures_offered", []):
        return None

    template = _category_template(procedure.get("category", "generic"))
    if not template:
        return None

    # Prefer the procedure's own min_stay over the template's last
    # offset; the template might be shorter than the procedure
    # actually needs (some clinics insist on extra recovery nights).
    template_last_day = _last_day_offset(template)
    min_stay = procedure.get("duration_days", {}).get("min_stay", template_last_day + 1)
    total_days = max(template_last_day + 1, min_stay)
    departure_date = arrival_date + timedelta(days=total_days - 1)

    # Sort by (day_offset, activity declaration order) so the same
    # day's activities appear in the order the template lists them.
    sorted_template = sorted(
        enumerate(template), key=lambda kv: (kv[1]["day_offset"], kv[0])
    )

    items: list[ItineraryItem] = []
    activities = _load_activities()
    for _, entry in sorted_template:
        day_offset = entry["day_offset"]
        activity_id = entry["activity_id"]
        activity_meta = activities.get(activity_id, {})
        item_date = arrival_date + timedelta(days=day_offset)
        items.append(
            ItineraryItem(
                day_offset=day_offset,
                date_iso=item_date.isoformat(),
                activity_id=activity_id,
                label=_activity_label(activity_id, locale),
                location=activity_meta.get("location", "clinic"),
                duration_hours=float(activity_meta.get("duration_hours", 0.0)),
            )
        )

    return Itinerary(
        procedure_id=procedure_id,
        procedure_name=procedure_catalog.name(procedure_id, locale),
        clinic_id=clinic_id,
        clinic_name=clinic["name"],
        clinic_city=clinic.get("city", ""),
        arrival_date_iso=arrival_date.isoformat(),
        departure_date_iso=departure_date.isoformat(),
        total_days=total_days,
        items=items,
        pre_op_requirements=list(procedure.get("pre_op_requirements", [])),
        post_op_no_fly_days=int(procedure.get("post_op_no_fly_days", 0)),
        post_op_followup_window_days=int(
            procedure.get("duration_days", {}).get("recovery_total", 0)
        ),
    )
