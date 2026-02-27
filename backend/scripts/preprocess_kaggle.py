#!/usr/bin/env python3
"""Offline preprocessing script: Kaggle CSV files -> deterministic JSON caches.

Usage:
    python scripts/preprocess_kaggle.py

Expects CSV files in backend/raw_data/:
    - dataset.csv             (Disease, Symptom_1, ..., Symptom_17)
    - Symptom-severity.csv    (Symptom, weight)
    - symptom_Description.csv (Disease, Description)

Outputs to backend/app/data/kaggle_cache/:
    - disease_symptoms.json     -- { disease: [symptom, ...] }
    - symptom_severity.json     -- { symptom: weight }
    - disease_descriptions.json -- { disease: description }
    - kaggle_to_canonical.json  -- { kaggle_symptom: canonical_tr | null }
"""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
RAW_DATA_DIR = BACKEND_DIR / "raw_data"
DATA_DIR = BACKEND_DIR / "app" / "data"
CACHE_DIR = DATA_DIR / "kaggle_cache"
SYNONYMS_FILE = DATA_DIR / "synonyms_tr.json"

# ─── Helpers ───

def normalize_symptom(s: str) -> str:
    """Normalize a Kaggle symptom name: strip, lowercase, collapse spaces/underscores."""
    s = s.strip().lower()
    s = re.sub(r"[\s_]+", "_", s)
    # Fix known Kaggle typos
    s = s.replace("dischromic _patches", "dischromic_patches")
    s = s.replace("spotting_ urination", "spotting_urination")
    return s


def human_readable(s: str) -> str:
    """Convert snake_case to human readable."""
    return s.replace("_", " ").strip()


# ─── Kaggle-to-canonical mapping ───

