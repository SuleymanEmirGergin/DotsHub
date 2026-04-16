# Expert Review v1 — Dotshub Triage Draft Content

> **Review Status:** Draft — pending medical expert review
> **Prepared:** 2026-04-17
> **Scope:** Stream A sessions A2, A3, A4, A6, A10 + A8 sameday rules
> **Baseline reference:** `docs/medical/coverage_audit.md` (A1 baseline)

---

## 0. Amaç

A1 baseline audit sonrası Stream A expansion session'larında eklenen **tüm
medikal içerik** bir hekim tarafından gözden geçirilmek üzere bu dokümanda
toplanmıştır. Her entry `"review_status": "draft"` metadata alanıyla
işaretlenmiştir; review sonrası hekim tarafından `"reviewed"` veya
`"revised"` olarak güncellenir.

Dotshub'ın temel ilkeleri (`README.md`):
- Tanı koymaz, pretriage yönlendirme yapar
- Safety-first: ER_NOW triggers kaçırılmamalı (sensitivity > specificity)
- Deterministik + açıklanabilir (LLM karar vermez, sadece çevirmen)

---

## 1. İçerik Özeti

Mevcut durum (A10 + A6 sonrası, A8 öncesi bazen → A8 bitince güncellenmeli):

| Boyut | Baseline (A1) | Mevcut | Change |
|---|---:|---:|---:|
| Canonical symptom | 32 | 66 | +34 |
| Variant (total) | 131 | ~590 | ~+460 |
| Specialty (active) | 8 (3 orphan, 3 missing) | 14 (0 orphan, 0 missing) | +3 |
| Disease mapping | 41 | 90 | +49 (net), +62 added, 13 removed |
| Emergency rule (hard_triggers) | 13 | 19 | +6 |
| Same-day rule | 0 (empty stub) | 13 | +13 (A8) |
| Red-flag question | 4 | 13 | +9 |
| Golden flow | 7 | 20 | +13 |

Tüm yeni entry'ler metadata'da `"review_status": "draft"` işaretlidir ve bu
doküman review'ı tetikler.

---

## 2. Draft İçeriğin Dağılımı (hekim review'ı için)

### 2.1 Psikiyatri (A2 — commit `66b2b95`)

**Canonicals:** uyku bozukluğu, düşük ruh hali, anksiyete, panik atak,
iştah kaybı, konsantrasyon bozukluğu, sosyal izolasyon, umutsuzluk

**Diseases (12):** Majör depresyon, Yaygın anksiyete bozukluğu, Panik
bozukluk, Obsesif kompulsif bozukluk, Travma sonrası stres bozukluğu,
Bipolar bozukluk, Sosyal fobi, İnsomnia, Somatizasyon bozukluğu, Uyum
bozukluğu, Postpartum depresyon, Erken psikoz

**Emergency rule:** `psychiatric_emergency_active_plan` — aktif intihar
planı (yöntem + zaman + araç hazırlığı) → ER_NOW

**Red-flag questions:** active suicide plan, harm to others, psychosis
(hallucinations), depression duration ≥2 weeks

**Golden flows:** psychiatry_depression_chronic, psychiatry_panic_attack,
psychiatry_active_suicidal_plan

### 2.2 OB-GYN (A3 — commit `ef4444c`)

**Canonicals:** vajinal kanama, gecikmiş adet, pelvik ağrı, adet
düzensizliği, dismenore, gebelik şüphesi, meme ağrısı, vajinal akıntı,
vajinal kaşıntı, amenore

**Diseases (13):** Dismenore, Polikistik over sendromu, Endometriosis,
Myoma uteri, Ovaryan kist, Menopoz, Vajinit, Pelvik inflamatuar hastalık,
Normal gebelik, Abortus imminens, **Ektopik gebelik (ACIL)**,
**Preeklampsi (ACIL)**, İnkontinans

**Emergency rules:** `ectopic_pregnancy_suspect`, `preeclampsia_severe`,
`postpartum_hemorrhage`

