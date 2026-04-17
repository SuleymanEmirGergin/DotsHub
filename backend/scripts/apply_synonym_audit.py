#!/usr/bin/env python3
"""One-shot: apply the Turkish NLU synonym audit (Root Cause #2).

Targets the canonical-extraction gaps catalogued in
memory/project_pretriage_synonym_audit.md. For each real patient
phrasing surfaced by the golden-flow triage triage, either:

  - add a variant to an existing canonical in synonyms_tr.json, OR
  - add a new canonical when no close match exists.

Run once, review the diff with git, then delete or keep as documentation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve()
_BACKEND = _SCRIPT.parent.parent
SYNONYMS_PATH = _BACKEND / "app" / "data" / "synonyms_tr.json"


# Variants to add to existing canonicals. {canonical: [variant, ...]}
# Every variant is appended only if not already present (idempotent).
VARIANTS_TO_ADD: dict[str, list[str]] = {
    "çarpıntı": [
        "kalbim hızlandı",
        "kalp hızlanması",
        "kalbim çarpıyor",
        "kalp çarpıntısı",
        "kalbim atıyor gibi",
    ],
    "nefes darlığı": [
        "nefes alamadım",
        "nefes alamıyorum",
        "soluk alamıyorum",
        "nefesim daraldı",
        "nefesim kesildi",
    ],
    "panik atak": [
        "öleceğimi sandım",
        "öleceğim korkusu",
        "kontrolü kaybetme korkusu",
        "aniden korktum",
        "panik yaşadım",
    ],
    "ani görme kaybı": [
        "perde indi",
        "perde iniyor",
        "göremiyorum",
        "o taraf görmüyor",
        "gözümde perde",
        "aniden kör oldum",
    ],
    "dismenore": [
        "adet sancısı",
        "şiddetli kramplar",
        "adet krampları",
        "adet ağrısı",
        "regl ağrısı",
        "adet dönemimde çok şiddetli kramplar",
    ],
    "hematüri": [
        "kırmızı idrar",
        "kırmızımsı idrar",
        "idrarımda kan",
        "idrarda kan",
        "idrarımın rengi kırmızı",
        "kan işedim",
    ],
    "yan ağrısı": [
        "böbreğim ağrıyor",
        "sol böbreğim ağrıyor",
        "sağ böbreğim ağrıyor",
        "sol böbrek ağrısı",
        "sağ böbrek ağrısı",
        "lomber ağrı",
    ],
    "adet düzensizliği": [
        "düzensiz adet",
        "2-3 ayda bir adet",
        "adetler seyrek",
        "adetlerim düzensiz",
        "adet gecikmesi",
    ],
    "febril konvülziyon": [
        "kasılmaya başladı",
        "havale geçirdi",
        "havale",
        "gözleri döndü",
        "bilinci gitti",
        "kasılıyor",
        "nöbet geçirdi",
    ],
    "sağ alt karın ağrısı": [
        "sağ alt karnım ağrıyor",
        "sağ alt karın bölgem",
        "sağ alt kadranda ağrı",
    ],
    "göz kızarıklığı": [
        "gözüm kırmızı",
        "gözlerim kırmızı",
        "iki gözüm de kırmızı",
    ],
}

# Entirely new canonicals to append.
NEW_CANONICALS: list[dict] = [
    {
        "canonical": "ışık haleleri",
        "type": "symptom",
        "variants_tr": [
            "ışıkların etrafında hale",
            "ışıkların etrafında halka",
            "ışıkta hale görüyorum",
            "ışıkların etrafında çember",
            "halo görme",
        ],
    },
    {
        "canonical": "yenidoğan ateşi",
        "type": "symptom",
        "variants_tr": [
            "6 haftalık bebeğim ateş",
            "2 aylık bebeğim ateş",
            "yenidoğanda ateş",
            "1 aylık bebeğim 38",
            "3 aydan küçük bebeğim ateş",
            "yenidoğan bebeğim ateşlendi",
            "bebeğim 6 haftalık ve 38",
            "bebeğim 6 haftalık ve termometre 38",
        ],
    },
    {
        "canonical": "hirsutizm",
        "type": "symptom",
        "variants_tr": [
            "yüzümde tüylenme",
            "erkeksi kıllanma",
            "yüzde kıllanma arttı",
            "istenmeyen tüylenme",
        ],
    },
    {
        "canonical": "konjunktivit",
        "type": "symptom",
        "variants_tr": [
            "gözüm hem kaşınıyor hem sulanıyor",
            "göz kaşıntısı ve sulanma",
            "kaşınıyor sulanıyor kırmızı",
        ],
    },
]


def main() -> int:
    data = json.loads(SYNONYMS_PATH.read_text(encoding="utf-8"))
    synonyms = data.setdefault("synonyms", [])
    by_canonical = {s["canonical"]: s for s in synonyms}

    added_variants = 0
    added_canonicals = 0
    skipped_variants = 0

    # 1) Extend existing canonicals
    for canonical, new_variants in VARIANTS_TO_ADD.items():
        entry = by_canonical.get(canonical)
        if entry is None:
            print(f"WARN: canonical not found, skipping: {canonical!r}", file=sys.stderr)
            continue
        variants = entry.setdefault("variants_tr", [])
        existing = {v.strip().lower() for v in variants}
        for v in new_variants:
            if v.strip().lower() in existing:
                skipped_variants += 1
                continue
            variants.append(v)
            existing.add(v.strip().lower())
            added_variants += 1

    # 2) Append new canonicals (only if not already there)
    for new_c in NEW_CANONICALS:
        if new_c["canonical"] in by_canonical:
            print(
                f"WARN: canonical already exists, skipping NEW: "
                f"{new_c['canonical']!r}",
                file=sys.stderr,
            )
            continue
        synonyms.append(new_c)
        by_canonical[new_c["canonical"]] = new_c
        added_canonicals += 1

    # Write back with the same formatting the file uses (2-space indent,
    # no trailing newline preserved by json.dumps; add one for POSIX).
    SYNONYMS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Done. Added {added_variants} variants across {len(VARIANTS_TO_ADD)} "
        f"canonicals (skipped {skipped_variants} already present). Added "
        f"{added_canonicals} new canonicals. Total canonicals now: "
        f"{len(synonyms)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
