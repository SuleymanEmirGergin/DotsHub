"""Runtime config & cache loader — loaded once at startup, shared across requests.

Adapts the actual data file formats in app/data/ to a clean Runtime object.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


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


def load_runtime(data_dir: str = "app/data") -> Runtime:
    """Load all config/cache files and build derived lookup structures."""
    d = Path(data_dir)

    disease_symptom_matrix = load_json(str(d / "kaggle_cache" / "disease_symptoms.json"))
    symptom_severity_en: Optional[Dict[str, int]] = None
    try:
        symptom_severity_en = load_json(str(d / "kaggle_cache" / "symptom_severity.json"))
    except Exception:
        pass

    symptom_map_en_to_tr = load_json(str(d / "kaggle_cache" / "kaggle_to_canonical.json"))
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

    # Load emergency rules
    emergency_cfg: Dict[str, Any] = {}
    risk_cfg: Dict[str, Any] = {}
    try:
        config_dir = Path("config")
        emerg_path = config_dir / "emergency_rules.json"
        if emerg_path.exists():
            emergency_cfg = load_json(str(emerg_path))
        risk_path = config_dir / "risk_rules.json"
        if risk_path.exists():
            risk_cfg = load_json(str(risk_path))
    except Exception:
        pass  # Gracefully fallback to empty config
    rt.emergency_rules_cfg = emergency_cfg
    rt.risk_rules_cfg = risk_cfg

    return rt