**Red-flag questions:** pregnancy bleeding + pain, preeclampsia warning,
postpartum hemorrhage

**Golden flows:** obgyn_dysmenorrhea, obgyn_suspected_ectopic, obgyn_pcos_irregular

### 2.3 Oftalmoloji (A4 — commit `f2099a6`)

**Canonicals:** ani görme kaybı, fotofobi, kızarık göz, göz ağrısı,
çift görme, göz sulanma

**Diseases (10):** Viral/Bakteriyel/Allerjik konjonktivit (3 ayrı),
**Akut glokom (ACIL)**, **Retina dekolmanı (ACIL)**, Katarakt, Kuru göz,
Kornea yaralanması, Blefarit, Arpacık

**Emergency rules:** `acute_glaucoma_suspect` (GI false-positive guard:
göz bulgusu + bulanık görme zorunlu), `retinal_detachment_suspect`

**Red-flag questions:** diplopia + trauma, sudden vision loss ≤24h

**Golden flows:** ophth_conjunctivitis, ophth_acute_glaucoma, ophth_sudden_vision_loss

### 2.4 Nefroloji + Endokrinoloji + Genel Cerrahi (A6 — commit `66b2b95` veya sonrası)

**Yeni specialty_id'ler:** nephrology, endocrinology, general_surgery

**Canonicals:** yan ağrısı, hematüri, idrarda köpük, aşırı susama,
poliüri, hipoglisemi belirtisi, ani karın ağrısı, kasık fıtığı

**Diseases (13):**
- Nefroloji: Renal kolik, Akut piyelonefrit, Kronik böbrek yetmezliği,
  Nefrotik sendrom
- Endokrinoloji: T1DM yeni tanı, T2DM, **DKA (ACIL)**, **Ağır hipoglisemi
  (ACIL)**, Cushing sendromu şüphesi
- Genel Cerrahi: **Akut apandisit (ACIL)**, Akut kolesistit, Kasık fıtığı
  (elektif), Akut intestinal tıkanma

**Disease transfers (A6):**
- Hypothyroidism: internal_gi → endocrinology
- Hyperthyroidism: internal_gi → endocrinology
- Dimorphic hemmorhoids(piles) → general_surgery (+ A10'da "Hemoroid"
  olarak yeniden adlandırıldı)

**Emergency rules:** `dka_suspect`, `severe_hypoglycemia`,
`acute_appendicitis_suspect`

**Golden flows:** nephro_renal_colic, endo_new_dka, surg_acute_appendicitis,
endo_t2dm_follow_up

### 2.5 A10 Disease List Revizyonu (commit bekleniyor)

