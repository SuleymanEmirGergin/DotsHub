"""Full deterministic triage orchestrator Ã¢â‚¬â€ connects all pipeline modules.

Pipeline per turn:
  1. Safety guard (EMERGENCY check)
  2. Canonical extraction (text Ã¢â€ â€™ TR canonicals)
  3. Disease candidate generation (canonicals Ã¢â€ â€™ top diseases via Kaggle matrix)
  4. Specialty scoring v2 (text + answer boosts + negatives)
  5. Disease prior Ã¢â€ â€™ specialty
  6. Merge final specialty scores
  7. Discriminative question selection
  8. Stop decision
  9. Confidence calculation (backend-authoritative)
  10. Build RESULT/QUESTION payload + debug patch

All deterministic. Same input Ã¢â€ â€™ same output. No LLM.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.runtime import Runtime
from app.canonical_extract import extract_canonicals_tr
from app.safety_guard import safety_guard_check
from app.emergency_router import evaluate_emergency
from app.confidence import compute_confidence
from app.stop_eval import should_stop
from app.top_conditions_filter import (
    apply_label_overrides,
    apply_top_conditions_gate,
    load_label_overrides,
)

# Confidence gate threshold for RESULT top_conditions — read from
# settings.RESULT_TOP_CONDITIONS_GATE so ops can tune without a code
# change. Default 0.25. See config.py for the full rationale (short
# version: top_conditions_filter's 0.35 default is too strict for live
# traffic; curated entries bypass this gate regardless).
def _result_top_gate() -> float:
    try:
        return float(settings.RESULT_TOP_CONDITIONS_GATE)
    except (AttributeError, TypeError, ValueError):
        return 0.25


# Canonical-injected disease labels (Panik Bozukluk, Majör Depresyon,
# Akut Otitis Media, Bronşiolit, Renal Kolik, Dismenore, PCOS,
# Alerjik Konjonktivit) are tagged as "curated" so the UI can:
#  - badge them differently from raw Kaggle candidates
#  - bypass the low-confidence gate (these were synthesized from a
#    deterministic canonical pattern, not a fragile overlap score)
#  - attach patient-facing prep fields (doktora sorular, self-care, …)
#    from backend/app/data/curated_conditions.json.
#
# Anything not in this set falls through as source_type="kaggle_candidate".
_CURATED_INJECTED_LABELS = frozenset({
    "Panik Bozukluk",
    "Majör Depresyon",
    "Akut Otitis Media",
    "Bronşiolit",
    "Renal Kolik",
    "Dismenore",
    "PCOS (Polikistik Over Sendromu)",
    "Alerjik Konjonktivit",
})


def _annotate_and_enrich_top_conditions(
    top_conditions: List[Dict[str, Any]],
    runtime: Runtime,
) -> List[Dict[str, Any]]:
    """Tag each entry with source_type and enrich curated entries with
    patient-facing metadata from curated_conditions.json.

    Non-mutating: returns a fresh list with fresh dict copies.
    """
    catalog = (runtime.curated_conditions or {}).get("conditions", {}) or {}
    disclaimer = (runtime.curated_conditions or {}).get(
        "disclaimer_tr",
        "Bu liste tanı değildir, yalnızca hazırlık amaçlıdır. Kesin "
        "değerlendirme için lütfen hekiminize başvurun.",
    )
    out: List[Dict[str, Any]] = []
    for c in top_conditions or []:
        if not isinstance(c, dict):
            continue
        label = c.get("disease_label") or ""
        entry = dict(c)
        if label in _CURATED_INJECTED_LABELS:
            entry["source_type"] = "curated"
            meta = catalog.get(label) or {}
            # Copy only the UI-facing fields; keep the envelope lean.
            for key in (
                "icd10",
                "disease_description_tr",
                "doktora_sorulacak_sorular_tr",
                "izlenecek_belirtiler_tr",
                "ne_zaman_tekrar_basvur_tr",
                "self_care_tr",
                "aciliyet_notu_tr",
            ):
                if key in meta and meta[key]:
                    entry[key] = meta[key]
            entry["disclaimer_tr"] = disclaimer
        else:
            entry["source_type"] = "kaggle_candidate"
            # Kaggle entries don't get curated prep fields in this initial
            # release. UI shows the raw disease_description_en (already
            # present via _lookup_disease_description). Disclaimer is still
            # attached so UI can render the same footer regardless of source.
            entry["disclaimer_tr"] = disclaimer
        out.append(entry)
    return out


def _apply_gate_curated_aware(
    top_conditions: List[Dict[str, Any]],
    confidence: Optional[float],
) -> List[Dict[str, Any]]:
    """A9 confidence gate that preserves curated entries.

    Curated labels are injected from deterministic canonical patterns
    and carry known clinical meaning, so the "fragile differential at
    low confidence" concern that motivates the gate doesn't apply to
    them. Kaggle candidates ARE gated: below threshold they're dropped.
    """
    if not top_conditions:
        return top_conditions
    curated = [c for c in top_conditions if c.get("source_type") == "curated"]
    non_curated = [c for c in top_conditions if c.get("source_type") != "curated"]
    gated_non_curated = apply_top_conditions_gate(
        non_curated, confidence, threshold=_result_top_gate()
    )
    # Preserve original ordering: curated first (injections already prepend),
    # then surviving Kaggle candidates.
    return curated + gated_non_curated
from app.scoring_v2 import (
    score_specialties_deterministic_v2,
    compute_specialty_prior,
    merge_final_specialty_scores,
)
from app.question_selector_v3 import select_discriminative_question_v3
from app.explain_specialty import build_why_specialty_tr
from app.risk import compute_risk
from app.core.config import settings

logger = logging.getLogger(__name__)


# Map emergency rule_id → recommended specialty for the EMERGENCY envelope.
# Consumed by the golden-flow suite (scenarios assert both final_type and
# recommended_specialty on EMERGENCY). Prefix match; first hit wins.
# Keep the prefixes aligned with config/emergency_rules.json rule ids.
_EMERGENCY_RULE_TO_SPECIALTY: List[Tuple[str, str, str]] = [
    # (rule_id prefix, specialty_id, specialty_tr)
    ("psychiatric_emergency", "psychiatry", "Psikiyatri"),
    ("suicidal_selfharm", "psychiatry", "Psikiyatri"),
    # safety_guard (rules.json) rule ids — prefixed versions of the
    # config/emergency_rules.json labels. Kept in the same map so ops
    # don't need to think about which source an emergency came from.
    ("self_harm", "psychiatry", "Psikiyatri"),
    ("chest_pain_plus_breathlessness", "cardiology", "Kardiyoloji"),
    ("chest_pain_breathlessness_soft", "cardiology", "Kardiyoloji"),
    ("breathing_severe", "pulmonology", "Göğüs Hastalıkları"),
    ("stroke_redflags", "neurology", "Nöroloji"),
    ("severe_headache_neuro", "neurology", "Nöroloji"),
    ("chest_pain_sob", "cardiology", "Kardiyoloji"),
    ("acute_glaucoma_crisis", "ophthalmology", "Göz Hastalıkları"),
    ("sudden_vision_loss", "ophthalmology", "Göz Hastalıkları"),
    ("infant_fever_under3months", "pediatrics", "Pediatri"),
    ("petechial_rash_child", "pediatrics", "Pediatri"),
    ("febrile_seizure_active", "pediatrics", "Pediatri"),
    ("dka_suspect", "endocrinology", "Endokrinoloji"),
    ("severe_hypoglycemia", "endocrinology", "Endokrinoloji"),
    ("ectopic_pregnancy_suspect", "obgyn", "Kadın Hastalıkları ve Doğum"),
    ("preeclampsia_suspect", "obgyn", "Kadın Hastalıkları ve Doğum"),
    ("postpartum_hemorrhage", "obgyn", "Kadın Hastalıkları ve Doğum"),
    ("acute_appendicitis_suspect", "general_surgery", "Genel Cerrahi"),
    # Truly systemic emergencies — no single specialty, route to ER.
    ("anaphylaxis", "emergency", "Acil Tıp"),
    ("severe_bleeding", "emergency", "Acil Tıp"),
    ("high_fever_with_red_flags", "emergency", "Acil Tıp"),
]


# A2 panic softener (RC #3) ─────────────────────────────────────────────
#
# When a patient describes a panic attack ("kalbim hızlandı, öleceğimi
# sandım, 10 dakikada geçti, birkaç kez oldu"), the extracted canonicals
# overlap heavily with cardiac / anaphylaxis emergency rules (çarpıntı,
# nefes darlığı). Both evaluate_emergency (chest_pain_sob, anaphylaxis)
# and safety_guard_check (breathing_severe in rules.json) fire, routing
# the user to EMERGENCY when the clinically correct output is a
# psychiatry RESULT. We soften those rules only when the panic canonical
# is present AND no hard cardiac/anaphylaxis signal is in the text.
#
# Guarded by "hard signals": sol-kola-vuruyor, çeneye-vuruyor, dil/boğaz
# şişmesi, yaygın döküntü, bayılma — any of these and we do NOT soften
# (a real MI or anaphylaxis can coexist with a panicked patient).
_PANIC_SOFTEN_EMERGENCY_RULES = frozenset({"chest_pain_sob", "anaphylaxis"})
_PANIC_SOFTEN_SAFETY_GUARD_IDS = frozenset({"breathing_severe", "chest_pain", "cardiac_emergency"})
_PANIC_HARD_SIGNALS = (
    "sol kola vuruyor", "çeneye vuruyor", "bayılacak gibi", "bayıldım",
    "dilim şişti", "boğazım şişti", "dudaklarım şişti",
    "yaygın döküntü", "morardım", "moraran",
)


def _has_panic_context(canonicals: List[str], text_norm: str) -> bool:
    """True when the patient message describes a panic attack and no
    hard cardiac/anaphylaxis signal is present (see constants above).
    """
    if "panik atak" not in canonicals:
        return False
    for sig in _PANIC_HARD_SIGNALS:
        if sig in text_norm:
            return False
    return True


# Pediatric bronchiolitis / RSV softener ─────────────────────────────────
#
# When a parent describes an infant with noisy breathing ("hırıltılı nefes")
# plus mild fever, rules.json's anaphylaxis hard_trigger can fire on the
# "nefes" / "hırıltı" keywords even though there's no allergy context. The
# clinically correct output is RESULT/pediatrics with SAME_DAY urgency.
# We soften the anaphylaxis rule only when the bronchiolitis canonical is
# present AND no true anaphylaxis signal (swelling, hives) is in the text.
_BRONCHIOLITIS_SOFTEN_SAFETY_GUARD_IDS = frozenset({"anaphylaxis"})
_ANAPHYLAXIS_HARD_SIGNALS = (
    "dilim şişti", "boğazım şişti", "dudaklarım şişti", "yüzüm şişti",
    "yaygın döküntü", "kurdeşen", "morardı", "morardım",
    "her yerim kaşınıyor", "tüm vücut",
)


def _has_bronchiolitis_context(canonicals: List[str], text_norm: str) -> bool:
    """True when the patient message describes infant noisy breathing and
    no anaphylaxis hard signal is in the text.
    """
    if "bebek nefes hırıltısı" not in canonicals:
        return False
    for sig in _ANAPHYLAXIS_HARD_SIGNALS:
        if sig in text_norm:
            return False
    return True


def _emergency_specialty_for(rule_id: Optional[str]) -> Tuple[str, str]:
    """Return (specialty_id, specialty_tr) for an emergency rule_id.

    Default: ('emergency', 'Acil Tıp'). Keeps the EMERGENCY envelope's
    recommended_specialty populated so downstream consumers (golden-flow
    fixtures, UI, session logs) don't need to special-case nulls.
    """
    if rule_id:
        for prefix, spec_id, spec_tr in _EMERGENCY_RULE_TO_SPECIALTY:
            if rule_id.startswith(prefix):
                return spec_id, spec_tr
    return "emergency", "Acil Tıp"


#Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Disease candidate generator (deterministic, Kaggle-based) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def _generate_candidates(
    user_canonicals_tr: List[str],
    runtime: Runtime,
    top_n: int = 6,
) -> List[Dict[str, Any]]:
    """
    Score each Kaggle disease by overlap with user's TR canonicals.
    Returns top_n candidates sorted by score_0_1 descending.
    """
    user_set: Set[str] = {
        str(c).strip().lower()
        for c in user_canonicals_tr
        if isinstance(c, str) and c.strip()
    }
    if not user_set:
        return []

    canonical_to_en: Dict[str, List[str]] = {}
    if runtime.symptom_severity_en:
        # Preferred path: runtime precomputes this index at startup.
        candidate_index = getattr(runtime, "canonical_to_en_symptoms", None)
        if isinstance(candidate_index, dict):
            canonical_to_en = candidate_index

        # Backward-compat: build once if the runtime does not expose the index.
        if not canonical_to_en:
            rebuilt: Dict[str, List[str]] = {}
            for en, tr in runtime.symptom_map_en_to_tr.items():
                if not isinstance(tr, str):
                    continue
                tr_clean = tr.strip().lower()
                en_clean = str(en).strip().lower()
                if not tr_clean or not en_clean:
                    continue
                rebuilt.setdefault(tr_clean, []).append(en_clean)
            canonical_to_en = {
                canonical: sorted(set(en_list))
                for canonical, en_list in rebuilt.items()
            }
            try:
                runtime.canonical_to_en_symptoms = canonical_to_en
            except Exception:
                pass

    scored: List[Tuple[float, str]] = []

    for disease, tr_syms in runtime.disease_to_trcanonicals.items():
        if not tr_syms:
            continue
        overlap = user_set & tr_syms
        if not overlap:
            continue

        # Base score: Jaccard-like with severity weighting
        raw = len(overlap) / max(1, len(tr_syms))

        # Boost if overlap is large relative to user symptoms
        coverage = len(overlap) / max(1, len(user_set))
        score = (raw * 0.6) + (coverage * 0.4)

        # Optional severity weighting
        if runtime.symptom_severity_en:
            severity_sum = 0
            count = 0
            for tr_c in overlap:
                # Reverse lookup: tr_canonical Ã¢â€ â€™ en_symptom
                en_symptoms = canonical_to_en.get(tr_c, [])
                if not en_symptoms:
                    continue
                # Use max severity per canonical to avoid over-counting duplicates.
                sev = max(runtime.symptom_severity_en.get(en, 3) for en in en_symptoms)
                severity_sum += sev
                count += 1
            if count > 0:
                avg_sev = severity_sum / count
                score *= (1.0 + (avg_sev - 3) * 0.05)  # mild boost for high severity

        scored.append((min(1.0, max(0.0, score)), disease))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"disease_label": dl, "score_0_1": round(s, 4)}
        for s, dl in scored[:top_n]
    ]


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Doctor-ready summary builder Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def _build_doctor_summary(
    user_canonicals_tr: List[str],
    answers: Dict[str, str],
) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for c in user_canonicals_tr:
        c_clean = c.strip().lower()
        if c_clean and c_clean not in seen:
            out.append(f"{c_clean.capitalize()} mevcut.")
            seen.add(c_clean)
    for k, v in sorted(answers.items()):
        vv = "var" if v.lower() == "yes" else "yok" if v.lower() == "no" else v
        out.append(f"{k}: {vv}.")
    return out[:18]


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Safety notes builder Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def _build_safety_notes(top_specialty_id: str) -> List[str]:
    notes = [
        "Bu bir ÃƒÂ¶n deÃ„Å¸erlendirmedir, teÃ…Å¸his deÃ„Å¸ildir.",
        "Ã…Âikayetler artarsa veya yeni belirtiler eklenirse doktora baÃ…Å¸vur.",
    ]
    if top_specialty_id in ("neurology", "cardiology"):
        notes.append(
            "Ani Ã…Å¸iddetli aÃ„Å¸rÃ„Â±, konuÃ…Å¸ma bozukluÃ„Å¸u, tek taraflÃ„Â± gÃƒÂ¼ÃƒÂ§sÃƒÂ¼zlÃƒÂ¼k "
            "gibi durumlarda acile baÃ…Å¸vur."
        )
    return notes


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Main orchestrator Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def _lookup_disease_description(runtime: Runtime, disease_label: str) -> Optional[str]:
    """Return EN disease description when available; fallback to None."""
    descriptions = getattr(runtime, "disease_descriptions_en", {})
    if not isinstance(descriptions, dict):
        return None

    value = descriptions.get(disease_label)
    if isinstance(value, str) and value.strip():
        return value.strip()

    normalized_label = disease_label.strip()
    if normalized_label != disease_label:
        value = descriptions.get(normalized_label)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def run_orchestrator_turn(
    runtime: Runtime,
    input_text: str,
    answers: Dict[str, str],
    asked_canonicals: List[str],
    turn_index: int,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Run one triage turn through the full deterministic pipeline.

    Returns:
        envelope_type: "QUESTION" | "RESULT" | "EMERGENCY" | "ERROR"
        payload: The envelope payload dict
        debug_state_patch: Fields to write back to the session row
    """

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 1) Safety guard Ã¢â‚¬â€ EMERGENCY check
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # Two parallel emergency rule sources are consulted (defense in depth):
    #   (a) runtime.rules_json         — text-only regex/keyword triggers
    #                                    (backend/app/data/rules.json)
    #   (b) runtime.emergency_rules_cfg — richer keyword + canonical rules
    #                                    (config/emergency_rules.json, 19 curated)
    # Either hit → EMERGENCY. Kept separate because they have different schemas
    # and different owners. See docs/TRIAJ_GOLDEN_FLOWS_17_25.md RC #1b.
    # Pre-compute deterministic canonicals once — both the A2 panic
    # softener and (if it runs) evaluate_emergency need them.
    _safety_canonicals = extract_canonicals_tr(
        text_tr=input_text,
        answers=answers,
        synonyms_json=runtime.synonyms,
    )
    from app.canonical_extract import normalize_text_tr as _norm_for_panic
    _text_norm_for_panic = _norm_for_panic(input_text)
    _panic_context = _has_panic_context(_safety_canonicals, _text_norm_for_panic)
    _bronchiolitis_context = _has_bronchiolitis_context(
        _safety_canonicals, _text_norm_for_panic
    )

    emergency = safety_guard_check(input_text, answers, runtime.rules_json)
    if (
        emergency
        and _panic_context
        and emergency.get("rule_id") in _PANIC_SOFTEN_SAFETY_GUARD_IDS
    ):
        logger.info(
            "A2 panic softener: suppressed safety_guard rule_id=%s "
            "because panik atak canonical is present",
            emergency.get("rule_id"),
        )
        emergency = None
    if (
        emergency
        and _bronchiolitis_context
        and emergency.get("rule_id") in _BRONCHIOLITIS_SOFTEN_SAFETY_GUARD_IDS
    ):
        logger.info(
            "Bronchiolitis softener: suppressed safety_guard rule_id=%s "
            "because bebek nefes hırıltısı canonical is present",
            emergency.get("rule_id"),
        )
        emergency = None

    if not emergency and runtime.emergency_rules_cfg:
        _em_match = evaluate_emergency(
            user_text=input_text,
            canonicals_tr=_safety_canonicals,
            rules_cfg=runtime.emergency_rules_cfg,
        )
        if (
            _em_match is not None
            and _panic_context
            and _em_match.rule_id in _PANIC_SOFTEN_EMERGENCY_RULES
        ):
            logger.info(
                "A2 panic softener: suppressed evaluate_emergency rule_id=%s "
                "because panik atak canonical is present",
                _em_match.rule_id,
            )
            _em_match = None
        if _em_match is not None:
            emergency = {
                "rule_id": _em_match.rule_id,
                "reason_tr": _em_match.message_tr or _em_match.title_tr,
                "instructions_tr": [_em_match.recommendation_tr]
                if _em_match.recommendation_tr
                else ["112'yi ara veya en yakın acile başvur."],
            }
    if emergency:
        _rule_id = emergency.get("rule_id")
        _spec_id, _spec_tr = _emergency_specialty_for(_rule_id)
        payload = {
            # "ER_NOW" matches the action value used in rules.json hard_triggers
            # and the golden-flow fixtures. Distinct from the "EMERGENCY"
            # envelope type (which is the outer return value).
            "urgency": "ER_NOW",
            "recommended_specialty": {"id": _spec_id, "name_tr": _spec_tr},
            "reason_tr": emergency.get("reason_tr", "Acil değerlendirme gerekebilir."),
            "instructions_tr": emergency.get(
                "instructions_tr", ["112'yi ara veya en yakın acile başvur."]
            ),
        }
        debug_patch = {
            "user_canonicals_tr": [],
            "top_conditions": [],
            "recommended_specialty_id": _spec_id,
            "recommended_specialty_tr": _spec_tr,
            "confidence_0_1": 1.0,
            "confidence_label_tr": "YÃƒÂ¼ksek",
            "confidence_explain_tr": "Acil uyarÃ„Â± kurallarÃ„Â± tetiklendi.",
            "stop_reason": "EMERGENCY_RULE_TRIGGERED",
            "emergency_rule_id": emergency.get("rule_id"),
            "emergency_reason_tr": payload["reason_tr"],
            "why_specialty_tr": [],
            "specialty_scoring_debug": {},
            "confidence_debug": {},
        }
        return "EMERGENCY", payload, debug_patch

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 2) Canonical extraction
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 2a) Deterministic extraction (always runs — provides fallback)
    nlu_source = "deterministic"
    user_canonicals_tr = extract_canonicals_tr(
        text_tr=input_text,
        answers=answers,
        synonyms_json=runtime.synonyms,
    )

    # 2b) LLM-augmented extraction (feature-flagged + rate-limited)
    if settings.LLM_NLU_ENABLED:
        # Rate-limit check: protect Wiro API quota before making any external call.
        # Uses a global server-side bucket (LLM_NLU_MAX_REQ calls/min, default 30).
        # On limit exceeded, silently fall back to deterministic — no error raised.
        from app.rate_limit import check_llm_nlu_rate_limit

        _rl_allowed, _rl_remaining, _ = check_llm_nlu_rate_limit("global")
        if not _rl_allowed:
            logger.warning(
                "LLM NLU rate limit exceeded (global). Falling back to deterministic."
            )
            nlu_source = "deterministic"
        else:
            try:
                from app.services.llm_nlu import extract_canonicals_llm  # deferred import

                llm_canonicals, llm_source = extract_canonicals_llm(
                    text=input_text,
                    locale="tr-TR",
                    synonyms_json=runtime.synonyms,
                )
                if llm_canonicals:
                    # Union merge: LLM + deterministic → richer signal
                    merged = sorted(set(user_canonicals_tr) | set(llm_canonicals))
                    nlu_source = "hybrid" if user_canonicals_tr else llm_source
                    user_canonicals_tr = merged
                else:
                    # LLM returned empty or failed schema — keep deterministic result
                    nlu_source = llm_source  # e.g. "llm_schema_error"
            except Exception as _llm_exc:
                logger.warning("LLM NLU failed, using deterministic fallback: %s", _llm_exc)
                nlu_source = "deterministic"

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 3) Disease candidate generation
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    candidates = _generate_candidates(user_canonicals_tr, runtime, top_n=6)
    top1 = candidates[0]["score_0_1"] if len(candidates) > 0 else 0.0
    top2 = candidates[1]["score_0_1"] if len(candidates) > 1 else 0.0

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 4) Rules-based specialty scoring v2
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    rules_scoring = score_specialties_deterministic_v2(
        text_tr=input_text,
        answers=answers,
        synonyms_json=runtime.synonyms,
        specialty_keywords_json=runtime.specialty_keywords,
    )
    rules_scores = rules_scoring["scores"]
    ranked = rules_scoring["ranked"]

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 5) Disease prior Ã¢â€ â€™ specialty
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    prior = compute_specialty_prior(
        candidates=candidates,
        disease_to_specialty_list=runtime.disease_to_specialty_list,
    )

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 6) Merge final scores
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    merged = merge_final_specialty_scores(rules_scores, prior)

    # Enrich merged with specialty_tr from ranked
    ranked_lookup = {r["id"]: r["specialty_tr"] for r in ranked}
    for m in merged:
        if "specialty_tr" not in m:
            m["specialty_tr"] = ranked_lookup.get(
                m["id"],
                runtime.specialty_by_id.get(m["id"], {}).get("specialty_tr", m["id"]),
            )

    top_spec = merged[0] if merged else {"id": "internal_gi", "specialty_tr": "Dahiliye", "final_score": 0.0}
    top_spec2 = merged[1] if len(merged) > 1 else {"id": "", "final_score": 0.0}

    specialty_gap = float(top_spec["final_score"]) - float(top_spec2["final_score"])
    top1_spec_score = float(top_spec["final_score"])
    top2_spec_score = float(top_spec2["final_score"])

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 7) Discriminative question selection
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    top_diseases = [c["disease_label"] for c in candidates[:6]]
    q = select_discriminative_question_v3(
        top_diseases=top_diseases,
        disease_to_canonicals_tr=runtime.disease_to_trcanonicals,
        asked_canonicals=asked_canonicals,
        answers=answers,
        question_bank=runtime.question_bank,
        question_effectiveness_map=runtime.question_effectiveness,
    )
    no_question_available = not bool(q.get("question_tr"))

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 8) Stop decision
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    max_q = int(runtime.stop_rules.get("max_questions", 6))
    stop, reason = should_stop(
        turn_index=turn_index,
        max_questions=max_q,
        top_disease_score=top1,
        specialty_gap=specialty_gap,
        no_question_available=no_question_available,
        stop_rules=runtime.stop_rules,
    )

    # Conjunctivitis context injection: ophthalmology + göz kaşıntısı →
    # surface "Alerjik Konjonktivit" as the top condition. Kaggle matrix
    # has no conjunctivitis entry. Seasonal/allergic is the most common
    # pre-triage pattern; caller can differentiate in-clinic.
    if (
        top_spec.get("id") == "ophthalmology"
        and "göz kaşıntısı" in _safety_canonicals
        and not any(
            "Konjonktivit" in (c.get("disease_label") or "")
            or "Konjunktivit" in (c.get("disease_label") or "")
            for c in candidates[:3]
        )
    ):
        candidates = [
            {"disease_label": "Alerjik Konjonktivit", "score_0_1": 0.7}
        ] + candidates[:2]

    # PCOS context injection: obgyn + hirsutism → surface "PCOS". The
    # hirsutism canonical alone is a strong PCOS fingerprint in the
    # pre-triage context (it's rarely standalone without menstrual or
    # metabolic issues, and obgyn routing already filters non-obgyn cases).
    if (
        top_spec.get("id") == "obgyn"
        and "hirsutizm" in _safety_canonicals
        and not any(
            "PCOS" in (c.get("disease_label") or "")
            or "Polikistik" in (c.get("disease_label") or "")
            for c in candidates[:3]
        )
    ):
        candidates = [
            {"disease_label": "PCOS (Polikistik Over Sendromu)", "score_0_1": 0.7}
        ] + candidates[:2]

    # ── Extra Kaggle-label top_condition injections (B1 NLU robustness)
    #
    # These surface the clinically expected label even when the Kaggle
    # disease matrix does not reach it via canonical overlap. Each gate
    # is specialty-first (so we don't cross-contaminate unrelated
    # presentations) + a canonical or text signal. All injections preserve
    # the existing top condition list as tail; they don't force routing
    # the way panic/pediatri overrides do.
    _text_norm_for_inject = _text_norm_for_panic  # cheap, already computed

    def _prepend_if_absent(label: str, score: float, matcher: str) -> None:
        nonlocal candidates
        if not any(matcher in (c.get("disease_label") or "") for c in candidates[:3]):
            candidates = [{"disease_label": label, "score_0_1": score}] + candidates[:2]

    if top_spec.get("id") == "neurology" and "baş ağrısı" in _safety_canonicals and (
        "ışık rahatsız" in _text_norm_for_inject
        or "zonklayıcı" in _text_norm_for_inject
        or "tek taraflı" in _text_norm_for_inject
        or "kusuyorum" in _text_norm_for_inject
        or "mide bulantısı" in _text_norm_for_inject
    ):
        _prepend_if_absent("Migren", 0.6, "Migren")

    if top_spec.get("id") == "endocrinology" and (
        "tip 2 diyabet" in _text_norm_for_inject
        or "tip 2 diyabetliyim" in _text_norm_for_inject
        or "şekerim yükseldi" in _text_norm_for_inject
        or "şekerim yüksek" in _text_norm_for_inject
    ):
        _prepend_if_absent("Tip 2 Diyabet", 0.65, "Diyabet")

    if top_spec.get("id") == "cardiology" and "yüksek tansiyon" in _safety_canonicals:
        _prepend_if_absent("Hipertansiyon", 0.65, "Hipertansiyon")

    # Hypothyroid: classic 4-of-4 combo signal (fatigue + weight gain +
    # dry skin + cold intolerance). Kaggle labels hypothyroidism but TR
    # form is better; surface "Hipotiroidi" explicitly.
    if top_spec.get("id") == "endocrinology" and (
        "halsizlik" in _safety_canonicals
        and (
            "kilo aldım" in _text_norm_for_inject
            or "kilo ald" in _text_norm_for_inject
        )
        and (
            "cildim kuru" in _text_norm_for_inject
            or "saçlarım dökül" in _text_norm_for_inject
            or "üşüyorum" in _text_norm_for_inject
        )
    ):
        _prepend_if_absent("Hipotiroidi", 0.6, "Hipotiroidi")

    # Hemorrhoids: anal pain + bleeding signal. Kaggle has
    # "Dimorphic hemmorhoids(piles)" which we already override to
    # "Hemoroid" — so the injection is only a safety net when scoring
    # doesn't reach the disease matrix at all.
    if top_spec.get("id") == "internal_gi" and "anal ağrı" in _safety_canonicals and (
        "kanama" in _text_norm_for_inject
        or "kanıyor" in _text_norm_for_inject
    ):
        _prepend_if_absent("Hemoroid", 0.6, "Hemoroid")

    # Dysmenorrhea context injection: obgyn + dismenore canonical →
    # surface "Dismenore" as the top condition. Kaggle matrix has no
    # dysmenorrhea entry.
    if (
        top_spec.get("id") == "obgyn"
        and "dismenore" in _safety_canonicals
        and not any(
            "Dismenore" in (c.get("disease_label") or "")
            for c in candidates[:3]
        )
    ):
        candidates = [
            {"disease_label": "Dismenore", "score_0_1": 0.7}
        ] + candidates[:2]

    # Renal colic context injection: nephrology + flank-pain canonical +
    # hematuria → surface "Renal Kolik" as the top condition. Kaggle
    # matrix maps flank pain to generic urinary conditions, which aren't
    # the specific label the clinic expects.
    if (
        top_spec.get("id") == "nephrology"
        and "yan ağrısı" in _safety_canonicals
        and not any(
            "Renal Kolik" in (c.get("disease_label") or "")
            or "Böbrek Taşı" in (c.get("disease_label") or "")
            for c in candidates[:3]
        )
    ):
        candidates = [
            {"disease_label": "Renal Kolik", "score_0_1": 0.7}
        ] + candidates[:2]

    # Pediatric context overrides — force pediatrics routing + RESULT.
    #
    # Why override top_spec + stop (and not just prepend a candidate):
    # deterministic NLU usually extracts a single strong canonical
    # (bebek nefes hırıltısı / kulak çekiştirme) and pediatrics ranks
    # top naturally. But LLM NLU returns a richer canonical set (adds
    # ateş, iştah kaybı, bebek huzursuzluğu) which shifts the scoring
    # ranking AND makes should_stop return False — the run falls
    # through to QUESTION even though the clinical route is clear.
    # Forcing top_spec + stop makes routing stable across DET and LLM
    # modes. Deterministic already stops; this is a no-op for it.
    _pedi_specialty = runtime.specialty_by_id.get("pediatrics") or {}

    if "bebek nefes hırıltısı" in _safety_canonicals:
        top_spec = {
            "id": "pediatrics",
            "specialty_tr": _pedi_specialty.get("specialty_tr", "Pediatri"),
        }
        stop = True
        reason = "PEDI_BRONCHIOLITIS_OVERRIDE"
        if not any(
            "Bronşiolit" in (c.get("disease_label") or "")
            for c in candidates[:3]
        ):
            candidates = [
                {"disease_label": "Bronşiolit", "score_0_1": 0.7}
            ] + candidates[:2]
        logger.info("Bronchiolitis override: forced pediatrics RESULT")
    elif "kulak çekiştirme" in _safety_canonicals:
        top_spec = {
            "id": "pediatrics",
            "specialty_tr": _pedi_specialty.get("specialty_tr", "Pediatri"),
        }
        stop = True
        reason = "PEDI_OTITIS_OVERRIDE"
        if not any(
            "Otitis" in (c.get("disease_label") or "")
            or "Otit" in (c.get("disease_label") or "")
            for c in candidates[:3]
        ):
            candidates = [
                {"disease_label": "Akut Otitis Media", "score_0_1": 0.7}
            ] + candidates[:2]
        logger.info("Otitis media override: forced pediatrics RESULT")

    # Depression context injection: when psychiatry is the top specialty
    # and the patient described low mood ("düşük ruh hali"), ensure the
    # top_conditions list contains "Majör Depresyon" — the Kaggle disease
    # matrix has no depression entry, so without this injection the RESULT
    # envelope lacks the clinically expected condition label.
    if (
        top_spec.get("id") == "psychiatry"
        and "düşük ruh hali" in _safety_canonicals
        and not any(
            "Depresyon" in (c.get("disease_label") or "")
            for c in candidates[:3]
        )
    ):
        candidates = [
            {"disease_label": "Majör Depresyon", "score_0_1": 0.6}
        ] + candidates[:2]

    # A2 panic softener override: when the panic context was confirmed
    # earlier (panic canonical present, no hard cardio/anaphylaxis
    # signals), short-circuit the question loop and force a psychiatry
    # RESULT with "Panik Bozukluk" as the top condition. This matches
    # the clinical expectation encoded in the panic golden-flow fixtures
    # and prevents downgrading to QUESTION on a single-turn input.
    if _panic_context:
        stop = True
        reason = "PANIC_CONTEXT_OVERRIDE"
        psych_entry = runtime.specialty_by_id.get("psychiatry") or {}
        top_spec = {
            "id": "psychiatry",
            "specialty_tr": psych_entry.get("specialty_tr", "Psikiyatri"),
        }
        # Ensure the panic disorder label is present in top_conditions AND
        # drop cardiology/respiratory differentials that would otherwise
        # surface as "Akut koroner sendrom şüphesi" / "Astım" alongside
        # Panik Bozukluk — clinically misleading in a panic-context RESULT.
        _CARDIO_RESP_EXCLUDE = (
            "Heart attack",
            "Akut koroner",
            "Astım",
            "Pneumonia",
            "Zatürre",
        )
        def _is_cardio_resp(label: str) -> bool:
            return any(kw in (label or "") for kw in _CARDIO_RESP_EXCLUDE)

        _filtered = [c for c in candidates if not _is_cardio_resp(c.get("disease_label") or "")]
        if not any(
            "Panik" in (c.get("disease_label") or "")
            for c in _filtered[:3]
        ):
            _filtered = [
                {"disease_label": "Panik Bozukluk", "score_0_1": 0.75}
            ] + _filtered[:2]
        candidates = _filtered
        logger.info("A2 panic softener: forced psychiatry RESULT for panic context")

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 9) Confidence (backend-authoritative)
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    conf, conf_label, conf_explain, conf_debug = compute_confidence(
        top1_disease=top1,
        top2_disease=top2,
        top1_spec=top1_spec_score,
        top2_spec=top2_spec_score,
        asked_count=len(asked_canonicals),
    )
    risk = compute_risk(
        extracted_canonicals=user_canonicals_tr,
        confidence_0_1=conf,
        same_day=None,
        duration_days=None,
        profile=None,
        risk_rules=runtime.risk_rules_cfg or {},
    )

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # 10) Build debug patch (written to session row)
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    debug_patch: Dict[str, Any] = {
        "user_canonicals_tr": user_canonicals_tr,
        "top_conditions": candidates[:3],
        "recommended_specialty_id": top_spec["id"],
        "recommended_specialty_tr": top_spec.get("specialty_tr", top_spec["id"]),
        "confidence_0_1": round(conf, 4),
        "confidence_label_tr": conf_label,
        "confidence_explain_tr": conf_explain,
        "stop_reason": reason,
        "specialty_scoring_debug": rules_scoring["debug"],
        "confidence_debug": conf_debug,
        "question_selector_debug": q.get("selector_debug") or {},
        "emergency_rule_id": None,
        "emergency_reason_tr": None,
    }

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # RESULT path
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    if stop or no_question_available:
        why = build_why_specialty_tr(
            top_specialty_id=top_spec["id"],
            specialty_name_tr=top_spec.get("specialty_tr", top_spec["id"]),
            scoring_debug=rules_scoring["debug"],
            disease_candidates=candidates,
            disease_to_specialty_map=runtime.disease_to_specialty_map,
        )

        # _meta for event logging (turn-level metrics)
        _meta = {
            "turn_index": turn_index,
            "confidence_0_1": round(conf, 4),
            "top1_spec": round(top1_spec_score, 4),
            "top2_spec": round(top2_spec_score, 4),
            "specialty_gap": round(specialty_gap, 4),
            "nlu_source": nlu_source,
        }

        # Apply disease_label overrides (Kaggle EN → curated TR labels).
        # The A9 confidence gate is intentionally NOT applied here: current
        # golden-flow fixtures assert top_condition_contains on low-confidence
        # scenarios (0.09-0.20 range), where the gate would empty the list.
        # Gate can be reintroduced as a separate follow-up once the disease
        # matrix / confidence calibration is tuned.
        _raw_top = [
            dict(
                {
                    "disease_label": c["disease_label"],
                    "score_0_1": round(float(c["score_0_1"]), 2),
                },
                **(
                    {"disease_description": description}
                    if description
                    else {}
                ),
            )
            for c in candidates[:3]
            for description in [_lookup_disease_description(runtime, c["disease_label"])]
        ]
        _overridden_top = apply_label_overrides(_raw_top, load_label_overrides())
        # Annotate each entry with source_type + enrich curated entries with
        # patient-facing prep fields; then apply the A9 confidence gate in
        # a curated-aware way (curated entries survive below threshold).
        _annotated_top = _annotate_and_enrich_top_conditions(_overridden_top, runtime)
        _filtered_top = _apply_gate_curated_aware(_annotated_top, conf)

        # Urgency tagging for non-emergency RESULT envelopes. Default is
        # ROUTINE; certain canonical contexts elevate to WITHIN_3_DAYS or
        # SAME_DAY (no hard stop but should be seen promptly). Ordered:
        # SAME_DAY wins over WITHIN_3_DAYS wins over ROUTINE.
        _result_urgency = "ROUTINE"
        if "bebek nefes hırıltısı" in _safety_canonicals:
            _result_urgency = "SAME_DAY"
        elif "yan ağrısı" in _safety_canonicals and top_spec.get("id") == "nephrology":
            _result_urgency = "SAME_DAY"
        elif "kulak çekiştirme" in _safety_canonicals:
            _result_urgency = "WITHIN_3_DAYS"

        payload = {
            "urgency": _result_urgency,
            "recommended_specialty": {
                "id": top_spec["id"],
                "name_tr": top_spec.get("specialty_tr", top_spec["id"]),
            },
            "top_conditions": _filtered_top,
            "confidence_0_1": round(conf, 3),
            "confidence_label_tr": conf_label,
            "confidence_explain_tr": conf_explain,
            "risk": risk,
            "stop_reason": reason,
            "why_specialty_tr": why,
            "doctor_ready_summary_tr": _build_doctor_summary(
                user_canonicals_tr, answers
            ),
            "safety_notes_tr": _build_safety_notes(top_spec["id"]),
            "_meta": _meta,
        }

        debug_patch["why_specialty_tr"] = why
        return "RESULT", payload, debug_patch

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # QUESTION path
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _meta = {
        "turn_index": turn_index,
        "confidence_0_1": round(conf, 4),
        "top1_spec": round(top1_spec_score, 4),
        "top2_spec": round(top2_spec_score, 4),
        "specialty_gap": round(specialty_gap, 4),
        "nlu_source": nlu_source,
    }

    payload = {
        "question_id": q.get("question_id", "q_auto"),
        "canonical": q.get("canonical"),
        "question_tr": q.get("question_tr"),
        "answer_type": q.get("answer_type", "yes_no"),
        "choices_tr": q.get("choices_tr"),
        "why_asking_tr": q.get("why_asking_tr"),
        "_meta": _meta,
    }
    debug_patch["why_specialty_tr"] = []
    return "QUESTION", payload, debug_patch
