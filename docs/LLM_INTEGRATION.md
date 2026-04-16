# LLM Integration — Stream B

> **Status:** Skeleton. Content is filled in as each session completes.
> **Strategy reference:** `docs/ARCHITECTURE.md` → "Hibrit Mimari — Gelecek Evrim".
> **Parallel stream:** `docs/COVERAGE_EXPANSION.md` (Stream A).

---

## 1. Amaç

Mevcut deterministik triage pipeline'ının önüne bir **LLM NLU katmanı**
eklemek — ama **medikal kararı LLM'e bırakmadan**. LLM sadece Türkçe
serbest metni canonical semptom listesine çevirir; karar (branş, risk,
safety note) deterministik rule engine'de kalır.

### Neden hibrit?

| | Saf kapsam genişletme | Saf LLM | **Hibrit** |
|---|---|---|---|
| Gerçek kullanıcı doğruluğu | %40-60 | %85-95 | **%85-95** |
| Hallucination riski | Sıfır | Yüksek | **Sıfır** (karar kural-bazlı) |
| Regülatör uyumu (SaMD) | Kolay | Zor/imkânsız | **Kolay** (LLM sadece NLU) |
| Explainability | Tam | Kayıp | **Tam** |
| Maliyet (1000 user/gün) | $0 | ~$50/gün | **~$5/gün** (Haiku/mini) |
| Bakım yükü | Çok yüksek | Düşük | Orta |
| Dil desteği | Her dil sıfırdan | Ücretsiz | **Ücretsiz** |

---

## 2. Mimari

```
Kullanıcı metni
  ↓
[Katman 1 — LLM NLU]           ← B stream'in eklediği kısım
  ↓ structured output (JSON)
{ canonicals, negations, duration_days, red_flags }
  ↓
[Katman 2 — Rule Engine]       ← mevcut pipeline, dokunulmaz
  ↓
[Katman 3 — LLM Explanation]   ← opsiyonel; karar değiştirmez
  ↓
Envelope
```

LLM çuvallarsa (timeout, schema violation, rate limit, down) →
deterministik fallback olarak `canonical_extract.extract_canonicals_tr`
devreye girer. Sistem LLM'ye bağımlı değildir.

Detay diagram: `docs/ARCHITECTURE.md` → "Hibrit Mimari".

---

## 3. Tasarım İlkeleri (değişmez)

1. **LLM karar vermez, sadece çevirir.** Structured output dışına
   çıkmaz. `tool_use` / `response_format: json_schema` ile zorlanır.
2. **Fallback daima deterministik.** Schema invalid → fallback, timeout
   → fallback, 5xx → fallback. Failure mode'u hiçbir zaman "sistem çöktü"
   değildir.
3. **PII LLM'e gitmez.** `app.pii.redact_pii` LLM call'dan önce.
4. **Determinism observability.** `_meta.nlu_source` field'ı
   `"llm" | "deterministic" | "hybrid"` döner → A/B karşılaştırma mümkün.
5. **Cost guardrail.** Günlük bütçe aşılırsa LLM devre dışı kalır,
   sistem deterministik mod'da çalışmaya devam eder.

---

## 4. Session Listesi ve Durum

| Session | Scope | Durum | Çıktı Dosyası |
|---|---|---|---|
| B1 | Architecture decision: provider, cost, KVKK stratejisi | ⏳ In progress | `docs/medical/llm_architecture_decision.md` (TBD) |
| B2 | `app/services/llm_nlu.py` iskelet + structured output schema | Pending | — |
| B3 | Provider client: Anthropic/OpenAI SDK, timeout, retry, circuit breaker | Pending | — |
| B4 | `triage_engine.py` entegrasyon + deterministik fallback + `_meta.nlu_source` | Pending | — |
| B5 | Unit testler (mocked LLM, schema violation, timeout) | Pending | — |
| B6 | Integration testler + golden flow A/B karşılaştırma raporu | Pending | — |
| B7 | Observability: Supabase `llm_calls` tablosu, dashboard panel | Pending | — |
| B8 | KVKK/privacy: PII redaction sırası, prompt injection guard, consent UX | Pending | — |
| B9 | Katman 3 — Explanation layer (opsiyonel) | Pending | — |
| B10 | Self-hosted LLM spike (Llama 3.1 8B / Qwen 2.5 7B) | Pending | — |

