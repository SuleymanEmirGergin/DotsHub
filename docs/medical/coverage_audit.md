# Medical Coverage Audit — Stream A Baseline

> **Purpose:** Stream A Session A1 çıktısı. Mevcut medikal kapsamı sayısallaştırır ve A2-A10'un iş hedeflerini sabitler.
> **Scope source:** Repo worktree `cool-matsumoto`, commit üzerinden tarama (backend/app/data/*, config/*, tests/golden_flows/*).
> **Review status:** Draft — tıp profesyoneli review için A8 expert_review_v1.md ile birlikte gönderilecek.

---

## 1. Özet (TL;DR)

| Boyut | Mevcut | Hedef (Stream A sonu) | Δ |
|---|---:|---:|---:|
| Canonical symptom sayısı | 32 | 72+ | +40 |
| Ortalama TR variant / canonical | ~4.0 | 15–25 | 3.7×–6.2× |
| Specialty ID sayısı | 11 (3'ü iskelet) | 14 (hepsi aktif) | +3 |
| Disease → specialty map girdisi | 41 | ~90 (Türkiye profili) | +49 (ve full revizyon) |
| Emergency rule sayısı | 13 | 24+ | +11 |
| Same-day rule sayısı | **0** (boş stub) | 14+ | +14 |
| Red-flag soru sayısı | 4 | 17+ | +13 |
| Golden flow senaryo sayısı | 7 | 25+ | +18 |
| Confidence gate (top_conditions suppression) | YOK | 0.35 threshold | +1 mekanizma |

**Kritik bulgular:**
1. `config/sameday_rules.json` tamamen boş — same-day triage filtresi fiilen inaktif.
2. `disease_to_specialty.json` içindeki `internal_gi` listesi Kaggle kökenli (Malaria, Dengue, AIDS, Hepatitis B/C/D/E, Typhoid) ve Türkiye birinci basamak profiline uymuyor.
3. Psychiatry, OB-GYN, Ophthalmology için specialty_id tanımlı ama **disease listesi sıfır** → UI'da bu branşları tavsiye etmek için deterministik yol yok, sadece keyword skoru.
4. Pediatri, Nefroloji, Genel Cerrahi specialty_id'leri **hiç yok**.
5. `"Paralysis (brain hemorrhage)"` ve `"Heart attack"` gibi ağır tanılar düşük güven durumunda bile `top_conditions`'a sızabiliyor (A9 gate yok).

---

## 2. Canonical × Specialty Heatmap

### 2.1 Mevcut canonical envanteri (32 adet, `backend/app/data/synonyms_tr.json`)

Düşük-variant canonical'lar **kalın** işaretli (≤4 variant — A7 hedefi):

| # | Canonical | Type | Variant | Line |
|---|---|---|---:|---:|
| 1 | baş dönmesi | symptom | 6 | 13 |
| 2 | bulantı | symptom | **4** | 25 |
| 3 | kusma | symptom | **4** | 35 |
| 4 | ishal | symptom | **4** | 45 |
| 5 | kabızlık | symptom | **3** | 55 |
| 6 | göğüs ağrısı | symptom | **3** | 64 |
| 7 | göğüste baskı | symptom | **3** | 73 |
| 8 | nefes darlığı | symptom | 11 | 82 |
| 9 | çarpıntı | symptom | **3** | 99 |
| 10 | ateş | symptom | **4** | 108 |
| 11 | boğaz ağrısı | symptom | **3** | 118 |
| 12 | öksürük | symptom | 7 | 127 |
| 13 | baş ağrısı | symptom | 6 | 140 |
| 14 | tek taraflı güçsüzlük/uyuşma | red_flag | **4** | 152 |
| 15 | konuşma bozukluğu | red_flag | **3** | 162 |
| 16 | idrar yanması | symptom | **3** | 171 |
| 17 | döküntü/ürtiker | symptom | **4** | 180 |
| 18 | yüz/dudak şişmesi | red_flag | **3** | 190 |
| 19 | intihar/kendine zarar | red_flag | **3** | 199 |
| 20 | sık idrara çıkma | symptom | **4** | 208 |
| 21 | kaşıntı | symptom | **3** | 218 |
| 22 | kızarıklık | symptom | **3** | 227 |
| 23 | sivilce | symptom | **3** | 236 |
| 24 | leke | symptom | **3** | 245 |
| 25 | kabarcık | symptom | **3** | 254 |
| 26 | şişlik | symptom | **4** | 263 |
| 27 | eklem tutukluğu | symptom | **3** | 273 |
| 28 | anal ağrı | symptom | **3** | 282 |
| 29 | kanlı balgam | red_flag | **3** | 291 |
| 30 | karın ağrısı | symptom | 5 | 300 |
| 31 | balgam | symptom | 5 | 311 |
| 32 | halsizlik | symptom | 5 | 322 |

**Özet:** 24/32 canonical (%75) ≤4 variant. Toplam mevcut ~131 variant. Stream A sonu hedef: **~1450+ variant**.

### 2.2 Heatmap — hangi canonical hangi specialty'ye puanlıyor

`specialty_keywords_tr.json` keyword listelerinden derlenmiştir. Hücre = "canonical ∈ specialty.keywords_tr (veya yakın variant ∈ keywords_tr)".

| Canonical ↓ / Specialty → | ent | pulm | cardio | neuro | int_gi | uro | derm | ophth | ortho | psych | obgyn |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| baş dönmesi | | | | ✓ | | | | | | | |
| bulantı | | | | | ✓ | | | | | | |
| kusma | | | | | ✓ | | | | | | |
| ishal | | | | | ✓ | | | | | | |
| kabızlık | | | | | ✓ | | | | | | |
| göğüs ağrısı | (neg) | (neg) | ✓ | | | | | | | | |
| göğüste baskı | | (neg) | ✓ | | | | | | | | |
| nefes darlığı | | ✓ | | | | | | | | | |
| çarpıntı | | | ✓ | | | | | | | | |
| ateş | | | | | (partial)¹ | | | | | | |
| boğaz ağrısı | ✓ | | | | | | | | | | |
| öksürük | | ✓ | | | | | | | | | |
| baş ağrısı | | | | ✓ | | | | | | | |
| tek taraflı güçsüzlük/uyuşma | | | | ✓ | | | | | | | |
| konuşma bozukluğu | | | | ✓ | | | | | | | |
| idrar yanması | | | | | | ✓ | | | | | |
| döküntü/ürtiker | | | | | | | ✓ | | | | |
| yüz/dudak şişmesi | | (neg) | | | | | ✓ | | | | |
| intihar/kendine zarar | | | | | | | | | | (indirect)² | |
| sık idrara çıkma | | | | | | ✓ | | | | | |
| kaşıntı | | | | | | | ✓ | | | | |
| kızarıklık | | | | | | | ✓ | | | | |
| sivilce | | | | | | | ✓ | | | | |
| leke | | | | | | | ✓ | | | | |
| kabarcık | | | | | | | ✓ | | | | |
| şişlik | | | | | | | | | ✓ | | |
| eklem tutukluğu | | | | | | | | | ✓ | | |
| anal ağrı | | | | | ✓ | | | | | | |
| kanlı balgam | | ✓ | | | | | | | | | |
| karın ağrısı | | | | | ✓ | | | | | | |
| balgam | | ✓ | | | | | | | | | |
| halsizlik | | | | | | | | | | | |

¹ `ateş` hiçbir specialty `keywords_tr` listesinde literal olarak yok — sadece disease-level eşleşmeyle işleniyor (Common Cold, Pneumonia, Gastroenteritis). Pediatri akışında kritik.
² `intihar/kendine zarar` canonical'ı `rules.json` `red_flags.hard_triggers` içinde var, ama `specialty_keywords_tr.json.psychiatry.keywords_tr` içinde doğrudan anahtar değil — psychiatry skoruna yalnız "panik/anksiyete/depresyon" üzerinden dolaylı katkı.

### 2.3 Boş kalan branşlar — canonical kapsama tablosu

| Specialty | Mevcut canonical kapsama | Eksik canonical (Stream A'da eklenecek) |
|---|---|---|
| psychiatry | 0 canonical — sadece `panik/anksiyete/depresyon/korku` keyword | uyku bozukluğu, düşük ruh hali, anksiyete/endişe (explicit canonical), panik atak, iştah kaybı, konsantrasyon bozukluğu, sosyal izolasyon, umutsuzluk |
| obgyn | 0 canonical — sadece `adet gecikmesi/düzensiz kanama/hamilelik` keyword | vajinal kanama, gecikmiş adet, pelvik ağrı, adet düzensizliği, dismenore, gebelik şüphesi, meme ağrısı/akıntısı, vajinal akıntı, kaşıntı (vajinal), amenore |
| ophthalmology | 0 canonical — sadece `göz kızarıklığı/ağrısı/batma/ışığa hassasiyet` keyword | ani görme kaybı, fotofobi (explicit), kızarık göz (explicit canonical), göz ağrısı (explicit), çift görme/diplopi, göz kaşıntısı/sulanma |
| pediatrics | **YOK** (specialty_id yok) | bebek huzursuzluğu, beslenmeyi reddetme, döküntü+ateş, yüksek ateş (çocuk), ağlamada değişiklik, ishal+dehidratasyon, kulak çekiştirme, nefes hırıltısı (bebek) |
| nephrology | **YOK** | yan ağrısı (renal kolik), hematüri, idrarda köpük |
| endocrinology | **YOK** (internal_gi'ye gömülü) | aşırı susama/polidipsi, poliüri, hipoglisemi belirtisi (terleme+titreme) |
| general_surgery | **YOK** (internal_gi fallback) | ani karın ağrısı (sağ alt), kasık fıtığı şişlik |

---

## 3. Disease → Specialty Map — Mevcut 41 Girdinin Analizi

### 3.1 Specialty dağılımı

| Specialty ID | Girdi sayısı | Girdi örnekleri |
|---|---:|---|
| `internal_gi` | 20 | GERD, Chronic cholestasis, PUD, **AIDS**, Diabetes, Gastroenteritis, Jaundice, **Malaria**, **Dengue**, **Typhoid**, hepatitis A, **Hepatitis B/C/D/E**, **Alcoholic hepatitis**, Piles, Hypothyroidism, Hyperthyroidism, Hypoglycemia |
| `dermatology` | 7 | Fungal infection, Allergy, Drug Reaction, Chicken pox, Acne, Psoriasis, **Impetigo** |
| `pulmonology` | 3 | Bronchial Asthma, Tuberculosis, Pneumonia |
| `cardiology` | 3 | Hypertension, **Heart attack**, Varicose veins |
| `neurology` | 3 | Migraine, **Paralysis (brain hemorrhage)**, BPPV |
| `orthopedics_rheum` | 3 | Cervical spondylosis, Osteoarthritis, Arthritis |
| `ent` | 1 | Common Cold |
| `urology_internal` | 1 | Urinary tract infection |
| `psychiatry` | **0** | — |
| `obgyn` | **0** | — |
| `ophthalmology` | **0** | — |

**Kalın** işaretli girdiler A10 (disease list revizyonu) tarafından **çıkarılacak** veya başka specialty_id'ye taşınacak (Türkiye birinci basamak profili dışı).

### 3.2 Veri kalite sorunları (A10'da düzeltilecek)

| Sorun | Örnek | Etki | A10 aksiyonu |
|---|---|---|---|
| Global/tropik hastalık gürültüsü | Malaria, Dengue, Typhoid | TR kullanıcıya saçma öneri | Listeden çıkar |
| HIV ve hepatit B/C/D/E birinci basamakta primer pretriage vakası değil | AIDS, Hepatitis B-E | Stigma + düşük prior | Listeden çıkar (hep-A salgın potansiyeli için kalır) |
| Agresif tanı label'ı | "Paralysis (brain hemorrhage)" | Düşük güvenle bile UI'da sızıntı | Relabel: "İnme/SVH şüphesi" + A9 confidence gate |
| Alkolik hepatit birinci basamakta nadir | Alcoholic hepatitis | Düşük prior | Çıkar |
| Endokrinoloji `internal_gi` altında | Diabetes, Hypothyroidism, Hyperthyroidism, Hypoglycemia | Karma specialty'ye puanlıyor | A6'da `endocrinology` specialty_id oluşturulunca taşı |
| Hemoroid `internal_gi`'de | Piles (Dimorphic hemmorhoids) | Cerrahi önerisi yanlış specialty | A6'da `general_surgery` altına taşı |
| Label tutarsızlığı | `"Hypertension "` (trailing space), `"Diabetes "`, `"Osteoarthristis"` (typo) | String-match risk | A10'da tüm label'lar normalize edilir |

### 3.3 Türkiye birinci basamak eksik hastalık listesi (A10'da eklenecek)

Kaynaklar: Türkiye Sağlık Bakanlığı birinci basamak istatistikleri (aday), TAHUD en sık görülen tanılar (aday), ICD-10 TR kodlaması.

| Branş | Eksik hastalık (Stream A'da eklenecek) |
|---|---|
| `cardiology` | Stabil hipertansiyon (mevcut ama relabel), Periferik arter hastalığı, Kalp yetmezliği (kronik) |
| `pulmonology` | Mevsimsel grip (influenza), COVID-19 akut, Allerjik rinit, KOAH stabil, Üst solunum yolu enfeksiyonu (mevcut "Common Cold"u buraya taşı) |
| `neurology` | Migren alt-tipleri (auralı/aurasız), Gerilim tipi baş ağrısı, Trigeminal nevralji |
| `internal_gi` (post-cleanup) | GER hastalığı, Fonksiyonel dispepsi, IBS, Akut gastroenterit (bakteri/virüs), Hemoroid → general_surgery'ye taşı |
| `ent` | Akut otitis media (yetişkin), Allerjik rinit, Sinüzit, Farenjit (mevsimsel), Vertigo (BPPV) |
| `dermatology` | Atopik dermatit, Kontakt dermatit, Seboreik dermatit, Tinea pedis, Urtikeria akut |
| `orthopedics_rheum` | Lomber disk/bel ağrısı, Fibromiyalji, Gut artropatisi, Plantar fasiitis, Boyun ağrısı (mekanik) |
| `urology_internal` | Prostatit, BPH (benign prostat), Üretrit |
| `psychiatry` (A2) | Majör depresyon, YAB, Panik bozukluk, OKB, PTSD, Bipolar, Sosyal fobi, İnsomnia, Somatizasyon, Adjustment disorder, Postpartum depresyon, Erken psikoz — **12 yeni** |
| `obgyn` (A3) | Dismenore, PCOS, Endometriosis, Myoma uteri, Ovaryan kist, Menopoz, Vajinit, PID, Normal gebelik, Abortus imminens, **Ektopik gebelik**, **Preeklampsi**, İnkontinans — **13 yeni** + 1 cross-ref (postpartum depresyon) |
| `ophthalmology` (A4) | Viral/Bakteriyel/Allerjik konjonktivit (3 ayrı), **Akut glokom**, **Retina dekolmanı**, Katarakt, Kuru göz, Kornea yaralanması, Blefarit, Arpacık, Üveit — **10 yeni** |
| `pediatrics` (A5) | Akut otitis media (çocuk), Bronşiolit/RSV, Pediatrik pnömoni, Hand-foot-mouth, Kızamıkçık, Suçiçeği, Rotavirüs, **Febril konvülziyon**, Strep boğaz, Adenoid hipertrofi, Pediatrik ÜYE, Atopik dermatit (bebek), Süt alerjisi, Kolik — **14 yeni** |
| `nephrology` (A6) | Renal kolik, Akut piyelonefrit, KBY takip, Nefrotik sendrom — **4 yeni** |
| `endocrinology` (A6) | T1DM yeni tanı, T2DM, **DKA**, **Ağır hipoglisemi**, Hipertiroidi, Hipotiroidi (taşı), Cushing şüphesi — **5 yeni + 2 taşıma** |
| `general_surgery` (A6) | **Akut apandisit**, Kolesistit, Kasık fıtığı, Hemoroid (taşı), Akut tıkanma — **4 yeni + 1 taşıma** |

**Net ekleme:** ~87 yeni/revize girdi, ~8 girdi silinecek → final ~90 girdi (mevcut 41 → 90).

---

## 4. Rules Kapsama Analizi

### 4.1 Emergency rules (`config/emergency_rules.json` — 13 kural)

Mevcut kural ID'leri (evaluator: `backend/app/emergency_router.py:91-166`):

- STROKE_SUSPECT, ACUTE_MI, ANAPHYLAXIS, SEVERE_RESP_DISTRESS, MASSIVE_HEMORRHAGE, SEVERE_ALT_CONSCIOUSNESS, SEIZURE_ACTIVE, DKA_SUSPECT (partial), MENINGITIS_SUSPECT, ACUTE_ABDOMEN (partial), OB_EMERGENCY (placeholder), PSYCHIATRIC_EMERGENCY (placeholder), HEAD_TRAUMA_SEVERE

**Not:** Son 3 kural içerik olarak zayıf (canonical_any listesi boş/kısmi). A2-A5 içinde genişletilecek.

### 4.2 Same-day rules (`config/sameday_rules.json` — **0 kural**)

```json
{"rules": []}
```

Bu kritik bir boşluk. `orchestrator_v5.py:192-200` bu dosyayı okuyor ama hiçbir eşleşme üretemiyor. A8'de doldurulacak. Önerilen ilk 14 kural:

| Rule ID | Tetik | Action |
|---|---|---|
| persistent_fever_3d | ateş ≥3 gün | see_today |
| cough_with_bloody_sputum_non_emergency | kanlı balgam (tek episode) | see_today |
| postmenopausal_bleeding | menopoz + vajinal kanama | see_today |
| diabetic_persistent_high_bs | DM öyküsü + "şekerim yüksek 3 gündür" | see_today |
| moderate_depression_2w | düşük ruh hali + 2 hafta süre | see_today |
| acute_otitis_suspect | kulak ağrısı + ateş (çocuk+yetişkin) | see_today |
| moderate_dehydration | ishal + az idrar + halsizlik | see_today |
| herpes_zoster_suspect | tek taraflı döküntü + yanma | see_today |
| acute_sinusitis_severe | yüz ağrısı + 7+ gün pürülan akıntı | see_today |
| pediatric_prolonged_fever_48h | çocuk + ateş ≥48 saat | see_today |
| new_onset_hypertension | ölçülmüş TA ≥160/100 | see_today |
| severe_back_pain_non_trauma | bel ağrısı + 7+ gün + dayanılmaz | see_today |
| persistent_headache_escalating | baş ağrısı ≥3 gün + şiddetlenen | see_today |
| moderate_asthma_exac | astım öyküsü + nefes darlığı (ER kriteri yok) | see_today |

### 4.3 Red-flag questions (`backend/app/data/red_flag_questions.json` — 4 soru)

Mevcut sorular: chest pain follow-up, headache follow-up, abdominal follow-up, cough follow-up.

**Eksik (A2-A6 boyunca eklenecek):**

| Specialty/trigger | Soru | if_yes_escalate |
|---|---|---|
| psychiatry / self-harm | Aktif intihar planı/yöntem hazırlığı var mı? | ER_NOW |
| psychiatry / self-harm | Başkasına zarar verme düşüncesi var mı? | ER_NOW |
| psychiatry / psychosis | Gerçek olmayan sesler duyuyor musun? | SAME_DAY |
| psychiatry / depression | 2 haftadan uzun mu? | SAME_DAY |
| obgyn / pregnancy_suspect | Gebelikle birlikte vajinal kanama var mı? | ER_NOW |
| obgyn / pregnancy+headache | Gebe misin ve görme bozukluğu var mı? | ER_NOW |
| obgyn / postpartum | Postpartum aşırı kanama (>1 ped/saat)? | ER_NOW |
| ophthalmology / diplopia | Kafa travması sonrası çift görme? | ER_NOW |
| ophthalmology / vision_loss | Ani tek taraflı görme kaybı ≤24 saat? | ER_NOW |
| pediatrics / infant_fever | <3 ay ve ateş ≥38°C? | ER_NOW |
| pediatrics / rash+fever | Petesyal/purpurik döküntü? | ER_NOW |
| pediatrics / lethargy | Şiddetli letarji/uyarılamama? | ER_NOW |
| pediatrics / cyanosis | Morarma/siyanoz? | ER_NOW |

**Net:** 4 → 17+ soru (+13).

### 4.4 Safety-guard hard triggers (`backend/app/data/rules.json.red_flags` — 13 hard + 7 soft)

Mevcut durumda iyi kapsama var (stroke, MI, anafilaksi, ağır solunum sıkıntısı, masif kanama, bilinç değişikliği, aktif nöbet, menenjit, meningokok döküntüsü, ağır travma, anaflaktoid, sepsis, self_harm). Stream A'da yalnız `specialty_routing` bölümüne 4 yeni specialty bloğu eklenecek.

---

## 5. Golden Flow Test Kapsama

### 5.1 Mevcut (7 senaryo, `tests/golden_flows/`)

| Dosya | Branş | Envelope |
|---|---|---|
| dermatology_acne_split.json | dermatology | RESULT |
| emergency_chest.json | cardiology | **EMERGENCY** |
| headache_migraine.json | neurology | RESULT |
| internal_gi_anal_pain.json | internal_gi | RESULT |
| ortho_joint_stiffness_swelling.json | orthopedics_rheum | RESULT |
| pulmonology_hemoptysis.json | pulmonology | RESULT |
| uti.json | urology_internal | RESULT |

### 5.2 Kapsama boşlukları

**Hiç coverage olmayan branşlar:** ent, ophthalmology, psychiatry, obgyn, pediatrics (yok), nephrology (yok), endocrinology (yok), general_surgery (yok)
**Envelope eksikleri:** Yalnız 1 EMERGENCY, QUESTION-only akış yok, düşük-güven (A9 gate) testi yok.

### 5.3 A10b hedefi (+18 senaryo)

| Dosya | Branş | Envelope |
|---|---|---|
| psychiatry_depression_chronic.json | psychiatry | RESULT |
| psychiatry_panic_attack.json | psychiatry | RESULT |
| psychiatry_active_suicidal_plan.json | psychiatry | **EMERGENCY** |
| obgyn_dysmenorrhea.json | obgyn | RESULT |
| obgyn_suspected_ectopic.json | obgyn | **EMERGENCY** |
| obgyn_pcos_irregular.json | obgyn | RESULT |
| ophth_conjunctivitis.json | ophthalmology | RESULT |
| ophth_acute_glaucoma.json | ophthalmology | **EMERGENCY** |
| ophth_sudden_vision_loss.json | ophthalmology | **EMERGENCY** |
| pedi_otitis_media.json | pediatrics | RESULT |
| pedi_febrile_seizure.json | pediatrics | **EMERGENCY** |
| pedi_bronchiolitis.json | pediatrics | RESULT |
| pedi_infant_high_fever.json | pediatrics | **EMERGENCY** |
| nephro_renal_colic.json | nephrology | RESULT |
| endo_new_dka.json | endocrinology | **EMERGENCY** |
| surg_acute_appendicitis.json | general_surgery | **EMERGENCY** |
| endo_t2dm_follow_up.json | endocrinology | RESULT |
| ent_otitis_external.json | ent | RESULT |
| cardio_stable_hypertension.json | cardiology | RESULT |
| low_confidence_no_conditions.json | — (A9 gate testi) | RESULT (top_conditions=[]) |

Total: 7 + 20 yeni = 27 senaryo. EMERGENCY: 1 → 8.

---

## 6. Öncelik Matrisi — Pazarlama/Impact Sıralaması

| Sıra | Session | Branş/Scope | Gerekçe |
|---|---|---|---|
| 1 | A9 | Confidence gate | **Altyapı sigortası** — tüm sonraki content'i "Brain hemorrhage" sızıntısından korur. 0.5 gün, düşük risk. |
| 2 | A7 collision test | test_synonym_collisions.py | A7 variant expansion'ı güvenle yapmak için. 2-3 saat. |
| 3 | A2 | Psikiyatri | Yüksek hacim (depresyon/anksiyete birinci basamakta top-3). Türkiye'de stigma sebebiyle pretriage yüksek değer katar. Self-harm red-flag zaten var — güçlendirme hızlı. |
| 4 | A3 | OB-GYN | Yüksek hacim + 2 kritik emergency (ektopik gebelik, preeklampsi). Ektopik gebelik T.C. birinci basamakta sık atlanan acil. |
| 5 | A4 | Oftalmoloji | Emergency sızıntı riski yüksek (ani görme kaybı → retina dekolmanı). Kapsam küçük (8-10 hastalık) ama impact büyük. |
| 6 | A5 | Pediatri | Yüksek hacim (çocuk ateş, RSV, otitis). Yaş bucket altyapısı gerekli → diğer branşları bloklamaz, paralel session'da bitirilebilir. |
| 7 | A6 | Genel Cerrahi + Nefro + Endo | Akut apandisit kritik emergency. DKA/hipoglisemi mortalite riski. Renal kolik birinci basamakta sık. |
| 8 | A10 | Disease list revizyonu | Veri hijyeni — Malaria/Dengue/AIDS gibi global gürültüyü temizler. Kullanıcı güvenini artırır. |
| 9 | A7 | Variant expansion (generator) | Recall iyileştirmesi — kullanıcı "başım zonkluyor" yazınca eşleşsin. Kümülatif işlem. |
| 10 | A8 | Rules audit + sameday doldurma | Boş `sameday_rules.json`'u doldurur. Expert review tetikleyici. |
| 11 | A10b | Golden flows | Regresyon kalkanı — önceki her session için 2-3 senaryo ekler. |
| 12 | A11 | UI yansıması | Full-stack ikon/label. Backend bittiğinde yapılır. |

---

## 7. Per-Session Numerik Hedefler (A2-A11'i sabitler)

| Session | Yeni canonical | Yeni disease | Yeni emergency rule | Yeni red-flag Q | Yeni golden flow |
|---:|---:|---:|---:|---:|---:|
| A2 Psikiyatri | 8 | 12 | 1 | 4 | 3 |
| A3 OB-GYN | 10 | 13 (+1 cross) | 3 | 3 | 3 |
| A4 Oftalmoloji | 6 | 10 | 2 | 2 | 3 |
| A5 Pediatri | 8 | 14 | 3 | 4 | 4 |
| A6 Nephro+Endo+GenSurg | 8 | 14 (+2 taşıma) | 3 | — | 4 |
| A7 Variant expansion | 0 (genişletme) | — | — | — | — |
| A8 Sameday + rules audit | — | — | — | — | — |
| A9 Confidence gate | — | — | — | — | 1 |
| A10 Disease list revizyonu | — | ~-10/+15 (net revizyon) | — | — | 2 (ent, cardio) |
| A10b Golden flows | — | — | — | — | +0 (önceki toplamla 20) |
| A11 UI full-stack | — | — | — | — | — |
| **Toplam** | **+40** | **+63** (+49 net) | **+12** | **+13** | **+20** |

---

## 8. Risk Dağılımı (Per-Session)

| Session | Risk | Mitigation |
|---|---|---|
| A2 Psikiyatri | Panik semptomları kardiyak false-positive yaratır (çarpıntı + nefes darlığı) | `psychiatric_emergency` kuralı yalnız explicit suicide plan için ER; panik→anksiyete routing + A9 gate |
| A3 OB-GYN | Ektopik gebelik false-negative | Red-flag sorusu "amenore + şiddetli pelvik ağrı" ER_NOW zincirler |
| A4 Oftalmoloji | Glokom krizi bulantıyla confound olur (GI false-positive) | `acute_glaucoma` kuralı tek-taraflı göz ağrısı + bulanık görme AND (require_all) gerektirir |
| A5 Pediatri | Yetişkin akışı bozulur | `_age_bucket` default "adult"; pediatri routing yalnız age verilirse aktif |
| A6 Endokrinoloji | DKA ve hipoglisemi confound olur | Kural ayrımı: DKA ↔ polidipsi+Kussmaul; hipoglisemi ↔ terleme+titreme+DM öyküsü |
| A7 Variant generator | Collision: aynı variant 2 canonical'a | Collision test CI-gate, longest-first match koruması |
| A8 Rules | Same-day false-positive kullanıcıyı gereksiz hastaneye yönlendirir | Expert review + golden flow edge-case'leri |
| A9 Gate | Yüksek-güvenli kritik tanı (heart attack) yanlışlıkla gizlenir | Threshold 0.35 konservatif; emergency envelope her zaman bypass |
| A10 Disease revizyonu | LLM agent eski label'ları hala üretir | `disease_to_specialty.json` tek kaynak; LLM output validation'da unknown label → drop |
| A10b Golden flows | Flaky | Deterministic fixture — LLM stubbed |
| A11 UI | i18n key eksikse UI crash | `getText` fallback mevcut (Faz 3'te test edildi) |

---

## 9. Açık Sorular (Tıp Profesyoneli Review İçin)

1. **Ektopik gebelik pretriage hassasiyeti**: "Amenore + pelvik ağrı + vajinal kanama" üçlüsü ER_NOW için yeterli mi, yoksa ayrıca `pozitif gebelik testi` anchor'ı istenmeli mi?
2. **Pediatrik ateş eşiği**: <3 ay ≥38°C ER_NOW — NICE vs AAP rehberleri farklı (AAP: 90 gün altı rektal ≥38°C). Hangi rehberi baseline alalım?
3. **Aktif intihar planı**: "Plan yaptım" keyword'ü yeterli trigger mi, yoksa method specificity (ilaç/ip/silah) + timeframe (bugün/bu hafta) sorulmalı mı?
4. **DKA threshold**: T1DM vs T2DM için farklı kural? (T2DM'de HHS daha sık — DKA değil)
5. **Konfidence threshold 0.35**: Klinik karar destek literatüründe optimal cut-off önerisi var mı? A/B test ile validate edilebilir mi?
6. **Disease list revizyonunda Hepatit A'nın tutulması**: Okul/kreş salgınları için mantıklı ama yetişkin akışında düşük prior — sadece çocuk branşında mı tutulsun?
7. **Somatizasyon ve fibromiyalji ayrımı**: Her ikisi de birden çok ağrı bölgesi + normal lab → psychiatry mi, orthopedics_rheum mi primary?

---

## 10. Sonraki Adım

**A2 — Psikiyatri branşı** (2 gün):
- 8 yeni canonical + variants (A1'deki liste)
- 12 yeni disease girdisi (A1'deki liste)
- 1 emergency kural (`psychiatric_emergency_active_plan`)
- 4 yeni red-flag sorusu
- `rules.json` psychiatry routing genişletme
- 3 golden flow senaryo

Commit sonrası A3'e geçilir.
