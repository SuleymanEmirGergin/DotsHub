# Golden Flows 17/25 Regresyon Triajı

**Tarih:** 2026-04-17 (güncel: commit `0c6e94e` sonrası)
**Kapsam:** `tests/golden_flows/` altındaki 25 senaryonun baseline (deterministic) durumu
**Kaynak veri:** `backend/scripts/shadow_eval.py` JSON raporu

## TL;DR

- **25 golden flow senaryosundan 17'si fail** (deterministic mod, cwd `backend/`).
- **14 non-xfail fail kategorize edildi**; 1 senaryo A2 xfail, 2 senaryo ek assertion fail.
- **Üç ayrı root cause** teyit edildi (üçüncüsü P0 fix sonrası ortaya çıktı):
  1. **P0 runtime path bug:** `runtime.py` cwd-relative → `emergency_rules_cfg` boş. ✅ Fix edildi (`0c6e94e`).
  2. **P0b orchestrator wiring gap:** Aktif orkestratör `runtime.emergency_rules_cfg`'ye bakmıyor, `runtime.rules_json` kullanıyor. İki paralel kural kaynağı var ve aktif flow zayıf olanı tüketiyor. ❌ Henüz fix yok.
  3. **P1 NLU coverage:** Türkçe canonical extraction 5+ senaryoda eşleşme üretmiyor. ❌ Henüz fix yok.

## Kategori Dağılımı (14 non-xfail fail)

### 🚨 Category D — EMERGENCY false-negative (8, safety-critical)

Beklenen EMERGENCY → gerçekte RESULT dönüyor:

| Senaryo | Gerçek vaka | Got |
|---|---|---|
| `psychiatry_active_suicidal_plan` | "İlaçları biriktirdim, bu gece kullanmayı düşünüyorum" | RESULT/internal_gi |
| `pedi_infant_high_fever` | 6 haftalık bebek 38.5°C | RESULT/psychiatry |
| `pedi_febrile_seizure` | Çocuk ateş + kasılma + bilinç kaybı | RESULT/pediatrics |
| `endo_new_dka` | Tip 1 DM + polidipsi + bulantı | RESULT/endocrinology |
| `obgyn_suspected_ectopic` | Gebelik + kasıkta şiddetli ağrı + kanama | RESULT/obgyn |
| `ophth_acute_glaucoma` | "Işıkların etrafında hale" + ani ağrı | RESULT/internal_gi |
| `ophth_sudden_vision_loss` | "Perde indi, görmüyor" | RESULT/internal_gi |
| `surg_acute_appendicitis` | RLQ ağrı + ateş 38.7 | RESULT/internal_gi |

### Category A — NLU gap → `internal_gi` fallback (5, confidence=0.0)

| Senaryo | Expected | Got |
|---|---|---|
| `nephro_renal_colic` | nephrology | internal_gi |
| `obgyn_dysmenorrhea` | obgyn | internal_gi |
| `obgyn_pcos_irregular` | obgyn | internal_gi |
| `ophth_conjunctivitis` | ophthalmology | internal_gi |
| `psychiatry_panic_attack` | psychiatry | internal_gi |

### Category C — EMERGENCY false-positive (1)

`pedi_bronchiolitis` — 8 aylık bebek hırıltılı nefes + hafif ateş → gereksiz EMERGENCY.

### Category B (yanlış branş, fallback değil)

Yok.

## Root Cause #1 — Runtime cwd path bug (P0)

### Gözlem
`backend/app/runtime.py:227`:
```python
config_dir = Path("config")
emerg_path = config_dir / "emergency_rules.json"
if emerg_path.exists():
    emergency_cfg = load_json(str(emerg_path))
```

`Path("config")` **relative** — Python'un cwd'sine bağlı. CI/regression test suite'i `cd backend && python -m pytest ...` formatıyla koşuyor, dolayısıyla arama `backend/config/` altında yapılıyor. Dosya aslında repo-root `config/` altında → `emerg_path.exists()` False → `emergency_cfg = {}` sessizce boş kalıyor (`except Exception: pass` ile error da yutuluyor).

