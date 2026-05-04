"""Build canonical TR text corpus per disease for embedding retrieval.

Combines:
  - kaggle_cache/disease_symptoms.json   : EN label -> [EN symptom...]
  - kaggle_cache/kaggle_to_canonical.json: EN symptom -> TR canonical
  - kaggle_cache/disease_descriptions.json: EN label -> EN description
  - disease_label_overrides.json         : EN label -> TR display label
  - disease_to_specialty.json            : EN label -> specialty_tr
  - kaggle_condition_meta.json (TR)      : TR label -> {disease_description_tr, ...}
  - curated_conditions.json              : extra curated diseases (TR-native)

Output: backend/app/data/disease_corpus.json
  {
    "version": "...",
    "items": [
      {
        "disease_label": "Migraine",        # source-of-truth EN key (matches Kaggle matrix)
        "tr_label": "Migren",                # display label
        "specialty_id": "neurology",
        "specialty_tr": "Nöroloji",
        "text": "Migren. <description>. Belirtiler: ..., .... Branş: Nöroloji."
      },
      ...
    ]
  }
"""

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "app" / "data"
CACHE_DIR = DATA_DIR / "kaggle_cache"
OUT_PATH = DATA_DIR / "disease_corpus.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        logger.warning(f"missing: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_kaggle_to_canonical(raw: Dict[str, Any]) -> Dict[str, str]:
    """kaggle_to_canonical.json maps EN symptom -> TR canonical (or None)."""
    if not raw:
        return {}
    return {k: v for k, v in raw.items() if v}


def disease_to_corpus_text(
    en_label: str,
    en_symptoms: List[str],
    kaggle_to_canonical: Dict[str, str],
    tr_label: str,
    tr_description: str,
    specialty_tr: str,
) -> str:
    canonical_symptoms: List[str] = []
    seen = set()
    for s in en_symptoms:
        tr = kaggle_to_canonical.get(s)
        if tr and tr not in seen:
            seen.add(tr)
            canonical_symptoms.append(tr)

    parts: List[str] = []
    parts.append(tr_label.strip() + ".")
    if tr_description:
        parts.append(tr_description.strip())
    if canonical_symptoms:
        parts.append("Belirtiler: " + ", ".join(canonical_symptoms) + ".")
    if specialty_tr:
        parts.append("Branş: " + specialty_tr.strip() + ".")
    return " ".join(parts)


def main() -> int:
    disease_symptoms = load_json(CACHE_DIR / "disease_symptoms.json") or {}
    kaggle_to_canonical_raw = load_json(CACHE_DIR / "kaggle_to_canonical.json") or {}
    en_descriptions = load_json(CACHE_DIR / "disease_descriptions.json") or {}
    label_overrides_doc = load_json(DATA_DIR / "disease_label_overrides.json") or {}
    spec_doc = load_json(DATA_DIR / "disease_to_specialty.json") or {}
    kaggle_meta_doc = load_json(DATA_DIR / "kaggle_condition_meta.json") or {}
    curated_doc = load_json(DATA_DIR / "curated_conditions.json") or {}

    if not disease_symptoms:
        logger.error("disease_symptoms.json missing or empty — run preprocess_kaggle.py first")
        return 1

    kaggle_to_canonical = build_kaggle_to_canonical(kaggle_to_canonical_raw)
    label_overrides: Dict[str, str] = label_overrides_doc.get("overrides", {})
    spec_map: Dict[str, Dict[str, Any]] = {
        e["disease_label"]: e for e in spec_doc.get("map", [])
    }
    kaggle_meta_conditions: Dict[str, Dict[str, Any]] = kaggle_meta_doc.get("conditions", {})

    items: List[Dict[str, Any]] = []
    skipped_no_specialty = 0

    for en_label, en_symptoms in disease_symptoms.items():
        spec_entry = spec_map.get(en_label) or spec_map.get(en_label.strip())
        if not spec_entry:
            skipped_no_specialty += 1
            continue

        tr_label = label_overrides.get(en_label) or label_overrides.get(en_label.strip()) or en_label
        meta = kaggle_meta_conditions.get(tr_label) or {}
        tr_description = meta.get("disease_description_tr") or en_descriptions.get(en_label, "")

        text = disease_to_corpus_text(
            en_label=en_label,
            en_symptoms=en_symptoms,
            kaggle_to_canonical=kaggle_to_canonical,
            tr_label=tr_label,
            tr_description=tr_description,
            specialty_tr=spec_entry.get("specialty_tr", ""),
        )

        items.append({
            "disease_label": en_label,
            "tr_label": tr_label,
            "specialty_id": spec_entry.get("specialty_id", ""),
            "specialty_tr": spec_entry.get("specialty_tr", ""),
            "text": text,
        })

    # Curated conditions (TR-native, no Kaggle symptom matrix entry)
    curated_items = curated_doc.get("conditions", []) if isinstance(curated_doc, dict) else []
    if isinstance(curated_items, dict):
        curated_items = list(curated_items.values())
    curated_added = 0
    for c in curated_items:
        if not isinstance(c, dict):
            continue
        disease_label = c.get("disease_label_tr") or c.get("disease_label") or c.get("label_tr")
        if not disease_label:
            continue
        if any(it["disease_label"] == disease_label or it["tr_label"] == disease_label for it in items):
            continue
        spec_id = c.get("specialty_id", "")
        spec_tr = c.get("specialty_tr", "")
        desc = c.get("disease_description_tr") or c.get("description_tr") or ""
        canonical_symptoms = c.get("canonical_symptoms_tr") or c.get("symptoms_tr") or []
        parts = [str(disease_label).strip() + "."]
        if desc:
            parts.append(str(desc).strip())
        if canonical_symptoms:
            parts.append("Belirtiler: " + ", ".join(canonical_symptoms) + ".")
        if spec_tr:
            parts.append("Branş: " + spec_tr + ".")
        items.append({
            "disease_label": str(disease_label),
            "tr_label": str(disease_label),
            "specialty_id": spec_id,
            "specialty_tr": spec_tr,
            "text": " ".join(parts),
            "source": "curated",
        })
        curated_added += 1

    payload = {
        "version": "1.0",
        "language": "tr-TR",
        "count": len(items),
        "items": items,
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    payload["content_hash"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        f"Wrote {OUT_PATH.relative_to(ROOT)} — {len(items)} items "
        f"(kaggle: {len(items) - curated_added}, curated: {curated_added}, "
        f"skipped_no_specialty: {skipped_no_specialty})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
