#!/usr/bin/env python3
"""Add detail symptoms (duration, timing, exertion) to disease_symptoms.json."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "app" / "data" / "kaggle_cache"
DISEASE_SYMPTOMS = DATA / "disease_symptoms.json"

# Disease -> list of new symptoms to add (only if not already present)
ADDITIONS = {
    "Migraine": ["headache_duration_days", "headache_worse_morning"],
    "Malaria": ["diarrhoea_duration_days", "fever_duration_days", "headache_duration_days"],
    "Dengue": ["fever_duration_days", "headache_duration_days"],
    "Chicken pox": ["fever_duration_days", "headache_duration_days"],
    "Common Cold": ["fever_duration_days", "headache_duration_days"],
    "Hypoglycemia": ["headache_duration_days"],
    "Paralysis (brain hemorrhage)": ["headache_duration_days"],
    "Typhoid": [
        "abdominal_pain_duration_days",
        "diarrhoea_duration_days",
        "fever_duration_days",
        "headache_duration_days",
    ],
    "GERD": ["abdominal_pain_duration_days"],
    "Peptic ulcer diseae": ["abdominal_pain_duration_days"],
    "Gastroenteritis": ["diarrhoea_duration_days"],
    "Pneumonia": ["fever_duration_days", "breathlessness_on_exertion"],
    "Tuberculosis": ["fever_duration_days", "breathlessness_on_exertion"],
    "Bronchial Asthma": ["breathlessness_on_exertion"],
    "Heart attack": ["breathlessness_on_exertion"],
    "Alcoholic hepatitis": ["abdominal_pain_duration_days"],
    "Chronic cholestasis": ["abdominal_pain_duration_days"],
    "Jaundice": ["abdominal_pain_duration_days"],
    "Hepatitis B": ["abdominal_pain_duration_days", "fever_duration_days"],
    "Hepatitis D": ["abdominal_pain_duration_days", "fever_duration_days"],
    "Hepatitis E": ["abdominal_pain_duration_days", "fever_duration_days", "diarrhoea_duration_days"],
    "hepatitis A": ["abdominal_pain_duration_days", "fever_duration_days", "diarrhoea_duration_days"],
    "(vertigo) Paroymsal  Positional Vertigo": ["headache_duration_days"],
}

def main():
    with open(DISEASE_SYMPTOMS, "r", encoding="utf-8") as f:
        data = json.load(f)
    for disease, new_syms in ADDITIONS.items():
        if disease not in data:
            continue
        current = set(data[disease])
        for s in new_syms:
            if s not in current:
                data[disease].append(s)
                current.add(s)
    with open(DISEASE_SYMPTOMS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Updated disease_symptoms.json")

if __name__ == "__main__":
    main()