---

## 5. Kilit Kararlar (ADR-style)

> Her karar tamamlandığında bu bölüme tek satırlık özet + ilgili commit
> hash eklenir. Uzun rasyonel için ayrı `docs/medical/adr/*.md` dosyası
> yazılır.

### ADR-B-001: Provider seçimi
_Pending B1._ Aday'lar: Anthropic Haiku, OpenAI gpt-4o-mini, Gemini
1.5 Flash, self-hosted Llama 3.1 8B / Qwen 2.5 7B. Karar kriterleri:
Türkçe kalite, maliyet, latency, KVKK uyumu.

### ADR-B-002: Structured output formatı
_Pending B2._ Aday'lar: Anthropic `tool_use`, OpenAI `response_format:
json_schema`, manual JSON + Pydantic validate. Schema `synonyms_tr.json`
canonical listesinden dinamik üretilmeli.

### ADR-B-003: Fallback threshold
_Pending B4._ Hangi durumlarda LLM output reddedilip deterministik
fallback'e geçilir? (schema invalid, confidence < X, provider 5xx,
timeout > Y ms).

### ADR-B-004: Günlük maliyet tavanı
_Pending B7._ Aşıldığında LLM devre dışı kalsın mı, yoksa daha ucuz
modele fallback mi? (ör: Haiku → deterministic vs Haiku → Sonnet → Haiku).

### ADR-B-005: On-premise / KVKK
_Pending B8/B10._ Prod'da cloud LLM kullanılabilir mi, yoksa
self-hosted zorunlu mu? Veri işleme anlaşması seçenekleri.

---

## 6. Çalıştırma ve Test

_B2 tamamlandığında eklenecek._

Planlanan:

```bash
# Unit testler (mocked)
cd backend
python -m pytest tests/test_llm_nlu.py -v

# Integration: LLM açık + LLM kapalı karşılaştırma
python scripts/ab_compare_nlu.py --scenarios tests/golden_flows/

# A/B raporu
python scripts/audit_coverage.py --llm-enabled --json > before.json
# ... expansion ...
python scripts/audit_coverage.py --llm-enabled --json > after.json
```

---

## 7. Maliyet Modeli

_B1 tamamlandığında sabitlenir._

Ön tahmin (Claude Haiku, ortalama turn ~500 input + 200 output token):
- Input: $0.0005/turn
- Output: $0.0003/turn
- Turn başına ~$0.0008
- 1000 user/gün × 5 turn = ~$4/gün
- Aylık: ~$120

Aylık bütçe tavanı (öneri): **$200**. Aşılırsa otomatik devre dışı + alert.

---

## 8. Risks ve Mitigation

| Risk | Mitigation |
|---|---|
| LLM provider outage | Deterministik fallback her zaman aktif |
| Schema drift (LLM farklı JSON döner) | Pydantic validate + test suite'de mock scenarios |
| Prompt injection | Sistem mesajı sertleştir, tool_use zorla, user input quote |
| KVKK ihlali | PII redaction ZORUNLU, LLM'ye raw text gitmez |
| Maliyet patlaması | Günlük bütçe guard, circuit breaker |
| Regülatör sorgusu | Karar katmanı deterministik ve auditable — LLM sadece NLU |
| Latency (1-3s) | Stream output yok, 10s timeout, deterministik fallback hızlı |

---

## 9. İlgili Dokümanlar

- `docs/ARCHITECTURE.md` — mimari genel bakış
- `docs/COVERAGE_EXPANSION.md` — Stream A (paralel)
- `docs/PRIVACY_AND_SECURITY.md` — KVKK + PII redaction
- `docs/SERBEST_METIN_PARSING.md` — mevcut deterministik extractor