# Manual mapping from Kaggle English symptom names to our Turkish canonicals
# (from synonyms_tr.json). Unmapped symptoms stay as English (None).
KAGGLE_TO_CANONICAL_MANUAL = {
    "headache": "baş ağrısı",
    "dizziness": "baş dönmesi",
    "spinning_movements": "baş dönmesi",
    "loss_of_balance": "baş dönmesi",
    "unsteadiness": "baş dönmesi",
    "nausea": "bulantı",
    "vomiting": "kusma",
    "diarrhoea": "ishal",
    "constipation": "kabızlık",
    "chest_pain": "göğüs ağrısı",
    "breathlessness": "nefes darlığı",
    "fast_heart_rate": "çarpıntı",
    "palpitations": "çarpıntı",
    "high_fever": "ateş",
    "mild_fever": "ateş",
    "throat_irritation": "boğaz ağrısı",
    "patches_in_throat": "boğaz ağrısı",
    "cough": "öksürük",
    "phlegm": "öksürük",
    "mucoid_sputum": "öksürük",
    "rusty_sputum": "öksürük",
    "blood_in_sputum": "kanlı balgam",
    "burning_micturition": "idrar yanması",
    "continuous_feel_of_urine": "sık idrara çıkma",
    "bladder_discomfort": "idrar yanması",
    "foul_smell_ofurine": "idrar yanması",
    "spotting_urination": "idrar yanması",
    "skin_rash": "döküntü/ürtiker",
    "itching": "kaşıntı",
    "nodal_skin_eruptions": "döküntü/ürtiker",
    "red_spots_over_body": "kızarıklık",
    "pus_filled_pimples": "sivilce",
    "blackheads": "sivilce",
    "skin_peeling": "leke",
    "dischromic_patches": "leke",
    "weakness_of_one_body_side": "tek taraflı güçsüzlük/uyuşma",
    "slurred_speech": "konuşma bozukluğu",
    "puffy_face_and_eyes": "yüz/dudak şişmesi",
    "stomach_pain": "karın ağrısı",
    "abdominal_pain": "karın ağrısı",
    "belly_pain": "karın ağrısı",
    "acidity": "hazımsızlık",
    "indigestion": "hazımsızlık",
    "passage_of_gases": "hazımsızlık",
    "back_pain": "bel/sırt ağrısı",
    "neck_pain": "boyun ağrısı",
    "stiff_neck": "boyun ağrısı",
    "joint_pain": "eklem ağrısı",
    "knee_pain": "eklem ağrısı",
    "hip_joint_pain": "eklem ağrısı",
    "swelling_joints": "şişlik",
    "movement_stiffness": "eklem tutukluğu",
    "muscle_pain": "kas ağrısı",
    "muscle_weakness": "kas ağrısı",
    "cramps": "kas ağrısı",
    "fatigue": "halsizlik",
    "lethargy": "halsizlik",
    "malaise": "halsizlik",
    "restlessness": "halsizlik",
    "weight_loss": "kilo kaybı",
    "weight_gain": "kilo artışı",
    "loss_of_appetite": "iştahsızlık",
    "excessive_hunger": "aşırı açlık",
    "increased_appetite": "aşırı açlık",
    "sweating": "terleme",
    "chills": "titreme/üşüme",
    "shivering": "titreme/üşüme",
    "dehydration": "dehidrasyon",
    "dark_urine": "koyu idrar",
    "yellow_urine": "koyu idrar",
    "yellowish_skin": "sarılık",
    "yellowing_of_eyes": "sarılık",
    "blurred_and_distorted_vision": "bulanık görme",
    "visual_disturbances": "bulanık görme",
    "depression": "depresyon/ruh hali",
    "irritability": "depresyon/ruh hali",
    "mood_swings": "depresyon/ruh hali",
    "anxiety": "anksiyete",
    "lack_of_concentration": "konsantrasyon kaybı",
    "altered_sensorium": "bilinç değişikliği",
    "coma": "bilinç değişikliği",
    "congestion": "burun tıkanıklığı",
    "runny_nose": "burun tıkanıklığı",
    "continuous_sneezing": "burun tıkanıklığı",
    "sinus_pressure": "sinüs basıncı",
    "watering_from_eyes": "göz yaşarması",
    "redness_of_eyes": "göz kızarıklığı",
    "pain_behind_the_eyes": "göz ağrısı",
    "obesity": "obezite",
    "polyuria": "sık idrara çıkma",
    "irregular_sugar_level": "kan şekeri düzensizliği",
    "swelled_lymph_nodes": "lenf bezi şişliği",
    "swollen_legs": "bacak şişliği",
    "swollen_blood_vessels": "damar şişliği",
    "swollen_extremeties": "uzuv şişliği",
    "enlarged_thyroid": "tiroid büyümesi",
    "brittle_nails": "tırnak kırılganlığı",
    "inflammatory_nails": "tırnak iltihabı",
    "small_dents_in_nails": "tırnak değişikliği",
    "silver_like_dusting": "leke",
    "prominent_veins_on_calf": "damar şişliği",
    "sunken_eyes": "dehidrasyon",
    "muscle_wasting": "kas erimesi",
    "extra_marital_contacts": None,  # not a symptom
    "family_history": None,  # not a symptom
    "receiving_blood_transfusion": None,
    "receiving_unsterile_injections": None,
    "history_of_alcohol_consumption": None,
    "fluid_overload": "ödem",
    "internal_itching": "kaşıntı",
    "toxic_look_(typhos)": "ateş",
    "ulcers_on_tongue": "ağız yarası",
    "painful_walking": "yürüme güçlüğü",
    "pain_during_bowel_movements": "anal ağrı",
    "pain_in_anal_region": "anal ağrı",
    "bloody_stool": "kanlı dışkı",
    "irritation_in_anus": "karın ağrısı",
    "acute_liver_failure": "karaciğer yetmezliği",
    "stomach_bleeding": "mide kanaması",
    "distention_of_abdomen": "karın şişliği",
    "swelling_of_stomach": "karın şişliği",
    "cold_hands_and_feets": "soğuk el/ayak",
    "weakness_in_limbs": "uzuv güçsüzlüğü",
    "bruising": "morarma",
    "scurring": "yara izi",
    "red_sore_around_nose": "burun çevresi yara",
    "yellow_crust_ooze": "kabarcık",
    "prognosis": None,
    "blister": "kabarcık",
    "drying_and_tingling_lips": "dudak kuruluğu",
    "loss_of_smell": "koku kaybı",
    "abnormal_menstruation": "adet düzensizliği",
}


def build_kaggle_to_canonical() -> dict:
    """Build the complete mapping, combining manual + synonym-based."""
    mapping = {}
    for kaggle_name, canonical in KAGGLE_TO_CANONICAL_MANUAL.items():
        mapping[kaggle_name] = canonical
    return mapping


# ─── Main Processing ───

def process_dataset_csv(path: Path) -> dict:
    """Parse dataset.csv -> {disease: set(symptoms)}."""
    diseases = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header if present
        for row in reader:
            if not row or not row[0].strip():
                continue
            disease = row[0].strip()
            symptoms = set()
            for cell in row[1:]:
                s = normalize_symptom(cell)
                if s:
                    symptoms.add(s)
            if disease not in diseases:
                diseases[disease] = set()
            diseases[disease] |= symptoms
    # Convert sets to sorted lists
    return {d: sorted(syms) for d, syms in sorted(diseases.items())}