**Çıkarılanlar (9 + 2 = 11):** Malaria, Dengue, Typhoid, AIDS, Hepatitis
B/C/D/E, Alcoholic hepatitis, Diabetes (trailing-space duplicate),
Hypoglycemia (A6'da "Ağır hipoglisemi" olarak güncellenmiş şekilde mevcut)

**Etiket düzeltmeleri:**
- "Hypertension " (trailing space) → "Hipertansiyon (stabil)"
- "Osteoarthristis" (typo) → "Osteoartrit"
- "Paralysis (brain hemorrhage)" (agresif) → "İnme/SVH şüphesi"
- "Dimorphic hemmorhoids(piles)" → "Hemoroid"

**Eklenenler (12, yüksek-impact):** Mevsimsel grip, COVID-19 akut,
Allerjik rinit, Gerilim tipi baş ağrısı, İrritabl bağırsak sendromu,
Akut otitis media (yetişkin), Akut sinüzit, Akut farenjit, Lomber disk
hernisi, Mekanik bel ağrısı, Benign prostat hiperplazisi, Kalp yetmezliği
(kronik)

**Yeni canonicals (2):** bel ağrısı, kulak ağrısı

### 2.6 A8 Same-day Rules (commit bekleniyor)

13 kural (`config/sameday_rules.json`), hepsi `action: SAME_DAY`:

1. persistent_fever_3d — ateş ≥3 gün
2. cough_with_bloody_sputum_non_emergency — tek episode kanlı balgam
3. postmenopausal_bleeding — menopoz + kanama
4. diabetic_persistent_high_bs — DM + şekerim 3 gündür yüksek
5. moderate_depression_2w — düşük ruh hali ≥2 hafta
6. acute_otitis_suspect_adult — kulak ağrısı + ateş (yetişkin)
7. moderate_dehydration — ishal + az idrar + halsizlik
8. herpes_zoster_suspect — tek taraflı döküntü + yanma
9. acute_sinusitis_severe — yüz ağrısı + ≥7 gün pürülan akıntı
10. new_onset_hypertension — ölçülmüş TA ≥160/100
11. severe_back_pain_non_trauma — bel ağrısı ≥7 gün + dayanılmaz
12. persistent_headache_escalating — baş ağrısı ≥3 gün + şiddetlenen
13. moderate_asthma_exacerbation — astım + nefes darlığı (ER kriteri yok)

**Not (KRİTİK):** Bu kurallar şu an **production pipeline'a bağlı değil**.
`safety_guard_check` sadece `rules.json` hard_triggers'ı okuyor. Sameday
kuralları aktif olmak için ya `triage_engine` entegrasyonu ya da Stream B
LLM NLU tarafından duration/severity extraction gerekir.

---

## 3. Açık Medikal Sorular (A1 section 9)

Hekim review'ında karara bağlanması gereken 7 açık soru:

### 3.1 Ektopik gebelik pretriage hassasiyeti

"Amenore + pelvik ağrı + vajinal kanama" üçlüsü ER_NOW için yeterli mi,
yoksa ayrıca pozitif gebelik testi anchor'ı istenmeli mi?

**Mevcut karar:** Gebelik testi şartı YOK (missed ectopic = ölüm; false
positive = acil servis ziyareti kabul edilebilir maliyet).

**Hekim değerlendirmesi:** ☐ Onay / ☐ Revize et / ☐ Reddet

### 3.2 Pediatrik ateş eşiği — NICE vs AAP

<3 ay ≥38°C ER_NOW için baseline rehber hangisi olmalı? (AAP: 90 gün altı
rektal ≥38°C)

**Mevcut durum:** Pediatri A5'e ertelendi — karar verilmedi.

**Hekim değerlendirmesi:** ☐ AAP rehberi / ☐ NICE rehberi / ☐ Türkiye ulusal protokol

### 3.3 Aktif intihar planı — trigger specificity

"Plan yaptım" keyword'ü yeterli trigger mi, yoksa method specificity
(ilaç/ip/silah) + timeframe (bugün/bu hafta) sorulmalı mı?

**Mevcut karar:** İki seviye:
- Hard trigger: plan/yöntem açık ifade → EMERGENCY hemen
- Belirsiz düşünce → red-flag question zinciri ile specificity

**Hekim değerlendirmesi:** ☐ Onay / ☐ Revize et / ☐ Reddet

### 3.4 DKA vs HHS — T1DM / T2DM ayrımı

T2DM'de HHS (hiperozmolar hiperglisemik sendrom) daha sık. Mevcut DKA
trigger'ımız T1DM + T2DM ayrımı yapmıyor — genel hiperglisemik acil
ele alıyor.

**Mevcut karar:** Tek `dka_suspect` rule. HHS ayrı rule gerekli mi?

**Hekim değerlendirmesi:** ☐ Yeterli / ☐ HHS ayrı rule ekle / ☐ Revize et

### 3.5 Confidence threshold 0.45 — klinik literatür?

Confidence gate (Opsiyon 1, commit `dcf1529`) mevcut threshold: 0.45.
Klinik karar destek literatüründe optimal cut-off önerisi var mı? A/B
test ile validate edilebilir mi?

**Hekim değerlendirmesi:** ☐ 0.45 uygun / ☐ Farklı threshold öner / ☐ Literatür referansı

### 3.6 Hepatit A — sadece çocuk branşında mı tutulmalı?

Okul/kreş salgınları için mantıklı ama yetişkin akışında düşük prior.
A10'da kaldı; sadece pediatri (A5) kapsamına mı taşınmalı?

**Hekim değerlendirmesi:** ☐ Genel kalsın / ☐ Sadece pediatri

### 3.7 Somatizasyon bozukluğu vs fibromiyalji — primary specialty?

Her ikisi de multifokal ağrı + normal lab → psychiatry mi,
orthopedics_rheum mi öncelikli routing?

**Mevcut karar:** Somatizasyon → psychiatry (A2'de); fibromiyalji henüz
disease listesinde yok.

**Hekim değerlendirmesi:** ☐ Onay / ☐ Revize et (fibromiyalji ekle)

---

## 4. Review Checklist (her specialty için)

Hekim review'ı sırasında kontrol edilecek kalemler:

### Per-specialty checklist

- ☐ **Canonical'lar klinik olarak anlamlı mı?**
  - Symptom'lar Türk hastaların gerçekten kullandığı terminoloji mi?
  - Variants yeterli aralıkta mı (akademik + günlük dil)?
- ☐ **Disease mapping doğru specialty'ye gidiyor mu?**
  - Cross-specialty overlap (ör. ENT ↔ pulmonology: rinit) netlik kazandı mı?
- ☐ **Emergency trigger'lar yanlış pozitif vermiyor mu?**
  - Bulantı → GI yanlış yönlendirmesi yok (glokom vakası)
  - Generic "kanama" → postpartum'u yakalarken normal menstrüeli yakalamıyor
- ☐ **Red-flag sorular klinik doğrusu mu?**
  - Yes/no yanıtı direkt ER_NOW'a götürüyor mu?
  - Escalation threshold'u doğru mu?
- ☐ **Same-day rule koşulları makul mu?**
  - Duration/frequency parametreleri (3d, 2w, 7d) klinik olarak uygun mu?
- ☐ **Hiçbir KRİTİK emergency kaçırılmamış mı?**
  - Örn: CVA (stroke), MI, anafilaksi, meninjit zaten var mı?

### Per-specialty sign-off

| Specialty | Hekim | Tarih | Status |
|---|---|---|---|
| Psychiatry | | | ☐ |
| OB-GYN | | | ☐ |
| Ophthalmology | | | ☐ |
| Nephrology | | | ☐ |
| Endocrinology | | | ☐ |
| General Surgery | | | ☐ |
| Same-day rules | | | ☐ |

---

## 5. Review Bulguları Uygulama Akışı

Hekim review tamamlandıktan sonra:

1. Her `review_status: draft` entry için → `reviewed` veya `revised`
   güncellemesi yapılır
2. Reddedilen entry'ler çıkarılır (commit mesajında sebep belirtilir)
3. Açık sorular (section 3) için kararlar `A8b — Post-review revisions`
   session'ında uygulanır
4. Golden flow'lar revised entry'lere göre güncellenir
5. `expert_review_v1.md` → `expert_review_v1_resolved.md` olarak
   archive'a alınır, v2 taslağı başlar

---

## 6. İlgili Dokümanlar

- `docs/medical/coverage_audit.md` — A1 baseline audit (kritik referans)
- `docs/COVERAGE_EXPANSION.md` — Stream A genel plan + ilerleme takibi
- `docs/ARCHITECTURE.md` → "Triage Pipeline" (deterministik akış)
- `docs/LLM_INTEGRATION.md` — Stream B planı (LLM NLU katmanı)
- `backend/scripts/audit_coverage.py` — canlı kapsam raporu (`python
  backend/scripts/audit_coverage.py`)

---

## 7. İletişim

Review sırasında sorular için proje sahibi + A1 session planlayıcısına
erişim. Sensitive medikal kararlar için birden fazla uzman görüşü tercih
edilir (özellikle obgyn ektopik gebelik, pediatri ateş eşiği, psychiatry
intihar planı trigger'ı).
