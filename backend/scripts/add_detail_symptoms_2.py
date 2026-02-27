#!/usr/bin/env python3
"""Add fever_degree_celsius, sputum_color, abdominal_pain_location to disease_symptoms.json."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "app" / "data" / "kaggle_cache"
DISEASE_SYMPTOMS = DATA / "disease_symptoms.json"

def main():
    with open(DISEASE_SYMPTOMS, "r", encoding="utf-8") as f:
        data = json.load(f)

    # fever_degree_celsius -> diseases that have high_fever or mild_fever
    for disease, syms in data.items():
        if "high_fever" in syms or "mild_fever" in syms:
            if "fever_degree_celsius" not in syms:
                syms.append("fever_degree_celsius")

    # sputum_color -> diseases that have phlegm, mucoid_sputum, rusty_sputum
    for disease, syms in data.items():
        if any(s in syms for s in ["phlegm", "mucoid_sputum", "rusty_sputum"]):
            if "sputum_color" not in syms:
                syms.append("sputum_color")

    # abdominal_pain_location -> diseases that have abdominal_pain or belly_pain
    for disease, syms in data.items():
        if "abdominal_pain" in syms or "belly_pain" in syms:
            if "abdominal_pain_location" not in syms:
                syms.append("abdominal_pain_location")

    with open(DISEASE_SYMPTOMS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Updated disease_symptoms.json (fever_degree, sputum_color, abdominal_pain_location)")

if __name__ == "__main__":
    main()
