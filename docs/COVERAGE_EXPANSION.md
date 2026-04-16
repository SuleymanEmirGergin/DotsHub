# Coverage Expansion — Stream A

> **Status:** Skeleton. Her session tamamlandığında bu dosya güncellenir.
> **Baseline audit:** `docs/medical/coverage_audit.md` (A1 session çıktısı).
> **Machine-readable baseline:** `backend/scripts/coverage_expected.json`.
> **Progress tracker:** `python backend/scripts/audit_coverage.py`.
> **Parallel stream:** `docs/LLM_INTEGRATION.md` (Stream B).

---

## 1. Amaç

Medikal veri kapsamını Türkiye birinci basamak profiline uygun hale
getirmek: **32 → 72+ canonical, 41 → 90 disease, 11 → 14 specialty
(hepsi aktif), 0 → 14+ same-day rule, 7 → 25+ golden flow**.

Stream B (LLM NLU) ile paralel çalışır — Stream A veriyi zenginleştirir,
Stream B o veriyi daha iyi kullanır.

---

## 2. Hedefler

A1 session'ın ölçümlediği baseline → hedef tablosu:

| Boyut | Baseline | Hedef | Δ |
|---|---:|---:|---:|
| Canonical symptom | 32 | 72+ | +40 |
| Variant / canonical (avg) | 4.0 | 15–25 | 3.7×–6.2× |
| Variant total | 128 | 1450+ | 11.3× |
| Specialty (aktif) | 8 | 14 | +3 orphan + 3 yeni |
| Disease mapping | 41 | ~90 | +49 |
| Emergency rule | 13 | 24+ | +11 |
| Same-day rule | **0** | 14+ | +14 |
| Red-flag soru | 4 | 17+ | +13 |
| Golden flow senaryo | 7 | 25+ | +18 |

Tam detay: `docs/medical/coverage_audit.md`.

Kritik bulgular (A1):

1. `config/sameday_rules.json` **tamamen boş** — same-day filtresi
   fiilen inaktif.
2. `disease_to_specialty.json` `internal_gi` listesi Kaggle kökenli
   (Malaria, Dengue, AIDS, Hepatitis B/C/D/E, Typhoid) — Türkiye
   birinci basamak profili dışı.
3. **3 orphan specialty**: psychiatry, obgyn, ophthalmology — keyword
   var, disease_id yok.
4. **3 missing specialty**: pediatrics, nephrology, endocrinology,
   general_surgery — hiç specialty_id yok.
5. `"Paralysis (brain hemorrhage)"` gibi agresif tanı label'ları
   kullanıcıya sızabiliyor (A9 confidence gate ile çözüldü,
   commit `dcf1529`).

---

## 3. Session Listesi ve Durum

| Session | Scope | Yeni canonical | Yeni disease | Rule | Red-flag | Golden flow | Durum |
|---|---|---:|---:|---:|---:|---:|---|
| **A1** | Coverage audit baseline | — | — | — | — | — | ✅ Done — `docs/medical/coverage_audit.md` |
| **A9** | Confidence gate | — | — | — | — | — | ✅ Done — commit `dcf1529` |
| **A7 collision test** | `test_synonym_collisions.py` — 14 test (data hygiene, collision, expansion guard, matcher sanity) | — | — | — | — | — | ✅ Done |
| A2 | Psikiyatri | 8 | 12 | 1 | 4 | 3 | Pending |
| A3 | OB-GYN | 10 | 13 (+1 cross) | 3 | 3 | 3 | Pending |
| A4 | Oftalmoloji | 6 | 10 | 2 | 2 | 3 | Pending |
| A5 | Pediatri | 8 | 14 | 3 | 4 | 4 | Pending |
| A6 | Nefro + Endo + Gen Surg | 8 | 14 (+2 taşıma) | 3 | — | 4 | Pending |
| A7 | Variant expansion (generator) | 0 (genişletme) | — | — | — | — | Pending |
| A8 | Sameday rules + audit | — | — | — | — | — | Pending |
| A10 | Disease list revizyonu | — | ~-10/+15 | — | — | 2 | Pending |
| A10b | Golden flows ek | — | — | — | — | +18 (toplam 25+) | Pending |
| A11 | UI full-stack yansıma | — | — | — | — | — | Pending |

**Hedef toplam:** +40 canonical, +63 disease (net +49), +12 emergency
rule, +13 red-flag soru, +20 golden flow senaryosu.

---

## 4. Öncelik Sıralaması (A1 matrisi)

A1'deki pazarlama/impact analizine göre:

1. **A9** (confidence gate) — altyapı sigortası ✅
2. **A7 collision test** — `test_synonym_collisions.py` variant
   expansion güvenliği için ✅