def process_severity_csv(path: Path) -> dict:
    """Parse Symptom-severity.csv -> {symptom: weight}."""
    severity = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 2:
                symptom = normalize_symptom(row[0])
                try:
                    weight = int(row[1].strip())
                except ValueError:
                    weight = 1
                if symptom:
                    severity[symptom] = weight
    return dict(sorted(severity.items()))


def process_description_csv(path: Path) -> dict:
    """Parse symptom_Description.csv -> {disease: description}."""
    descriptions = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 2 and row[0].strip():
                descriptions[row[0].strip()] = row[1].strip()
    return dict(sorted(descriptions.items()))


def run_mapping_validator() -> int:
    """Run mapping guardrails after cache generation."""
    validator_path = SCRIPT_DIR / "validate_kaggle_mapping.py"
    if not validator_path.exists():
        print("WARNING: Validator script missing.")
        print("Run manually: python scripts/validate_kaggle_mapping.py")
        return 0

    print("\nRunning mapping guardrails ...")
    result = subprocess.run(
        [sys.executable, str(validator_path)],
        cwd=str(BACKEND_DIR),
        check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: Mapping validator failed with exit code {result.returncode}.")
    return int(result.returncode)


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Check input files
    dataset_csv = RAW_DATA_DIR / "dataset.csv"
    severity_csv = RAW_DATA_DIR / "Symptom-severity.csv"
    description_csv = RAW_DATA_DIR / "symptom_Description.csv"

    if not dataset_csv.exists():
        print(f"ERROR: {dataset_csv} not found. Place Kaggle CSV files in {RAW_DATA_DIR}/")
        sys.exit(1)

    # 1) Process disease-symptom matrix
    print("Processing dataset.csv ...")
    disease_symptoms = process_dataset_csv(dataset_csv)
    out_path = CACHE_DIR / "disease_symptoms.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(disease_symptoms, f, ensure_ascii=False, indent=2)
    print(f"  -> {out_path} ({len(disease_symptoms)} diseases)")

    # Collect all unique symptoms
    all_symptoms = set()
    for syms in disease_symptoms.values():
        all_symptoms.update(syms)
    print(f"  -> {len(all_symptoms)} unique symptoms")

    # 2) Process severity weights
    if severity_csv.exists():
        print("Processing Symptom-severity.csv ...")
        symptom_severity = process_severity_csv(severity_csv)
        out_path = CACHE_DIR / "symptom_severity.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(symptom_severity, f, ensure_ascii=False, indent=2)
        print(f"  -> {out_path} ({len(symptom_severity)} symptoms)")
    else:
        print(f"  WARNING: {severity_csv} not found, generating defaults")
        symptom_severity = {s: 3 for s in sorted(all_symptoms)}
        out_path = CACHE_DIR / "symptom_severity.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(symptom_severity, f, ensure_ascii=False, indent=2)

    # 3) Process descriptions
    if description_csv.exists():
        print("Processing symptom_Description.csv ...")
        descriptions = process_description_csv(description_csv)
        out_path = CACHE_DIR / "disease_descriptions.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(descriptions, f, ensure_ascii=False, indent=2)
        print(f"  -> {out_path} ({len(descriptions)} diseases)")
    else:
        print(f"  WARNING: {description_csv} not found, generating empty")
        out_path = CACHE_DIR / "disease_descriptions.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

    # 4) Build kaggle-to-canonical mapping
    print("Building kaggle_to_canonical.json ...")
    mapping = build_kaggle_to_canonical()

    # Add any symptoms from dataset not in manual mapping
    for sym in sorted(all_symptoms):
        if sym not in mapping:
            mapping[sym] = None  # unmapped

    out_path = CACHE_DIR / "kaggle_to_canonical.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(mapping.items())), f, ensure_ascii=False, indent=2)

    mapped_count = sum(1 for v in mapping.values() if v is not None)
    print(f"  -> {out_path} ({mapped_count}/{len(mapping)} mapped to canonical)")

    # Summary
    print(f"\nDone! {len(disease_symptoms)} diseases, {len(all_symptoms)} symptoms, "
          f"{mapped_count} canonical mappings.")
    print(f"Output: {CACHE_DIR}/")
    print("Validation command: python scripts/validate_kaggle_mapping.py")

    validation_rc = run_mapping_validator()
    if validation_rc != 0:
        sys.exit(validation_rc)


if __name__ == "__main__":
    main()
