#!/usr/bin/env python3
"""B2 coverage expansion for synthetic_new paraphrases (23 fails).

This adds:
  - specialty keywords for new clinical patterns (sinüzit, bel ağrısı,
    siyatik, diz yaralanması, kronik öksürük, bebek/çocuk ishal, döküntü
    + ateş, mantar enfeksiyonu, psoriasis, konjunktivit-otitis-externa
    ayrımı, arpacık, kataract, frozen shoulder, OCD, insomnia, …)
  - synonym variants (hipertansiyon "170/100", hipertiroidi combo, …)

Run once, review diff, commit.
"""

from __future__ import annotations
import json, sys, pathlib

BACKEND = pathlib.Path(__file__).resolve().parent.parent
SYN = BACKEND / "app" / "data" / "synonyms_tr.json"
KW = BACKEND / "app" / "data" / "specialty_keywords_tr.json"


SYNONYM_VARIANTS: dict[str, list[str]] = {
    "yüksek tansiyon": [
        "170/100",
        "180/110",
        "tansiyonum 170/100",
        "evde ölçtüm 170",
    ],
    "baş ağrısı": [
        "başım ağrıyor ve halsizlik",
    ],
    "halsizlik": [
        "halsiz hissediyorum",
        "çok yorgunum kilo aldım",
    ],
    "öksürük": [
        "1 aydır kuru öksürük",
        "kuru öksürüğüm geçmiyor",
        "geceleri artıyor öksürük",
    ],
    "uyku bozukluğu": [
        "2 aydır uyuyamıyorum",
        "3-4 saat uyuyabiliyorum",
        "uykuya dalmakta zorlanıyorum",
    ],
    "konsantrasyon bozukluğu": [
        "kontrol etme takıntım var",
        "sürekli endişeliyim",
    ],
    "çocukta ishal ve dehidrasyon": [
        "3 yaşındaki kızım 2 gündür ishalde",
        "2 yaşındaki oğlum ishal",
        "günde 5-6 kez sulu ishal",
    ],
    "çocukta döküntü ve ateş": [
        "4 yaşındaki oğlumun vücudunda kırmızı noktalar",
        "kırmızı noktalar çıktı ateş",
        "boynunda bez var ateşi",
    ],
    "dökűntű/ürtiker": [],  # (typo-guard — not a canonical)
}