3. **A2** (psikiyatri) — yüksek hacim, stigma'yı azaltır
4. **A3** (OB-GYN) — ektopik gebelik + preeklampsi kritik emergency
5. **A4** (oftalmoloji) — ani görme kaybı emergency
6. **A5** (pediatri) — yüksek hacim, yaş bucket altyapısı
7. **A6** (genel cerrahi + nefro + endo) — akut apandisit + DKA
8. **A10** (disease list revizyonu) — Malaria/Dengue/AIDS temizlik
9. **A7** (variant expansion generator) — recall iyileştirmesi
10. **A8** (sameday + rules audit) — expert review tetikleyici
11. **A10b** (golden flows) — regresyon kalkanı
12. **A11** (UI full-stack) — backend bittiğinde

---

## 5. İş Akışı

Her session şu sırayla:

```
1. Session planı (medikal gap listesi + ICD-10 eşleme)
   ↓
2. Data değişiklikleri:
   - synonyms_tr.json: yeni canonical + 15-25 varyant her biri
   - disease_to_specialty.json: yeni hastalıklar + specialty_id
   - specialty_keywords_tr.json: branş keywords_tr
   - kaggle_cache/kaggle_to_canonical.json: mapping güncelleme
   - config/emergency_rules.json: yeni kurallar (varsa)
   - red_flag_questions.json: yeni sorular (varsa)
   ↓
3. Golden flow testleri (her branş için 2-3 senaryo)
   ↓
4. Audit script doğrulama:
   python backend/scripts/audit_coverage.py
   ↓
5. Test suite:
   cd backend && python -m pytest --tb=short -q
   ↓
6. Commit
```

---

## 6. Progress Tracker

Her commit sonrası:

```bash
python backend/scripts/audit_coverage.py --json > progress.json
```

JSON output'u `progress.<session_id>.json` olarak saklanabilir →
trend analizi için.

CI otomatik (`.github/workflows/audit-coverage.yml`):
- PR: kritik gap varsa build fail
- main: rapor + artifact
- Pazartesi 06:17 UTC: haftalık snapshot

### Güncel Durum (2026-04-16)

```
canonicals             current=32    baseline=32  target=72 (44.4%)
variants_total         current=128   baseline=131 target=1450 (8.8%)
diseases               current=41    baseline=41  target=90 (45.6%)
emergency_rules        current=7     target=24
sameday_rules          current=0     target=14    ⚠ EMPTY STUB
red_flag_questions     current=4     target=17
golden_flows           current=7     target=25
orphan_specialties     ['obgyn', 'ophthalmology', 'psychiatry']  target: 0
```

---

## 7. Expert Review Kapısı

A1'den kalan 7 açık tıp sorusu (uzman review'da yanıtlanacak):

1. Ektopik gebelik pretriage hassasiyeti (amenore + pelvik ağrı +
   kanama → ER_NOW; ayrıca pozitif gebelik testi şart mı?)
2. Pediatrik ateş eşiği: NICE vs AAP (<3 ay ≥38°C?)
3. Aktif intihar planı trigger specificity (method + timeframe?)
4. DKA vs HHS (T1DM vs T2DM ayrımı)
5. Confidence threshold 0.35 vs 0.45 — klinik literatür desteği?
6. Hepatit A çocuk branşına özel mi kalsın?
7. Somatizasyon vs fibromiyalji → psychiatry vs orthopedics_rheum?

A8 session'da tıp expert review dokümanı oluşturulacak
(`docs/medical/expert_review_v1.md`).

---

## 8. Risks ve Mitigation (A1 analizi)

| Session | Risk | Mitigation |
|---|---|---|
| A2 | Panik semptomları kardiyak false-positive yaratır | A9 gate + psychiatric_emergency yalnız explicit plan için ER |
| A3 | Ektopik gebelik false-negative | Red-flag soru "amenore + şiddetli pelvik ağrı" ER_NOW zinciri |
| A4 | Glokom krizi bulantıyla confound olur | `acute_glaucoma` require_all: tek-taraflı göz ağrısı + bulanık görme |
| A5 | Yetişkin akışı bozulur | `_age_bucket` default "adult"; pediatri routing yalnız age verilirse |
| A6 | DKA vs hipoglisemi confound | Kural ayrımı: polidipsi+Kussmaul vs terleme+titreme+DM öyküsü |
| A7 | Variant collision (aynı varyant 2 canonical'a) | Collision test CI-gate, longest-first match |
| A8 | Same-day false-positive kullanıcıyı gereksiz hastaneye yönlendirir | Expert review + golden flow edge-case |
| A10 | Disease label değişikliği LLM output'unu bozar (Stream B ile sync) | `disease_to_specialty.json` tek kaynak; Stream B schema validate |

---

## 9. İlgili Dokümanlar

- `docs/medical/coverage_audit.md` — A1 tam baseline
- `docs/LLM_INTEGRATION.md` — Stream B (paralel)
- `docs/ARCHITECTURE.md` → "Triage Pipeline"
- `docs/KAGGLE_INGEST_AUTOMATION.md` — Kaggle veri pipeline
- `docs/VERI_KALITE.md` — veri kalitesi ölçümü
- `backend/scripts/audit_coverage.py` — progress tracker
- `backend/scripts/coverage_expected.json` — A1 hedef JSON
