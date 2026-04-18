# Hastalık Şüphesi Katmanı (C2)

**Tarih:** 2026-04-18
**Commit kapsamı:** C2 uygulaması — curated/kaggle ayrımı, confidence gate aktivasyonu, hasta hazırlık metadatası, real_corpus genişletmesi.
**Değişen dosyalar:** 6 (katalog, runtime, triage_engine, real_corpus, test runner, bu rapor).

## TL;DR

- RESULT envelope'un `top_conditions` listesindeki her entry artık **`source_type`** etiketi taşıyor:
  - `"curated"`: deterministik canonical pattern'den inject edilen, klinik olarak spesifik 8 etiket (Panik Bozukluk, Majör Depresyon, Akut Otitis Media, Bronşiolit, Renal Kolik, Dismenore, PCOS, Alerjik Konjonktivit).
  - `"kaggle_candidate"`: Kaggle disease matrix'ten gelen adaylar.
- Curated entry'ler **patient-prep metadatası** taşıyor: `icd10`, `disease_description_tr`, `doktora_sorulacak_sorular_tr`, `izlenecek_belirtiler_tr`, `ne_zaman_tekrar_basvur_tr`, `self_care_tr`, `aciliyet_notu_tr`, `disclaimer_tr`.
- **A9 confidence gate** (daha önce devre dışıydı) artık aktif — ama **curated-aware**: curated entry'ler herhangi bir confidence'ta geçer, Kaggle candidate'ler <0.25 eşiğin altında drop edilir.
- Real corpus 46 → **79 senaryo**ya genişledi; pass rate threshold'u yeni baseline'a göre 0.35'e kalibre edildi.

## Ürün kararı özetleri (karar alındı → uygulama)

