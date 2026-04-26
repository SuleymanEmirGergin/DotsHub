"""Quote engine — score and rank clinics for a procedure + patient profile.

Single public entry point: ``rank_clinics(procedure_id, profile, locale,
target_city, top_n)`` returns ``ClinicQuoteItem`` instances ordered
best-first.

Scoring weights (sum to 1.0)
    0.35 — language match (clinic offers patient's locale natively)
    0.25 — certifications (JCI / IFSO / ESHRE / ESC etc.)
    0.20 — clinic experience (years_experience + before_after_count)
    0.10 — average_rating_5
    0.10 — city match (target_city == clinic.city, if specified)

The weights are deliberately interpretable, not learned. Every
ranking decision must be explainable to a reviewer; ``why_recommended_tr``
on each result encodes that explanation in the user's language.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.models.schemas import ClinicQuoteItem
from app.services import clinic_registry, procedure_catalog

logger = logging.getLogger(__name__)


# ─── Score helpers ───────────────────────────────────────────────────


def _score_language(clinic: dict, locale: str | None) -> float:
    """1.0 if the clinic offers the patient's locale directly, 0.0 if not.

    Why binary, not graded: language match is a hard quality
    signal — a partner you can't talk to is fundamentally lower
    quality. "Has someone who speaks broken English" doesn't deserve
    a partial score in this layer; cluster the borderline cases at
    the clinic-detail page, not in initial ranking.
    """
    short = (locale or "tr").split("-")[0].split("_")[0].lower()
    return 1.0 if short in clinic.get("languages", []) else 0.0


def _score_certifications(clinic: dict) -> float:
    """Cap at 4 weighted credentials = 1.0. JCI is the gold standard
    for international patients, so it weighs double. Others contribute
    one unit each, capped at 4 total."""
    certs = set(clinic.get("certifications", []))
    score = 0.0
    if "JCI" in certs:
        score += 2.0
    score += sum(1.0 for c in certs if c not in {"JCI"})
    return min(score / 4.0, 1.0)


def _score_experience(clinic: dict) -> float:
    """Combine years_experience (cap 20) with before_after_count
    (cap 1000). 50/50 split."""
    years = min(clinic.get("years_experience", 0), 20) / 20.0
    before_after = min(clinic.get("before_after_count", 0), 1000) / 1000.0
    return 0.5 * years + 0.5 * before_after


def _score_rating(clinic: dict) -> float:
    """Linear 0-5 → 0.0-1.0 mapping, with anything below 3.5
    contributing 0 (signal floor)."""
    rating = clinic.get("average_rating_5", 0.0)
    if rating < 3.5:
        return 0.0
    return min((rating - 3.5) / 1.5, 1.0)


def _score_city(clinic: dict, target_city: Optional[str]) -> float:
    if not target_city:
        return 0.5  # neutral when caller didn't express a preference
    return 1.0 if target_city.strip().lower() == clinic.get("city", "").lower() else 0.0


# ─── Pricing helpers ─────────────────────────────────────────────────


def _quoted_price_eur(clinic: dict, procedure: dict) -> int:
    """Apply clinic.price_modifier to the procedure mid band. We use
    'mid' as the public quote because it's the most common transaction
    band; the full band is also surfaced on the response for ranges."""
    base = procedure.get("price_band_eur", {}).get("mid")
    if base is None:
        return 0
    modifier = clinic.get("price_modifier", 1.0)
    return int(round(base * modifier))


def _quoted_band_eur(clinic: dict, procedure: dict) -> dict:
    band = procedure.get("price_band_eur", {})
    modifier = clinic.get("price_modifier", 1.0)
    return {
        k: int(round(v * modifier))
        for k, v in band.items()
        if isinstance(v, (int, float))
    }


# ─── Why-recommended copy ────────────────────────────────────────────


def _explain_match(
    clinic: dict, breakdown: dict[str, float], locale: str | None
) -> List[str]:
    """Human-readable bullets explaining why this clinic ranked.

    We surface the top 2-3 contributing scores; below 0.3 they're
    dropped because flagging weak signals as 'reasons' would dilute
    the explanation. Locale = TR for now; EN/DE/RU/AR can be added
    when a client surface needs them — keeping copy in code (not a
    JSON catalog) until then to keep the change footprint small.
    """
    out: list[str] = []
    if breakdown["language"] > 0.5:
        out.append(f"{clinic['name']} dilinizi destekliyor.")
    if breakdown["certifications"] > 0.5:
        certs = ", ".join(clinic.get("certifications", [])[:3])
        out.append(f"Sertifikalar: {certs}.")
    if breakdown["experience"] > 0.5:
        years = clinic.get("years_experience", 0)
        count = clinic.get("before_after_count", 0)
        out.append(f"{years} yıl deneyim, {count}+ vaka portföyü.")
    if breakdown["rating"] > 0.5:
        rating = clinic.get("average_rating_5", 0.0)
        out.append(f"Hasta puanı {rating}/5.")
    if breakdown["city"] > 0.5 and locale != "no_target":
        out.append(f"Tercih ettiğiniz şehir: {clinic.get('city', '')}.")
    return out


# ─── Public API ──────────────────────────────────────────────────────


def rank_clinics(
    procedure_id: str,
    locale: str | None,
    target_city: Optional[str] = None,
    top_n: int = 5,
) -> List[ClinicQuoteItem]:
    """Return up to ``top_n`` clinics ranked best-first for a procedure.

    Empty list when the procedure exists but no partner clinic offers
    it; the route handler should turn that into an informative ERROR
    envelope, not a silent 200 with zero clinics.
    """
    procedure = procedure_catalog.get_procedure(procedure_id)
    if procedure is None:
        return []
    candidates = clinic_registry.clinics_for_procedure(procedure_id)
    if not candidates:
        return []

    weights = {
        "language": 0.35,
        "certifications": 0.25,
        "experience": 0.20,
        "rating": 0.10,
        "city": 0.10,
    }
    scored: list[tuple[float, dict[str, float], dict]] = []
    for clinic in candidates:
        breakdown = {
            "language": _score_language(clinic, locale),
            "certifications": _score_certifications(clinic),
            "experience": _score_experience(clinic),
            "rating": _score_rating(clinic),
            "city": _score_city(clinic, target_city),
        }
        total = sum(weights[k] * v for k, v in breakdown.items())
        scored.append((total, breakdown, clinic))

    # Sort descending by score; tie-break by alphabetical clinic id
    # so the order is deterministic (tests rely on this).
    scored.sort(key=lambda t: (-t[0], t[2].get("id", "")))

    out: list[ClinicQuoteItem] = []
    for total, breakdown, clinic in scored[:top_n]:
        out.append(
            ClinicQuoteItem(
                clinic_id=clinic["id"],
                clinic_name=clinic["name"],
                city=clinic.get("city", ""),
                score_0_1=round(total, 3),
                price_eur=_quoted_price_eur(clinic, procedure),
                price_band_eur=_quoted_band_eur(clinic, procedure),
                package_features=list(clinic.get("package_features", [])),
                languages=list(clinic.get("languages", [])),
                certifications=list(clinic.get("certifications", [])),
                consult_response_hours=clinic.get("consult_response_hours", 24),
                average_rating_5=clinic.get("average_rating_5", 0.0),
                map_url=clinic_registry.maps_url(clinic),
                why_recommended_tr=_explain_match(
                    clinic, breakdown, locale if target_city else "no_target"
                ),
            )
        )
    return out
