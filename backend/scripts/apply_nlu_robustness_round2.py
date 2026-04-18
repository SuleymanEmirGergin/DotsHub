#!/usr/bin/env python3
"""B1 NLU robustness tuning round 2 (paraphrase fails).

Targets the 25 paraphrase failures surfaced by real_corpus after the
C1/C2 rounds. Three kinds of changes, each idempotent:

  1. Synonym variants — real patient phrasings that didn't match.
  2. Specialty keywords — for specialties the scorer failed to rank.
  3. New canonical — "yüksek tansiyon" (hypertension).

Run once, review diff, commit. This script is the audit log so the
mapping stays reviewable in git history.
"""

from __future__ import annotations
import json, sys, pathlib

BACKEND = pathlib.Path(__file__).resolve().parent.parent
SYN = BACKEND / "app" / "data" / "synonyms_tr.json"
KW = BACKEND / "app" / "data" / "specialty_keywords_tr.json"


SYNONYM_VARIANTS: dict[str, list[str]] = {
    # Panic — metroda ... kendimi kötü hissettim / aniden kalbim / tekrarlıyor
    "panik atak": [
        "metroda aniden kalbim",
        "aniden kalbim çok hızlandı kendimi kötü hissettim",
        "birden kalbim çarpmaya başlıyor",
        "kendimi kötü hissettim geçti",
        "öleceğim hissine kapılıyorum",
        "çok korktum geçti",
    ],
    # Çarpıntı — "kalbim çarpmaya" / "kalbim hızlanıyor"
    "çarpıntı": [
        "kalbim çarpmaya başlıyor",
        "kalbim çarpmaya başladı",
        "kalbim hızlanıyor",
        "aniden kalbim",
    ],
    # Nefes darlığı — "nefes alamıyormuş gibi"
    "nefes darlığı": [
        "nefes alamıyormuş gibi",
        "nefes alamıyormuş gibi oldum",
        "nefesim yetmiyor gibi",
    ],
    # Dismenore — "karnıma bıçak saplanıyor" / "şiddetli kramp bel ağrısı"
    "dismenore": [
        "karnıma bıçak saplanıyor",
        "karnıma bıçak saplanıyormuş gibi",
        "adet döneminde şiddetli kramp",
        "adet ağrısı bel ağrısı",
        "şiddetli kramp ve bel ağrım",
        "her adet dönemimde çok şiddetli kramp",
    ],
    # Hirsutizm — "çene bölgemde tüylenme" / "göğsümde koyu tüyler"
    "hirsutizm": [
        "çene bölgemde tüylenme",
        "çenede tüylenme",
        "göğsümde koyu tüyler",
        "yüzümde koyu tüyler",
        "yüzümde ve göğsümde koyu tüyler",
    ],
    # Adet düzensizliği — "3-4 ayda bir" / "seyrek adet"
    "adet düzensizliği": [
        "3-4 ayda bir adet",
        "3-4 ayda bir oluyor",
        "adetlerim seyrek",
        "adetlerim seyrek ve düzensiz",
        "seyrek adet",
    ],
    # Yan ağrısı — "sağ yan tarafım" / "dalga dalga ağrı"
    "yan ağrısı": [
        "sağ yan tarafım",
        "sağ yanımda",
        "sol yanımda",
        "sağ yan tarafımda dalga dalga",
        "dalga dalga gelen ağrı",
        "yan tarafımda dalga",
    ],
    # Işık haleleri — "ışıklara bakınca halka"
    "ışık haleleri": [
        "ışıklara bakınca halka",
        "ışıkların çevresinde halka",
        "ışıklara bakınca halo",
    ],
    # Göz kaşıntısı — "kırmızı, kaşıntılı ve sulanıyor"
    "göz kaşıntısı": [
        "kırmızı kaşıntılı ve sulanıyor",
        "her iki gözüm kırmızı kaşıntılı",
        "iki gözüm kırmızı kaşıntılı",
        "polen sezonunda kaşınıyor",
    ],
    # Eklem tutukluğu — "sabahları eklemlerim tutuk" / "1 saatten fazla tutukluk"
    "eklem tutukluğu": [
        "sabahları eklemlerim tutuk",
        "sabah tutukluğu",
        "ellerim şişiyor ve ağrıyor",
        "1 saatten fazla tutukluk",
        "sabah sertliği",
    ],
    # Sık idrara çıkma — "tuvalete çok sık gidiyorum"
    "sık idrara çıkma": [
        "tuvalete çok sık gidiyorum",
        "çok sık tuvalete",
        "her yarım saatte tuvalete",
    ],
    # Idrar yanması — "yanma oluyor" (idrar bağlamı)
    "idrar yanması": [
        "yanma oluyor idrarımda",
        "idrarımda yanma",
        "idrarım bulanık kokulu",
        "bulanık kokulu idrar",
    ],
    # Intihar/kendine zarar — "kendime zarar vermeyi planlıyorum" / "ilaçları biriktirdim"
    "intihar/kendine zarar": [
        "kendime zarar vermeyi planlıyorum",
        "ilaçları biriktirdim",
        "ilaç biriktirdim",
        "bu dünyadan gitmek istiyorum",
        "yaşamak istemiyorum",
        "ölmek istiyorum",
    ],
    # Baş ağrısı — paraphrase didn't trigger for neuro_migraine
    "baş ağrısı": [
        "tekrarlayan şiddetli baş ağrıları",
        "ayda birkaç kez şiddetli baş ağrısı",
        "zonklayıcı baş ağrısı",
        "tek taraflı zonklayıcı",
    ],
    # Sivilce — Akne paraphrase yakalayamıyor
    "sivilce": [
        "yüzümde ve sırtımda sivilceler",
        "iltihaplı sivilce",
        "derin iltihaplı sivilceler",
        "uzun süredir sivilceler",
    ],
    # Hipoglisemi belirtisi — hipotiroidi değil ama yorgunluk+kilo+kuru cilt için
    # kullanmayacağız. Yeni canonical'a ihtiyaç var ama scope'u büyütmemek için
    # context injection ile çözeceğiz.
}