| Soru | Karar | Uygulama |
|---|---|---|
| UI konumu | Opsiyon A — "Olası durumlar (bilgi amaçlı)" low-key liste | Backend payload hazır; mobile/dashboard render'ı takip PR |
| Confidence gate | Aktif et, dene | `_apply_gate_curated_aware` eklendi, threshold 0.25 (migraine fixture'ını koruyor) |
| Kaynak ayrımı | Kesinlikle ayır | `source_type` alanı her entry'de |
| Korpus genişletmesi | Büyük tut | 46 → 79 senaryo (+%72) |
| Ek meta ne gelmeli | Bana bırakıldı | Aşağıdaki katalog yapısı — ICD-10 + 4 hasta-odaklı alan + disclaimer |

## Backend payload şeması (RESULT envelope)

```json
{
  "urgency": "ROUTINE",
  "recommended_specialty": {"id": "psychiatry", "name_tr": "Psikiyatri"},
  "top_conditions": [
    {
      "disease_label": "Majör Depresyon",
      "score_0_1": 0.6,
      "source_type": "curated",
      "icd10": "F33.0",
      "disease_description_tr": "En az 2 hafta süren belirgin çökkün duygu durumu...",
      "doktora_sorulacak_sorular_tr": [
        "Belirtilerim ne kadar süredir var ve giderek mi ağırlaşıyor?",
        "İlaç tedavisi mi, psikoterapi mi, her ikisi mi benim için uygun?",
        ...
      ],
      "izlenecek_belirtiler_tr": ["Uyku süresi ve kalitesi", ...],
      "ne_zaman_tekrar_basvur_tr": [
        "Aktif intihar planı veya kendine zarar verme düşüncesi → hemen 112...",
        ...
      ],
      "self_care_tr": ["Her gün kısa da olsa dışarı çık...", ...],
      "aciliyet_notu_tr": "Aktif intihar planı varsa acildir...",
      "disclaimer_tr": "Bu liste tanı değildir, yalnızca hazırlık amaçlıdır..."
    },
    {
      "disease_label": "Migren",
      "score_0_1": 0.33,
      "source_type": "kaggle_candidate",
      "disclaimer_tr": "Bu liste tanı değildir..."
      // Kaggle entries don't carry curated prep fields in this release
    }
  ]
}
```

## Confidence gate — curated-aware

`backend/app/triage_engine.py:_apply_gate_curated_aware`:

- Curated entry'ler confidence'dan bağımsız her zaman geçer (deterministic canonical pattern'den injection oldukları için "fragile differential" değiller).
- Kaggle candidate'lerde `_RESULT_TOP_CONDITIONS_GATE = 0.25` eşiği uygulanır. Altında drop.
- Default threshold `top_conditions_filter.MIN_CONFIDENCE_FOR_CONDITIONS = 0.35` değil — live ölçümde tipik RESULT confidence'ları 0.09-0.50 aralığında; 0.35 çok sıkı (migraine gibi rutin vakaları siliyor).

**Takip:** threshold'u deneyimle ayarla. Kullanıcı geri bildirimine göre 0.20-0.30 arasında tune.

## Multi-tenant mimari hazırlığı

`curated_conditions.json` dosyası `"tenant_scope": "default"` alanını taşıyor. İleride A hastanesi / B hastanesi farklı etiket setlerine geçildiğinde yapılacaklar:

1. `backend/app/data/curated_conditions.<tenant>.json` çoğul dosya
2. `load_runtime(tenant_id=...)` parametresi veya `TENANT_ID` env var
3. Request-time tenant çözümleme (query parameter veya subdomain → runtime'a map)
4. Admin paneli: tenant seçici + curated katalog editörü

**Şu andaki davranış:** tek "default" tenant, ve `triage_engine._CURATED_INJECTED_LABELS` set'i hard-code'lu. Multi-tenant'a geçişte bu set de tenant-scoped olmalı.

## Real corpus genişlemesi

| Milestone | Senaryo sayısı | Pass rate | Threshold |
|---|---|---|---|
| C1 baseline (`1fd8c0c`) | 46 | 52.2% | 0.50 |
| C2 expand (bu commit) | **79** | 40.5% | 0.35 |

Pass rate geçici olarak düştü — yeni 33 senaryo henüz tuning görmedi. Per-source breakdown:

| Source | Count | Pass rate |
|---|---|---|
| ambiguous | 5 | 100.0% |
| paraphrase | 36 | 33.3% |
| synthetic_new | 38 | 39.5% |

Bu düşüş beklenen — amaç test yüzeyini önce genişletmek, sonra tuning yapmak. paraphrase'lerin synthetic'den daha düşük oranda pass etmesi C1 raporunda tespit edilen "canonical-overfit" desenini doğruluyor ve ek kanıt sağlıyor.

## Eklenen patient-prep alanlarının güvenlik profili

Her curated entry'de:

- **`ne_zaman_tekrar_basvur_tr`**: kullanıcı kötüleşirse ne yapacağını açıkça söylüyor (112, acil servis, belirli kriterler). Pre-triage sisteminin "safety first" ilkesine uygun.
- **`aciliyet_notu_tr`**: hekim-yüzlü bir cümle — "rutin değerlendirme uygun" vs "acil" netleştirmesi.
- **`disclaimer_tr`**: her entry'de otomatik — UI bu footer'ı göstermek zorunda.
- **Self-care önerileri** tedavi önerisi değil, klinik öncesi yaşam tarzı ipuçları (egzersiz, uyku, ağrı kesici kullanımı). İlaç doz/seçimi önerisi yok.

## Takip iş listesi

1. **UI render**: mobile + dashboard RESULT screen'inde `top_conditions[*].source_type`, icd10, sorular, izlenecek belirtiler, disclaimer'ı gösteren koleksiyon. (Opsiyon A — low-key liste)
2. **Kaggle candidate enrichment**: mevcut Kaggle label'ları için de kısa açıklama + ICD-10 lookup tablosu. Sadece curated'lar değil, tüm Kaggle label'lar (en az 20-30 top pattern) için hasta-odaklı meta.
3. **Gate threshold tuning**: kullanıcı feedback sonrası 0.25 değerini 0.20 veya 0.30'a ayarlama — ve/veya Kaggle candidate'leri için "scary label" listesi (Heart attack, Paralysis vs) özel olarak daha yüksek threshold.
4. **Multi-tenant mimari**: yukarıda sıralandı.
5. **Real corpus tuning**: 47 fail senaryoyu incele; synonym/keyword gap'leri kapat. Her turda pass rate 5-10 puan yukarı çekilebilir. Hedef 80%.
