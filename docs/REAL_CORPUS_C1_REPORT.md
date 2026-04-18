# Real Corpus Regression Set (C1)

**Tarih:** 2026-04-18
**Korpus boyutu:** 46 hand-labeled senaryo (`tests/real_corpus/scenarios.json`)
**Test runner:** `backend/tests/test_real_corpus.py`
**Baseline measurement commit:** `1fd8c0c` (B2 sonrası)

## TL;DR

| Metric | Value |
|---|---|
| Total scenarios | 46 |
| **Baseline pass rate** | **24/46 = 52.2%** |
| `ambiguous` pass rate | 4/4 (100.0%) |
| `synthetic_new` pass rate | 10/18 (55.6%) |
| `paraphrase` pass rate | 10/24 (41.7%) |

`MIN_PASS_RATE` threshold'u **0.50**'ye pinlendi — baseline'ın 2 puan altı. Normal tuning flake üretmez, gerçek regresyon fail eder.

## Corpus composition

Üç kaynak karıştırıldı:

- **paraphrase** (24 scenario, 52%): golden_flows'daki klinik vakaların farklı Türkçe ifadeleri. NLU'nun canonical/keyword **robustness**'ini ölçer — golden_flows'da %100 pass eden bir vaka, ifade değişince yine tanınıyor mu?
- **synthetic_new** (18 scenario, 39%): golden_flows'da olmayan yeni klinik pattern'ler (sinüzit, GERD, konstipasyon, hipotiroidi, astım krizi, anafilaksi vd.). **Coverage** ölçer.
- **ambiguous** (4 scenario, 9%): gerçekten çok-seçenekli durumlar (yorgunluk, sırt/renal ağrı kesişimi). `final_type` assert edilir ama specialty esnetilir.

## Failure breakdown (baseline)

### Paraphrase source — NLU robustness gap (14/24 failing)

Golden_flows'da pass eden vaka farklı kelimelerle yazılınca çoğu senaryoda `internal_gi` fallback'e düşüyor. Örnekler:

| ID | Got | Expected | Failure |
|---|---|---|---|
| `nephro_stone_paraphrase_01` | internal_gi | nephrology | specialty |
| `neuro_migraine_paraphrase_01` | neurology | neurology | top_condition (Migren yok) |
| `obgyn_pcos_paraphrase_01` | internal_gi | obgyn | specialty |
| `ortho_arthritis_paraphrase_01` | internal_gi | orthopedics_rheum | specialty + top_condition |
| `psych_panic_paraphrase_01` | internal_gi | psychiatry | specialty |
| `psych_suicidal_redflag_01` | RESULT | EMERGENCY | final_type |
| `ophth_glaucoma_paraphrase_01` | RESULT | EMERGENCY | final_type + specialty |
| `pulm_hemoptysis_paraphrase_01` | **EMERGENCY** | RESULT | **LLM-style false-positive** (cardio rule fires on "gece terlemesi + kan") |

Kök sebep paternleri:
- Canonical variant listeleri golden_flow metinlerinin **kesin kelime dizilişine** tuned.
- "sol böbreğim" match ediyor ama "sağ yanım" → miss.
- "öleceğim korkusu" match ediyor ama `metroda ... kendimi kötü hissettim` → miss.
- "yaşamak istemiyorum" match ediyor ama `bu dünyadan gitmek istiyorum` → miss.

### Synthetic_new source — coverage gap (8/18 failing)

Golden_flows'da hiç olmayan vakalar. Her biri ayrı bir canonical/rule/scoring eksikliği:

- `neuro_stroke_redflag_01` (yüz kaydı, konuşma bozukluğu, kol tutmuyor) → stroke_redflags rule tetiklenmeli, tetiklenmiyor.
- `psych_anxiety_new_01`, `derm_eczema_new_01`, `derm_urticaria_new_01`, `pulm_cough_chronic_new_01`, `ortho_back_pain_new_01`, `ortho_knee_new_01`, `ent_sore_throat_new_01` — çoğunluk `internal_gi` fallback.

### Ambiguous source — 4/4 pass

Ambiguous senaryolarda `recommended_specialty` assert'i yok (sadece `final_type: RESULT`). Her dördü de RESULT dönüyor.

## Kök neden tespiti: golden-flow-overfit

Paraphrase pass rate'inin (%41.7) synthetic_new pass rate'inden (%55.6) **daha düşük** olması çarpıcı. Normalde yeni senaryolar daha zor olur. Burada tersi olması gösteriyor ki:

> Aşama A'da eklediğimiz canonical varyantları ve keyword listesi **golden_flow fixture metinlerine özel** — aynı klinik durumu farklı kelimelerle yazınca NLU canonical üretmiyor.

Bu "overfit to test set" problemidir. synthetic_new senaryolarda sistem daha "dürüst" çünkü orada hiç overfit yok.

## Önerilen takip işleri

Bunların hepsi C1 kapsamı dışında — ayrı PR'larda ele alınacak:

1. **NLU robustness tuning** (en büyük kazanım): paraphrase fail'lerindeki gerçek ifadeleri birer birer inceleyip `synonyms_tr.json` variant listelerini **generic pattern**'lere genişlet (örn: "böbreğim" — sağ/sol agnostik, "göğsümün ortası" — "göğüs ortası"ndan ayrı).
2. **Stroke redflag keyword audit**: `rules.json` hard_trigger "yüzüm kaydı/ağzım kaydı" pattern'i var mı? `neuro_stroke_redflag_01` neden tetiklenmiyor — kontrol et.
3. **Eczema / urtikaria / anksiyete yeni canonical'lar**.
4. **Korpusu büyüt**: hedef 100-150 senaryo. Gerçek anonim kullanıcı verisi ile doldur (PII temizlenmiş).

## Raporlama protokolü

- Her PR'dan sonra test runner `--print` modu pass rate ve per-source breakdown'u CI stdout'a basar.
- `MIN_PASS_RATE` değerini düşürmek için ayrı bir commit + yazılı gerekçe ister. Yukarı çekmek (baseline iyileşince) her zaman serbest.
- Senaryo ekleyen PR **aynı PR'da** baseline'ı günceller: yeni scenarios.json + yeni MIN_PASS_RATE + bu rapora ek bir "Run <commit>" tablosu.