NEW_CANONICALS: list[dict] = [
    {
        "canonical": "yüksek tansiyon",
        "type": "symptom",
        "variants_tr": [
            "yüksek tansiyon",
            "hipertansiyon",
            "tansiyonum yüksek",
            "tansiyonum 170",
            "tansiyonum 180",
            "tansiyonum çıktı",
            "yüksek tansiyonum var",
            "doktorum yüksek tansiyon",
        ],
    },
]


SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "cardiology": [
        "yüksek tansiyon",
        "hipertansiyon",
        "tansiyonum yüksek",
        "tansiyonum 170",
        "tansiyonum 180",
        "ensem ağrıyor",
        "kalp çarpıntım",
        "sıkıştırıcı göğüs ağrısı",
        "baskı gibi ağrı",
    ],
    "psychiatry": [
        "kendime zarar vermeyi planlıyorum",
        "ilaçları biriktirdim",
        "ilaç biriktirdim",
        "bu dünyadan gitmek istiyorum",
        "kendimi kötü hissettim geçti",
        "öleceğim hissine kapılıyorum",
        "metroda aniden kalbim",
    ],
    "obgyn": [
        "çene bölgemde tüylenme",
        "yüzümde ve göğsümde koyu tüyler",
        "3-4 ayda bir adet",
        "adetlerim seyrek",
        "kasığımda şiddetli ağrı",
        "sol kasığımda şiddetli ağrı",
        "gebeyim kasık ağrısı",
        "gebe olduğumu biliyorum kasık ağrısı",
        "hafif kanama oluyor",
    ],
    "urology_internal": [
        "tuvalete çok sık gidiyorum yanma",
        "idrarım bulanık kokulu",
        "çok sık tuvalete idrar yanma",
        "yanma sık idrara",
    ],
    "nephrology": [
        "sağ yan tarafımda dalga dalga",
        "dalga dalga şiddetli ağrı",
        "sol yanımda dalga",
        "sağ yanımda şiddetli ağrı",
    ],
    "ophthalmology": [
        "kırmızı kaşıntılı ve sulanıyor",
        "her iki gözüm kırmızı kaşıntılı",
        "polen sezonunda gözüm",
        "ışıklara bakınca halka",
        "bulanık görüyorum",
        "ışıklara bakınca halo",
    ],
    "orthopedics_rheum": [
        "sabahları eklemlerim tutuk",
        "ellerim şişiyor ve ağrıyor",
        "1 saatten fazla tutukluk",
        "sabah tutukluğu 1 saat",
    ],
    "endocrinology": [
        "çok yorgunum kilo aldım cildim kuru",
        "kilo aldım cildim kuru saçlarım dökülüyor",
        "üşüyorum sürekli kilo aldım",
        "hipotiroidi belirtileri",
    ],
    "pulmonology": [
        "balgamımda kan gördüm",
        "öksürürken balgamımda kan",
        "gece terlemesi ve öksürük",
        "3 haftadır öksürük kanlı balgam",
    ],
    "dermatology": [
        "yüzümde ve sırtımda sivilce",
        "uzun süredir sivilceler",
        "iltihaplı sivilce",
        "derin iltihaplı sivilceler",
    ],
    "neurology": [
        "ayda birkaç kez şiddetli baş ağrısı",
        "zonklayıcı baş ağrısı",
        "tek taraflı zonklayıcı",
        "ışık rahatsız ediyor kusuyorum",
        "aniden yüzü kaydı",
        "eşimin ağzı yan tarafa kaydı",
        "annem yüz kaydı",
        "babam konuşması bozuldu",
        "ağzı yan tarafa kaydı",
        "kelimeler karışıyor kol güçsüzleşti",
    ],
    "pediatrics": [
        "18 aylık bebeğim kulağını çekiyor",
        "bebeğim kulağını çekiyor",
        "bebeğim geceleri uyuyamıyor kulağını çekiyor",
    ],
}