NEW_CANONICALS: list[dict] = [
    {
        "canonical": "ayak mantarı",
        "type": "symptom",
        "variants_tr": [
            "ayak parmaklarımın arasında kaşıntılı",
            "ayak parmakları arası kaşıntı",
            "ayakta soyulan döküntü",
            "havuza gittikten sonra kaşıntı",
            "atlet ayağı",
        ],
    },
    {
        "canonical": "psoriasis belirtisi",
        "type": "symptom",
        "variants_tr": [
            "gümüş beyaz kepekli plaklar",
            "dirseklerim gümüş kepekli",
            "saçlı derimde kepekli plaklar",
            "kırmızı plaklar kepekli",
            "psoriasis",
            "sedef hastalığı",
        ],
    },
    {
        "canonical": "kulak kanalı akıntısı",
        "type": "symptom",
        "variants_tr": [
            "kulak kanalım ağrıyor",
            "kulakta akıntı kaşıntı",
            "yüzerken kulağıma su kaçtı",
            "dış kulak iltihabı",
        ],
    },
    {
        "canonical": "sinüs basıncı",
        "type": "symptom",
        "variants_tr": [
            "yüzümde basınç",
            "alın ve yanak bölgesinde basınç",
            "yüzümde alın ve yanak basınç",
            "burnum tıkalı ve akıyor",
            "sinüzit",
        ],
    },
    {
        "canonical": "bademcik iltihabı",
        "type": "symptom",
        "variants_tr": [
            "bademciklerim şiş",
            "bademciklerim beyaz lekeli",
            "tonsillit",
            "yutkunamıyorum ateş",
        ],
    },
    {
        "canonical": "bel ağrısı",
        "type": "symptom",
        "variants_tr": [
            "belimde çok şiddetli ağrı",
            "belim ağrıyor",
            "bel ağrım bacağıma vuruyor",
            "bel ağrısı bacağa yayılıyor",
            "siyatik ağrı",
            "siyatik",
            "otururken artıyor bel ağrısı",
        ],
    },
    {
        "canonical": "diz yaralanması",
        "type": "symptom",
        "variants_tr": [
            "dizim döndü",
            "dizim şişti ve ağrıyor",
            "dize basamıyorum",
            "menisküs",
            "bağ yaralanması",
        ],
    },
    {
        "canonical": "omuz ağrısı",
        "type": "symptom",
        "variants_tr": [
            "omzum ağrıyor",
            "omzumu kaldıramıyorum",
            "donuk omuz",
            "frozen shoulder",
            "omuz hareketi kısıtlı",
        ],
    },
    {
        "canonical": "arpacık belirtisi",
        "type": "symptom",
        "variants_tr": [
            "göz kapağımda ağrılı kırmızı şişlik",
            "göz kapağında küçük şişlik",
            "arpacık",
            "göz kapağı sivilce gibi",
        ],
    },
    {
        "canonical": "görme bulanıklığı ilerleyen",
        "type": "symptom",
        "variants_tr": [
            "görüşüm yavaş yavaş bulanıklaştı",
            "geceleri farlar etrafında kamaşma",
            "kataract",
            "göz merceği bulanıklaşması",
            "yaş bağlı görme azalması",
        ],
    },
    {
        "canonical": "hipertiroidi belirtisi",
        "type": "symptom",
        "variants_tr": [
            "kilo verdim çarpıntım var",
            "ellerim titriyor ve çok terliyorum",
            "iştahım iyi ama zayıflıyorum",
            "hipertiroidi",
            "tiroid yüksek",
        ],
    },
    {
        "canonical": "obsesif kompülsif belirti",
        "type": "symptom",
        "variants_tr": [
            "günde 20 kez ellerimi yıkıyorum",
            "kontrol etme takıntı",
            "takıntı var",
            "kompülsiyon",
            "obsesif",
            "evden çıkamıyorum takıntı",
        ],
    },
    {
        "canonical": "gebelik takibi isteği",
        "type": "symptom",
        "variants_tr": [
            "adetim gecikti test pozitif",
            "gebeyim ilk kontrol",
            "gebelik takibi",
            "ilk prenatal kontrol",
        ],
    },
    {
        "canonical": "menopoz belirtisi yaşam",
        "type": "symptom",
        "variants_tr": [
            "sıcak basması gece terlemesi",
            "6 aydır adet görmedim",
            "50 yaşında adet yok",
            "menopoz dönemi",
        ],
    },
]


SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "cardiology": [
        "tansiyon 170/100",
        "tansiyon 180/110",
        "evde ölçtüm 170",
        "başım ağrıyor tansiyon",
    ],
    "pulmonology": [
        "1 aydır kuru öksürük",
        "kuru öksürüğüm geçmiyor",
        "geceleri artıyor öksürük",
        "5 gündür öksürük balgam göğüs ağrısı",
        "öksürük balgam ateş nefes darlığı",
        "pnömoni",
        "zatürre",
        "akciğer enfeksiyonu",
    ],
    "orthopedics_rheum": [
        "belimde şiddetli ağrı",
        "belim ağrıyor bacağa vuruyor",
        "siyatik",
        "siyatik ağrı",
        "dizim döndü",
        "dizim şişti",
        "dize basamıyorum",
        "omzum ağrıyor kaldıramıyorum",
        "donuk omuz",
        "frozen shoulder",
        "omuz hareketi kısıtlı",
    ],
    "endocrinology": [
        "hipertiroidi",
        "tiroid yüksek",
        "kilo verdim çarpıntım var ellerim titriyor",
        "kilo verdim çarpıntı",
        "ellerim titriyor terliyorum",
        "iştahım iyi ama zayıflıyorum",
        "yorgunum kilo aldım cildim kuru saçlarım dökülüyor",
    ],
    "psychiatry": [
        "günde 20 kez ellerimi yıkıyorum",
        "kontrol etme takıntı",
        "takıntı var",
        "evden çıkamıyorum takıntı",
        "2 aydır 3-4 saat uyuyorum",
        "uykuya dalmakta zorlanıyorum",
        "3-4 saat uyuyabiliyorum",
        "bu dünyadan gitmek istiyorum",
        "dayanacak gücüm yok",
        "artık dayanacak gücüm yok",
    ],
    "dermatology": [
        "ayak parmaklarımın arasında kaşıntılı",
        "ayakta soyulan döküntü",
        "havuza gittikten sonra",
        "atlet ayağı",
        "ayak mantarı",
        "gümüş beyaz kepekli plaklar",
        "dirseklerim gümüş kepekli",
        "saçlı derimde kepekli plaklar",
        "psoriasis",
        "sedef hastalığı",
    ],
    "ent": [
        "yüzümde basınç",
        "alın ve yanak bölgelerinde basınç",
        "burnum tıkalı ve akıyor",
        "sinüzit",
        "bademciklerim şiş",
        "bademciklerim beyaz lekeli",
        "tonsillit",
        "yutkunamıyorum ateş",
        "kulak kanalım ağrıyor",
        "kulakta akıntı kaşıntı",
        "yüzerken kulağıma su kaçtı",
        "dış kulak iltihabı",
    ],
    "pediatrics": [
        "3 yaşındaki kızım ishalde",
        "2 yaşındaki oğlum ishal",
        "günde 5-6 kez sulu ishal",
        "3 yaşındaki ishal ateş",
        "4 yaşındaki kırmızı noktalar",
        "4 yaşındaki oğlumun vücudunda kırmızı noktalar",
        "boynunda bez var ateşi",
    ],
    "obgyn": [
        "adetim gecikti test pozitif",
        "gebeyim ilk kontrol",
        "gebelik takibi",
        "ilk prenatal kontrol",
        "sıcak basması gece terlemesi",
        "6 aydır adet görmedim",
        "50 yaşında adet yok",
        "menopoz dönemi",
    ],
    "ophthalmology": [
        "görüşüm yavaş yavaş bulanıklaştı",
        "geceleri farlar etrafında kamaşma",
        "kataract",
        "yaş bağlı görme azalması",
        "göz kapağımda ağrılı kırmızı şişlik",
        "göz kapağı sivilce gibi",
        "arpacık göz",
    ],
}


def _append(dest: list, items: list) -> int:
    existing = {str(x).strip().lower() for x in dest}
    added = 0
    for it in items:
        key = str(it).strip().lower()
        if key and key not in existing:
            dest.append(it)
            existing.add(key)
            added += 1
    return added


def main() -> int:
    # Synonyms
    syn = json.loads(SYN.read_text(encoding="utf-8"))
    by_canonical = {s["canonical"]: s for s in syn["synonyms"]}
    var_adds = 0
    for canonical, variants in SYNONYM_VARIANTS.items():
        if not variants:
            continue
        entry = by_canonical.get(canonical)
        if entry is None:
            print(f"WARN: canonical not found: {canonical!r}", file=sys.stderr)
            continue
        var_adds += _append(entry.setdefault("variants_tr", []), variants)
    can_adds = 0
    for nc in NEW_CANONICALS:
        if nc["canonical"] not in by_canonical:
            syn["synonyms"].append(nc)
            by_canonical[nc["canonical"]] = nc
            can_adds += 1
    SYN.write_text(json.dumps(syn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Specialty keywords
    kw = json.loads(KW.read_text(encoding="utf-8"))
    kw_adds = 0
    for s in kw["specialties"]:
        sid = s.get("id")
        if sid in SPECIALTY_KEYWORDS:
            kw_adds += _append(s.setdefault("keywords_tr", []), SPECIALTY_KEYWORDS[sid])
    KW.write_text(json.dumps(kw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Done. +{var_adds} synonym variants, +{can_adds} new canonicals, "
        f"+{kw_adds} specialty keywords."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
