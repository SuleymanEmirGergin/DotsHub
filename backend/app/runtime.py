"""Runtime config & cache loader — loaded once at startup, shared across requests.

Adapts the actual data file formats in app/data/ to a clean Runtime object.
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config directory resolution
# ---------------------------------------------------------------------------
#
# Safety-critical config lives in <repo_root>/config/  (emergency_rules.json,
# risk_rules.json, stop_rules.json, etc.). We must NOT resolve that path via
# os.getcwd(), because CI and the regression runner cd into backend/ before
# invoking tests — which would silently miss the file and load 0 emergency
# rules. Instead, resolve from __file__ so the path is invariant under cwd.
#
# Override order (first match wins):
#   1. PRETRIAGE_CONFIG_DIR env var (explicit override for deploys)
#   2. <repo_root>/config/    (derived from __file__: backend/app/runtime.py → ../../..)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/app/runtime.py → repo root


def _resolve_config_dir() -> Path:
    override = os.environ.get("PRETRIAGE_CONFIG_DIR", "").strip()
    if override:
        return Path(override).resolve()
    return _REPO_ROOT / "config"


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Runtime:
    # Kaggle disease → EN symptom list
    disease_symptom_matrix: Dict[str, List[str]]
    # EN symptom → severity int (optional)
    symptom_severity_en: Optional[Dict[str, int]]
    # EN symptom → TR canonical  (kaggle_to_canonical.json)
    symptom_map_en_to_tr: Dict[str, Optional[str]]
    # disease_label → [{specialty_id, specialty_tr, confidence}]
    disease_to_specialty_list: List[Dict[str, Any]]
    # specialty_keywords_tr.json  (array format)
    specialty_keywords: Dict[str, Any]
    # stop_rules.json
    stop_rules: Dict[str, Any]
    # symptom_question_bank_tr.json
    question_bank: Dict[str, Any]
    # synonyms_tr.json  (array format)
    synonyms: Dict[str, Any]
    # rules.json (emergency red flags etc.)
    rules_json: Dict[str, Any]
    # disease_label -> EN description (kaggle_cache/disease_descriptions.json)
    disease_descriptions_en: Dict[str, str] = field(default_factory=dict)
    # ─── Derived at load time ───
    # disease → set of TR canonicals
    disease_to_trcanonicals: Dict[str, Set[str]] = field(default_factory=dict)
    canonical_to_en_symptoms: Dict[str, List[str]] = field(default_factory=dict)
    # disease_label → {specialty_id, specialty_tr, confidence}  (lookup dict)
    disease_to_specialty_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # canonical_symptom → question dict  (lookup for question selector)
    questions_by_canonical: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Synonym lookup: normalized phrase → canonical
    synonym_lookup: Dict[str, str] = field(default_factory=dict)
    # Specialty lookup by id
    specialty_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Question effectiveness map: canonical -> effectiveness row
    question_effectiveness: Dict[str, Any] = field(default_factory=dict)
    # Emergency rules configuration
    emergency_rules_cfg: Dict[str, Any] = field(default_factory=dict)
    # Risk stratification rules (config/risk_rules.json)
    risk_rules_cfg: Dict[str, Any] = field(default_factory=dict)
    # Curated "possible conditions" catalog (app/data/curated_conditions.json).
    # Keyed by canonical TR disease label; each entry has icd10, description,
    # patient-facing prep fields (questions, symptoms to monitor, escalation
    # triggers, self-care) and a disclaimer. Used by triage_engine to enrich
    # top_conditions entries that were context-injected (source_type="curated").
    curated_conditions: Dict[str, Any] = field(default_factory=dict)
    # Kaggle-derived disease-label meta (app/data/kaggle_condition_meta.json).
    # Lighter than curated_conditions: icd10 + one-paragraph description + one
    # "ipucu" hint. Keyed by the TR *override target* label (so it joins after
    # apply_label_overrides). Enriches source_type="kaggle_candidate" entries.
    kaggle_condition_meta: Dict[str, Any] = field(default_factory=dict)


def _build_disease_to_trcanonicals(
    matrix: Dict[str, List[str]],
    en_to_tr: Dict[str, Optional[str]],
) -> Dict[str, Set[str]]:
    """Map each disease to the set of TR canonical symptoms it involves."""
    out: Dict[str, Set[str]] = {}
    for disease, en_list in matrix.items():
        s: Set[str] = set()
        for en in en_list:
            tr = en_to_tr.get(str(en).strip().lower())
            if isinstance(tr, str):
                tr_clean = tr.strip().lower()
                if tr_clean:
                    s.add(tr_clean)
        if s:
            out[disease] = s
    return out


def _build_canonical_to_en_symptoms(
    en_to_tr: Dict[str, Optional[str]],
) -> Dict[str, List[str]]:
    """Build reverse lookup: canonical -> sorted EN symptoms."""
    grouped: Dict[str, Set[str]] = {}
    for en, tr in en_to_tr.items():
        if not isinstance(tr, str):
            continue
        canonical = tr.strip().lower()
        if not canonical:
            continue
        en_clean = str(en).strip().lower()
        if not en_clean:
            continue
        grouped.setdefault(canonical, set()).add(en_clean)
    return {
        canonical: sorted(en_list)
        for canonical, en_list in grouped.items()
    }


def _build_disease_to_specialty_map(
    spec_list: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """disease_label → first matching specialty entry."""
    out: Dict[str, Dict[str, Any]] = {}
    for entry in spec_list:
        dl = entry.get("disease_label", "")
        if dl and dl not in out:
            out[dl] = entry
    return out


def _build_questions_by_canonical(
    bank: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """canonical_symptom → question dict."""
    out: Dict[str, Dict[str, Any]] = {}
    for q in bank.get("questions", []):
        c = q.get("canonical_symptom", "").strip().lower()
        if c:
            out[c] = q
    return out


def _build_synonym_lookup(synonyms_json: Dict[str, Any]) -> Dict[str, str]:
    """normalized variant → canonical (phrase-first lookup)."""
    out: Dict[str, str] = {}
    for entry in synonyms_json.get("synonyms", []):
        canonical = entry.get("canonical", "").strip().lower()
        if not canonical:
            continue
        for v in entry.get("variants_tr", []):
            vn = v.strip().lower()
            if vn:
                out[vn] = canonical
        # canonical itself maps to itself
        out[canonical] = canonical
    return out


def _build_specialty_by_id(spec_json: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """specialty id → full spec entry."""
    out: Dict[str, Dict[str, Any]] = {}
    for entry in spec_json.get("specialties", []):
        sid = entry.get("id", "")
        if sid:
            out[sid] = entry
    return out


def load_runtime(data_dir: str = "app/data", tenant_id: str = "default") -> Runtime:
    """Load the Runtime for a given tenant (multi-tenant C1).

    The only tenant-scoped asset today is the curated_conditions
    catalog. Lookup order for the catalog:
      1. <data_dir>/curated_conditions.<tenant_id>.json  (tenant-specific)
      2. <data_dir>/curated_conditions.json              (default fallback)

    All other data files stay shared across tenants (emergency rules,
    disease matrix, synonyms, etc.). If the tenant file is missing
    the loader transparently falls back to the default — so partial
    tenant customization is supported: a hospital can override just
    a few labels while inheriting the rest.
    """
    """Load all config/cache files and build derived lookup structures."""
    d = Path(data_dir)

    disease_symptom_matrix = load_json(str(d / "kaggle_cache" / "disease_symptoms.json"))
    symptom_severity_en: Optional[Dict[str, int]] = None
    try:
        symptom_severity_en = load_json(str(d / "kaggle_cache" / "symptom_severity.json"))
    except Exception:
        pass

    symptom_map_en_to_tr = load_json(str(d / "kaggle_cache" / "kaggle_to_canonical.json"))
    disease_descriptions_en: Dict[str, str] = {}
    try:
        descriptions_raw = load_json(str(d / "kaggle_cache" / "disease_descriptions.json"))
        if isinstance(descriptions_raw, dict):
            disease_descriptions_en = {
                str(k): str(v).strip()
                for k, v in descriptions_raw.items()
                if isinstance(v, str) and v.strip()
            }
    except Exception:
        pass

    disease_to_specialty_raw = load_json(str(d / "disease_to_specialty.json"))
    disease_to_specialty_list: List[Dict[str, Any]] = disease_to_specialty_raw.get("map", [])

    specialty_keywords = load_json(str(d / "specialty_keywords_tr.json"))
    stop_rules = load_json(str(d / "stop_rules.json"))
    question_bank = load_json(str(d / "symptom_question_bank_tr.json"))
    synonyms = load_json(str(d / "synonyms_tr.json"))
    rules_json = load_json(str(d / "rules.json"))

    rt = Runtime(
        disease_symptom_matrix=disease_symptom_matrix,
        symptom_severity_en=symptom_severity_en,
        symptom_map_en_to_tr=symptom_map_en_to_tr,
        disease_descriptions_en=disease_descriptions_en,
        disease_to_specialty_list=disease_to_specialty_list,
        specialty_keywords=specialty_keywords,
        stop_rules=stop_rules,
        question_bank=question_bank,
        synonyms=synonyms,
        rules_json=rules_json,
    )

    # Derived structures
    rt.disease_to_trcanonicals = _build_disease_to_trcanonicals(
        disease_symptom_matrix, symptom_map_en_to_tr
    )
    rt.canonical_to_en_symptoms = _build_canonical_to_en_symptoms(
        symptom_map_en_to_tr
    )
    rt.disease_to_specialty_map = _build_disease_to_specialty_map(disease_to_specialty_list)
    rt.questions_by_canonical = _build_questions_by_canonical(question_bank)
    rt.synonym_lookup = _build_synonym_lookup(synonyms)
    rt.specialty_by_id = _build_specialty_by_id(specialty_keywords)

    # Load question effectiveness data (optional, for v3 selector)
    qe_map: Dict[str, Any] = {}
    try:
        cache_dir = d.parent / "data_cache"
        qe_path = cache_dir / "question_effectiveness_latest.json"
        if qe_path.exists():
            qe_data = load_json(str(qe_path))
            for row in qe_data.get("question_effectiveness", []):
                c = str(row.get("canonical", "")).strip().lower()
                if c:
                    qe_map[c] = row
    except Exception:
        pass  # Gracefully fallback to empty map
    rt.question_effectiveness = qe_map

    # Load emergency & risk rules from the cwd-independent config directory.
    # A missing/empty emergency_rules.json is a production risk (every emergency
    # rule becomes dead code), so we log loudly — never silent-swallow.
    config_dir = _resolve_config_dir()
    emergency_cfg: Dict[str, Any] = {}
    risk_cfg: Dict[str, Any] = {}

    emerg_path = config_dir / "emergency_rules.json"
    if emerg_path.exists():
        try:
            emergency_cfg = load_json(str(emerg_path))
            n_rules = len(emergency_cfg.get("rules", []) or [])
            if n_rules == 0:
                logger.warning(
                    "emergency_rules.json loaded but contains 0 rules "
                    "(path=%s) — every emergency rule will be dead.",
                    emerg_path,
                )
            else:
                logger.info(
                    "Loaded %d emergency rules from %s", n_rules, emerg_path
                )
        except Exception as exc:  # noqa: BLE001 — log and continue, do NOT silence
            logger.error(
                "Failed to parse emergency_rules.json at %s: %s",
                emerg_path,
                exc,
            )
    else:
        logger.warning(
            "emergency_rules.json not found at %s — emergency routing will "
            "fall back to stop_rules.json only. Check PRETRIAGE_CONFIG_DIR "
            "or repo layout.",
            emerg_path,
        )

    risk_path = config_dir / "risk_rules.json"
    if risk_path.exists():
        try:
            risk_cfg = load_json(str(risk_path))
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to parse risk_rules.json at %s: %s", risk_path, exc
            )
    else:
        logger.warning(
            "risk_rules.json not found at %s — risk stratification will use "
            "defaults.",
            risk_path,
        )

    rt.emergency_rules_cfg = emergency_cfg
    rt.risk_rules_cfg = risk_cfg

    # Curated "possible conditions" catalog — tenant-aware (C1).
    # Lookup order:
    #   1) curated_conditions.<tenant_id>.json   (tenant-specific override)
    #   2) curated_conditions.json               (default fallback)
    # A missing tenant file transparently falls back to default — so a
    # hospital can ship a partial override without re-authoring the full
    # catalog. Logger makes the chosen path visible at startup.
    curated_conditions: Dict[str, Any] = {}
    curated_load_source: Optional[str] = None
    try:
        tenant_specific = d / f"curated_conditions.{tenant_id}.json"
        default_path = d / "curated_conditions.json"
        chosen_path = tenant_specific if tenant_specific.exists() else default_path
        if chosen_path.exists():
            raw_curated = load_json(str(chosen_path))
            if isinstance(raw_curated, dict):
                curated_conditions = raw_curated
                curated_load_source = str(chosen_path.name)
    except Exception as exc:
        logger.warning(
            "Failed to load curated_conditions for tenant=%r at %s: %s",
            tenant_id,
            d,
            exc,
        )
    if curated_load_source:
        logger.info(
            "Loaded curated_conditions (tenant=%r) from %s — %d condition labels",
            tenant_id,
            curated_load_source,
            len((curated_conditions or {}).get("conditions", {})),
        )
    rt.curated_conditions = curated_conditions

    # Kaggle-candidate meta (B3). Loaded from app/data/kaggle_condition_meta.json.
    # Missing file is non-fatal — kaggle_candidate entries simply render
    # without ICD-10 / description, matching pre-B3 behaviour.
    kaggle_meta: Dict[str, Any] = {}
    try:
        kaggle_meta_path = d / "kaggle_condition_meta.json"
        if kaggle_meta_path.exists():
            raw_kaggle = load_json(str(kaggle_meta_path))
            if isinstance(raw_kaggle, dict):
                kaggle_meta = raw_kaggle
    except Exception as exc:
        logger.warning(
            "Failed to load kaggle_condition_meta.json at %s: %s",
            d / "kaggle_condition_meta.json",
            exc,
        )
    rt.kaggle_condition_meta = kaggle_meta

    return rt
