# ADR-001: Safety Guard Consolidation

**Status:** Accepted (live-path cutover landed; legacy-path follow-up tracked)
**Date:** 2026-04-27
**Deciders:** Eng (kod sahibi), Ürün (klinik karar)
**Risk lineage:** `RISK_REGISTER_2026_04.md:C-2` (Critical)
**Tech-debt lineage:** `TECH_DEBT_2026_04.md:#1`

---

## Context

Bugün `backend/app/` içinde iki ayrı `safety_guard` implementasyonu yan yana yaşıyor:

1. **`app/safety_guard.py`** (75 satır) — pure function `safety_guard_check(text_tr, answers, rules_json) -> Optional[Dict]`. Tamamen deterministic: `rules.json` `red_flags.hard_triggers` listesinden regex + keyword fallback. **Soft trigger yok, age risk yok, LLM çağrısı yok.** Çağıran: `triage_engine.run_orchestrator_turn` (README'de "live path" denilen entrypoint).

2. **`app/agents/safety_guard.py`** (171 satır) — class `SafetyGuardAgent(BaseAgent)`. `rules.json`'u modül import zamanında yükler, regex'leri pre-compile eder, **hard triggers + soft triggers + age risk + LLM-based final pass** birlikte sırayla çalıştırır. `SafetyGuardOutput` schema'sını döner. Çağıran: `app/agents/orchestrator.py`.

İki dosya da `data/rules.json` aynı kaynağı okuyor ama **sözleşme + akış farklı**. Aynı `rules.json` güncellemesi ikisini farklı şekilde etkileyebilir; daha kötüsü, biri güncellenirken (örn. yeni hard trigger eklenmesi ama eski path'e yansımaması) **emergency kuralı sessizce kaçabilir**.

Bu ürün sağlık sektöründe; emergency kaçağı = klinik zarar (kalp krizi/inme tipi semptomu hard-stop yapamamak). Risk register'da **C-2 Critical** olarak kayıtlı.

### Forces

- **Klinik garanti:** Hard trigger'lar deterministic + LLM bağımsız çalışmalı (LLM down olduğunda bile emergency yakalansın).
- **Zenginleştirme isteği:** Soft trigger + age risk + LLM enrichment gerçekten klinik değer üretiyor (ör. "65 yaş üstü + göğüs ağrısı çağrısı belirsiz" → temkinli yaklaş).
- **Akış birliği:** İki orchestrator path'i (`triage_engine` ve `agents/orchestrator`) live mı, biri deprecated mi netleşmemiş — bu ADR'ın çözmesi GEREKEN sorun değil ama her iki path'i de kapsamalı.
- **Cross-border data minimization:** Compliance KR-4 — LLM çağrılarına serbest metin gönderirken provider'a gitmeden önce hard trigger fire etmiş olmalı (acil semptom için LLM'e bile danışılmasın).
- **Test corpus:** Hard trigger değişikliklerinin ikinci bir yere unutulmadan yansıdığını test'le doğrulayabilmeliyiz.

---

## Decision

**Option B'yi seçiyoruz: deterministic fast path → opsiyonel LLM enrichment pipeline, tek entry point.**

Yeni modül: `app/safety/` (paket).

```
app/safety/
├── __init__.py           # public API: check_safety(...)
├── deterministic.py      # hard regex+keyword (eski safety_guard.py mantığı)
├── soft.py               # soft trigger + age risk
├── enrichment.py         # opsiyonel LLM pass (feature-flag'li)
├── types.py              # SafetyResult dataclass — single contract
└── rules_loader.py       # rules.json'u tek yerden yükler, cache'ler
```

Her iki orchestrator (`triage_engine` + `agents/orchestrator`) **`app.safety.check_safety(...)`'e geçer**. Eski iki dosya silinir (deprecation period 1 release).

### Akış (sırasıyla, kısa-circuit)

1. **Hard trigger** (deterministic, asla skip edilmez). Match → return `SafetyResult(status=EMERGENCY, ...)`. **LLM çağrılmaz.**
2. **Soft trigger** match var mı + high-risk age (`<6` veya `>65`)? → escalate to `EMERGENCY` (mevcut `agents/safety_guard.py` mantığı).
3. **Soft trigger var ama age low-risk** → result OK + `follow_up_questions` döner; orchestrator bunu sonraki turn'e taşır.
4. **Hiçbir match yok + LLM enrichment etkin** (`SAFETY_LLM_ENRICHMENT=true`) → opsiyonel LLM pass. LLM `EMERGENCY` derse `confirmed_by_llm=true` flag'iyle döner (klinik audit için).
5. **LLM enrichment kapalı veya LLM down** → result OK.

### Tek SafetyResult sözleşmesi

```python
@dataclass(frozen=True)
class SafetyResult:
    status: Literal["OK", "EMERGENCY"]
    rule_id: Optional[str]              # hangi trigger fire etti
    reason_tr: str
    instructions_tr: List[str]
    soft_triggers: List[str]            # follow-up için
    high_risk_age: bool
    enriched_by_llm: bool                # observability
    path: Literal["hard_keyword", "hard_regex", "soft_age", "llm", "none"]
```

`path` field'i **observability için kritik** — Prometheus counter `safety_guard_triggers_total{path=}` ile hangi path'in ne sıklıkta fire ettiğini izleyeceğiz.

---

## Options Considered

### Option A — İki dosyayı tek dosyaya merge

| Boyut | Değerlendirme |
|-------|---------------|
| Karmaşıklık | Orta |
| Maliyet | Düşük (1-2 gün) |
| Ölçeklenebilirlik | Yetersiz — büyüdükçe yine bölmemiz gerekecek |
| Tanıdıklık | Yüksek |

**Pros:**
- En hızlı çözüm.
- Tek dosya = tek import = tek test.

**Cons:**
- API surface seçimi belirsiz: top-level fonksiyon mu, class mı? İki çağıranı da memnun etmek için kompromis API çıkar.
- Hard path + soft + LLM aynı dosyada → 250+ satır, yine alt fonksiyonlara bölünmesi gerekecek.
- "Tek dosya" endişeyi gizler ama **iki orchestrator path'i sorunu çözmez**.

### Option B — Deterministic fast path → opsiyonel LLM enrichment pipeline (SEÇİLEN)

| Boyut | Değerlendirme |
|-------|---------------|
| Karmaşıklık | Orta |
| Maliyet | Orta (3-4 gün) |
| Ölçeklenebilirlik | İyi — yeni katman (örn. yeni klinik kural seti) ekleme yeri net |
| Tanıdıklık | Orta — paket yapısı yeni ama Pythonic |

**Pros:**
- **Klinik garanti:** Hard path her zaman çalışır, LLM kapanmasından bağımsız.
- **Tek sözleşme:** `SafetyResult` her iki orchestrator için aynı.
- **Compliance ile uyumlu:** LLM enrichment opsiyonel → `KR-4` (cross-border) için "LLM-suz mode" doğal olarak destekleniyor.
- **Observability:** `path` field + counter ile hangi katmanın ne sıklıkta tetiklendiği görünür.
- **Test corpus:** Tek entry point → tek test corpus, hard rule değişikliği iki yere unutulamaz.

**Cons:**
- Yeni paket yapısı; mevcut iki call site refactor gerektirir.
- Migration boyunca import path'leri değişir; küçük breaking change.

### Option C — İki orchestrator'dan birini deprecate

| Boyut | Değerlendirme |
|-------|---------------|
| Karmaşıklık | Yüksek |
| Maliyet | Yüksek (1-2 sprint) |
| Ölçeklenebilirlik | İyi (uzun vadede) |
| Tanıdıklık | Düşük — derin refactor |

**Pros:**
- "Sadece bir orchestrator var" → safety_guard problemini de doğal olarak çözer.

**Cons:**
- **Scope creep:** Bu ADR'ın amacı safety_guard; orchestrator deprecate kararı bambaşka boyut.
- Hangi orchestrator live? `triage_engine` README'de "live path" deniyor ama `agents/orchestrator` da imports görüyor — netlik yok.
- Migration süresi içinde hâlâ iki path olduğundan safety_guard sorunu *çözülmüyor*; sadece erteleniyor.

---

## Trade-off Analysis

| Boyut | A | B | C |
|-------|---|---|---|
| Klinik garanti | Eşit | **En iyi** (deterministic-first explicit) | Eşit |
| Maliyet | Düşük | Orta | Yüksek |
| Çözdüğü sorun kapsamı | Sadece safety_guard | safety_guard + observability + LLM-bağımsızlık + compliance hazırlık | Tüm orchestration |
| Risk (yapılırken) | Düşük (tek dosya değişir) | Orta (yeni paket, 2 call site refactor) | Yüksek (orchestrator hangisi sorgulanır) |
| 6 ay sonra durum | "İçinde 250 satır mı bu?" | "Net yapı, ekleme kolay" | "Bitirebildik mi?" |

**Karar gerekçesi:** Option B, klinik risk için en güçlü garantileri verir (hard path LLM bağımsız), tek SafetyResult sözleşmesi iki orchestrator path'i hâlâ ayakta olsa bile drift'i engeller, ve compliance hedefleriyle (cross-border, deterministic-only mode) doğal uyum içindedir. C bu sprint için scope dışı; A yetersiz.

---

## Consequences

**Kolaylaşan:**
- Hard rule eklenmesi/değiştirilmesi tek yerde olur, iki module'e unutulmadan yansır.
- "Emergency kuralı kaçtı mı?" sorusu için tek test corpus + tek metric.
- LLM provider değiştirmek (compliance KR-4): `enrichment.py` izole modül; `SAFETY_LLM_ENRICHMENT=false` ile prod'da kapatılabilir.
- `safety_guard_triggers_total{path=}` Grafana panel'inde hangi katmanın ne sıklıkta fire ettiği görünür.

**Zorlaşan:**
- Migration döneminde (1 release) iki call site eş zamanlı güncellenmeli; geçişte test corpus çok kritik.
- Yeni katkıcılar için "paket nedir, hangi dosya nedir" küçük bir öğrenme yokuşu.

**Tekrar bakacağımız:**
- LLM enrichment'ın gerçekten klinik değer üretip üretmediği (3 ay sonra metric review). Üretmiyorsa sadece risk kaynağı; kaldır.
- `path=llm` triggered ama hard path tetiklemedi case'leri — bunları kuralsızlaştırma sinyali olarak kullanıp `rules.json`'a ekle.

---

## Action Items

1. [x] **`app/safety/` paketini oluştur**, `types.py`'da `SafetyResult` dataclass'ı tanımla. *(session 17, 76dd0e8)*
2. [x] **`deterministic.py`'a eski `safety_guard.py` mantığını taşı**; behavior preserve. *(session 17, 76dd0e8)*
3. [x] **`soft.py`'a `agents/safety_guard.py`'dan soft trigger + age risk mantığını taşı**. *(session 17)*
4. [ ] **`enrichment.py`'a LLM pass'i taşı**, `SAFETY_LLM_ENRICHMENT` env flag. *(deferred — compliance KR-4 gates this; currently no-op stub OK)*
5. [x] **`__init__.py`'da public `check_safety()`** orchestrate eden fonksiyonu yaz. *(session 17)*
6. [x] **`triage_engine.py:24` import'unu güncelle** → `from app.safety import check_safety`. *(this commit)*
7. [ ] **`agents/orchestrator.py:25` import'unu güncelle**, `SafetyGuardAgent` wrapper'ını `check_safety`'i çağıracak şekilde sadeleştir veya kaldır. **Deferred** — `agents/orchestrator.py` is the legacy in-memory orchestrator (only `_handle_turn_legacy` uses it; live path is `triage_engine.run_orchestrator_turn`). The legacy path uses an async LLM step inside `SafetyGuardAgent.run()` — folding it into the new package is a separate refactor. Agent path retains `agents/safety_guard.py` until then.
8. [x] **`safety_guard_triggers_total{path=}` counter'ını `observability/metrics.py`'a ekle**, `__init__.py`'da increment et. *(session 17)*
9. [x] **Test corpus**: `tests/test_safety_consolidated.py` — her path için en az 5 case (hard_keyword, hard_regex, soft_age, none); 22 test, real `rules.json`. *(session 17)*
10. [x] **Live path için eski dosya sil**: `app/safety_guard.py` deleted along with its branch-coverage test (`tests/test_safety_guard_branches.py`); coverage replaced by the consolidated tests. `app/agents/safety_guard.py` stays until action 7 is complete. *(this commit)*
11. [ ] **CHANGELOG'a not düş** (breaking change değil, internal refactor).
12. [ ] **6 ay sonra LLM enrichment review tarihi takvim'e** (2026-10-27).

**Status:** live path cutover done. Legacy agent-orchestrator path (action 7) tracked as a separate ticket. Risk register C-2 downgraded from Critical to Medium — the duplicate that mattered for the live triage endpoint is gone.