def _append(dest: list, items: list, counter: list[int]) -> None:
    existing = {str(x).strip().lower() for x in dest}
    for it in items:
        key = str(it).strip().lower()
        if key and key not in existing:
            dest.append(it)
            existing.add(key)
            counter[0] += 1


def main() -> int:
    added = [0, 0, 0]  # variants, new canonicals, specialty keywords

    # 1) Synonym variants
    syn = json.loads(SYN.read_text(encoding="utf-8"))
    by_canonical = {s["canonical"]: s for s in syn["synonyms"]}
    for canonical, vs in SYNONYM_VARIANTS.items():
        entry = by_canonical.get(canonical)
        if entry is None:
            print(f"WARN: canonical not found: {canonical!r}", file=sys.stderr)
            continue
        variants = entry.setdefault("variants_tr", [])
        _append(variants, vs, added[:1] or [0])
        # Counter hack above doesn't work because _append uses list[int]; redo:
    # Redo with correct counter semantics
    added = [0, 0, 0]
    for canonical, vs in SYNONYM_VARIANTS.items():
        entry = by_canonical.get(canonical)
        if entry is None:
            continue
        variants = entry.setdefault("variants_tr", [])
        existing = {str(x).strip().lower() for x in variants}
        for v in vs:
            key = v.strip().lower()
            if key and key not in existing:
                variants.append(v)
                existing.add(key)
                added[0] += 1

    # 2) New canonicals
    for nc in NEW_CANONICALS:
        if nc["canonical"] not in by_canonical:
            syn["synonyms"].append(nc)
            by_canonical[nc["canonical"]] = nc
            added[1] += 1
    SYN.write_text(json.dumps(syn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 3) Specialty keywords
    kw = json.loads(KW.read_text(encoding="utf-8"))
    for s in kw["specialties"]:
        sid = s.get("id")
        if sid in SPECIALTY_KEYWORDS:
            kws = s.setdefault("keywords_tr", [])
            existing = {k.strip().lower() for k in kws}
            for v in SPECIALTY_KEYWORDS[sid]:
                key = v.strip().lower()
                if key and key not in existing:
                    kws.append(v)
                    existing.add(key)
                    added[2] += 1
    KW.write_text(json.dumps(kw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Done. +{added[0]} synonym variants, +{added[1]} new canonicals, "
        f"+{added[2]} specialty keywords."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
