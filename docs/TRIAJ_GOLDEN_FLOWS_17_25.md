# Golden Flows 17/25 Regresyon Triajı

**Tarih:** 2026-04-17
**Kapsam:** `tests/golden_flows/` altındaki 25 senaryonun baseline (deterministic) durumu
**Kaynak veri:** `backend/scripts/shadow_eval.py` JSON raporu

## TL;DR

- **25 golden flow senaryosundan 17'si fail** (deterministic mod, cwd `backend/`).
- **14 non-xfail fail kategorize edildi**; 1 senaryo A2 xfail, 2 senaryo ek assertion fail.
- **İki ayrı root cause** teyit edildi:
  1. **P0 safety:** `backend/app/runtime.py` relative path bug → `config/emergency_rules.json` CI/test koşumunda **hiç yüklenmiyor** (0 rule).
  2. **P1 coverage:** NLU Türkçe canonical extraction 5 senaryoda hiç eşleşme üretmiyor → `internal_gi` fallback + emergency rule'ların `canonical_any` clause'ları ölü kalıyor.

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

### Önerilen fix (ayrı küçük PR)

```python
# backend/app/runtime.py
from pathlib import Path

# repo root: backend/app/runtime.py → ../../  -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
config_dir = _REPO_ROOT / "config"
```

Ayrıca `except Exception: pass` sessiz yutmayı kaldır → boş rules yüklenince WARN log at (silent regression'dan kaçın).

**Fix ile kurtulan senaryolar (doğrudan kanıtlı):**
- `psychiatry_active_suicidal_plan` ✅ (canonical `intihar kendine zarar` → `psychiatric_emergency_active_plan` sev=3)

Diğer safety-critical senaryolar için path fix tek başına yetmiyor — Root Cause #2 ile birleşmeli.

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

## Öncelik ve PR planı

| # | İş | Öncelik | Süre | Etkilenecek senaryo sayısı |
|---|---|---|---|---|
| 1 | **Runtime path fix + silent swallow kaldır** | P0 (safety) | 30 dk | 1 net kanıt + emergency rules artık canlı |
| 2 | Synonym genişletmesi + keyword audit | P1 | 2-3 saat | ~10 senaryo |
| 3 | `pedi_bronchiolitis` false-positive | P2 | 1 saat | 1 senaryo |
| 4 | A2 panic-vs-cardio softener (xfail fix) | P2 | 1-2 saat | 1 senaryo (xfail→pass) |

### İlgili referanslar
- Shadow eval tool: `backend/scripts/shadow_eval.py`
- A2 edge fixture: `tests/golden_flows/psychiatry_panic_vs_cardio_edge.json`
- Emergency router: `backend/app/emergency_router.py`
- Canonical extract: `backend/app/canonical_extract.py`
- Runtime loader (bug'lı satır): `backend/app/runtime.py:227`
- Emergency rules: `config/emergency_rules.json` (19 rule)
- Stop rules (ikincil emergency yolu): `backend/app/data/stop_rules.json`