### Kanıt

```
$ cd backend && python -c "from app.runtime import load_runtime; print(len(load_runtime(data_dir='app/data').emergency_rules_cfg.get('rules', [])))"
0

$ cd <repo-root> && python -c "import sys; sys.path.insert(0,'backend'); from app.runtime import load_runtime; print(len(load_runtime(data_dir='backend/app/data').emergency_rules_cfg.get('rules', [])))"
19
```

### Etki
Rule'lar yüklenmediği için `evaluate_emergency()` hiçbir eşleşme döndürmüyor. Emergency envelope sadece `stop_rules.json`'daki ikincil yoldan çıkabiliyor:
```python
emergency_specialty_ids: ["cardiology", "emergency", "neurology"]
emergency_disease_keywords: ["Heart attack", "Paralysis", "Stroke", "Aortic", "Pulmonary embolism"]
```
Bu yüzden `emergency_chest.json` ve `pedi_bronchiolitis.json` EMERGENCY dönebiliyor (cardiology branşı kazanınca `stop_rules`'tan EMERGENCY escalate ediyor), ama config dosyasındaki **19 specialized emergency rule'un 17'si hiç çalışmıyor**: `psychiatric_emergency_active_plan`, `infant_fever_under3months`, `sudden_vision_loss`, `acute_glaucoma_crisis`, `dka_suspect`, `ectopic_pregnancy_suspect`, `febrile_seizure_active`, `acute_appendicitis_suspect`, vd.

### Fix — commit `0c6e94e` (tamamlandı)

- `_REPO_ROOT = Path(__file__).resolve().parent.parent.parent` ile cwd-independent path.
- `PRETRIAGE_CONFIG_DIR` env var override.
- `except Exception: pass` kaldırıldı → missing/empty/malformed config artık `app.runtime` logger üzerinden WARN/ERROR log atıyor.
- 8 unit test (`backend/tests/test_runtime_config_loading.py`) regresyonu pinliyor.

### Beklenmedik bulgu — Root Cause #1b (orchestrator wiring gap)

Shadow eval before/after diff: **0 senaryo değişti.** Deterministic accuracy hem öncesi hem sonrası %50.

Sebep: Aktif orkestratör (`backend/app/triage_engine.py:206`):
```python
emergency = safety_guard_check(input_text, answers, runtime.rules_json)
```

**İki paralel emergency kural kaynağı var:**

| Kaynak | Path | Kim tüketiyor | Rule sayısı |
|---|---|---|---|
| `runtime.rules_json` | `backend/app/data/rules.json` | `triage_engine.safety_guard_check` (canlı) | zayıf |
| `runtime.emergency_rules_cfg` | `config/emergency_rules.json` | `orchestrator_v5.emergency_router` (deneysel) | 19 curated |

Path fix zorunluydu çünkü:
1. `orchestrator_v5` aktif olduğu flow'larda (admin_v5, api_v5) artık rules var
2. Silent swallow kaldırıldı → gelecek regresyonlar görünür
3. **Synonym/keyword audit'in önkoşulu** — audit etmeden önce rules gerçekten yükleniyor olmalı

Ama canlı akış için **ek bir wiring PR'ı lazım**: `triage_engine` ya `runtime.emergency_rules_cfg` üzerinden `evaluate_emergency()`'yi çağırmalı, ya da iki kaynak tek dosyada konsolide edilmeli. Bu tercih karar gerektirir.

## Root Cause #2 — NLU canonical coverage boşluğu (P1)

### Gözlem
Path fix'ten sonra bile bazı safety-critical senaryolarda canonical boş:

| Senaryo | Canonical çıktısı |
|---|---|
| `pedi_infant_high_fever` ("bebeğim 6 haftalık, 38.5") | `[]` |
| `ophth_sudden_vision_loss` ("perde indi, görmüyor") | `[]` |
| `psychiatry_panic_attack` ("kalbim hızlandı, öleceğimi sandım") | `[]` |

Rule'lar için bu senaryolarda ya `canonical_any` match'i yok, ya da `keyword_any` listesi hastanın gerçek ifadelerini kapsamıyor:
- `infant_fever_under3months` rule'u "3 aydan küçük" arıyor — hasta "6 haftalık" yazıyor.
- `sudden_vision_loss` rule'u "ani görme kaybı" arıyor — hasta "perde indi, görmüyor" yazıyor.

### Önerilen fix (ayrı büyük PR, 2-3 saat)

1. **Synonym genişletmesi** (`backend/app/data/synonyms_tr.json`):
   - `perde indi` / `perde iniyor` / `görmüyorum` → `ani görme kaybı` canonical
   - `6 haftalık` / `yenidoğan` / `1-3 aylık` → `yenidogan doneminde ateş` veya yeni canonical
   - `öleceğimi sandım` / `kontrolü kaybetme korkusu` → `panik atak` canonical
   - `kalbim hızlandı` / `çarpıntı` → `çarpıntı` canonical (mevcut muhtemelen eksik)
   - `adet sancısı` / `kramp` → `dismenore` canonical
   - `kırmızı idrar` / `kan işedim` → `hematuri` canonical

2. **Emergency rule `keyword_any` listesi audit**:
   Her rule için gerçek hasta ifadesi örneklerinden 3-5 Türkçe varyant ekle.

3. **Metrik:** Fix sonrası shadow_eval çıkarıp `det_specialty_accuracy_pct` ve false-negative sayısını raporla.

## Category C (false-positive) — ayrı küçük PR

`pedi_bronchiolitis` (8 aylık, hırıltı, hafif ateş, 2 gün): stop_rules "pediatrics → emergency" agresif tetikleniyor. Çözüm: pediatrik wheezing için age_months ve respiratory_distress şiddet gate'i ekle.

## Öncelik ve PR planı (güncel)

| # | İş | Öncelik | Süre | Durum | Etki |
|---|---|---|---|---|---|
| 1 | Runtime path fix + silent swallow kaldır | P0 (safety) | 30 dk | ✅ `0c6e94e` | Rules artık yüklü; silent failure kapısı kapandı |
| 1b | **Orchestrator wiring: canlı akış `emergency_rules_cfg`'yi tüketsin** (veya iki kaynağı konsolide et) | P0 (safety) | 2-4 saat | ❌ Açık | 8 safety-critical senaryo + ek emergency kapsaması |
| 2 | Synonym genişletmesi + `keyword_any` audit | P1 | 2-3 saat | ❌ Açık | ~10 senaryo, NLU kapsaması |
| 3 | `pedi_bronchiolitis` false-positive | P2 | 1 saat | ❌ Açık | 1 senaryo |
| 4 | A2 panic-vs-cardio softener (xfail→pass) | P2 | 1-2 saat | ❌ Açık | 1 senaryo |

**Not:** #1b #2'nin önkoşulu — synonym genişletmesini test etmeden önce canlı akış zengin rule setini kullanıyor olmalı, aksi halde audit'in gerçek etkisi ölçülemez.

### İlgili referanslar
- Shadow eval tool: `backend/scripts/shadow_eval.py`
- A2 edge fixture: `tests/golden_flows/psychiatry_panic_vs_cardio_edge.json`
- Emergency router: `backend/app/emergency_router.py`
- Canonical extract: `backend/app/canonical_extract.py`
- Runtime loader (bug'lı satır): `backend/app/runtime.py:227`
- Emergency rules: `config/emergency_rules.json` (19 rule)
- Stop rules (ikincil emergency yolu): `backend/app/data/stop_rules.json`
