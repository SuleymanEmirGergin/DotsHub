# Shadow Eval Report (B1)

**Tarih:** 2026-04-18 (HMAC auth fix sonrası güncellendi)
**Komut:** `WIRO_API_KEY=<env> WIRO_API_SECRET=<env> LLM_NLU_RATE_LIMIT_MAX_REQ=500 python backend/scripts/shadow_eval.py`
**Kaynak:** 25 golden flow senaryosu (`tests/golden_flows/*.json`), Aşama A sonrası (commit `ed2acde`) + HMAC auth fix.

## TL;DR

- **Deterministic specialty accuracy: 100.0%** (24/24 with expected specialty).
- **LLM specialty accuracy: 91.67%** (22/24) — LLM 2 pediatri senaryosunda routing'i kırıyor.
- **Mode agreement: 92.0%** (23/25 senaryoda DET ve LLM aynı final_type + specialty).
- **Graceful degradation doğrulandı**: LLM başarısızlığında deterministic fallback → safety korunuyor.
- **İlk denemedeki 401 Unauthorized kök sebebi bulundu ve düzeltildi**: Wiro projesi HMAC signature auth zorunlu (x-api-key + x-nonce + x-signature). Hem sync (`services/llm_nlu_client.py`) hem async (`core/llm_client.py`) client'lar imza hesaplıyor artık.

## Ham metrikler (HMAC auth sonrası)

| Metric | Değer |
|---|---|
| Scenarios evaluated | 25/25 |
| Scenarios crashed | 0 |
| final_type agreement (DET vs LLM) | 92.0% |
| specialty agreement (DET vs LLM) | 92.0% |
| **DET specialty accuracy** | **100.0%** (24/24 with expected specialty) |
| **LLM specialty accuracy** | **91.67%** (22/24) |
| LLM breaks routing on | `pedi_bronchiolitis`, `pedi_otitis_media` |
| LLM fixes routing on | — (DET zaten %100) |

## Confidence delta dağılımı (|Δ| ≥ 0.03)

| Senaryo | DET conf | LLM conf | Δ |
|---|---|---|---|
| `uti` | 0.388 | 0.686 | **+0.298** |
| `psychiatry_depression_chronic` | 0.200 | 0.325 | +0.125 |
| `obgyn_pcos_irregular` | 0.200 | 0.322 | +0.122 |
| `ortho_joint_stiffness_swelling` | 0.445 | 0.495 | +0.050 |
| `endo_t2dm_follow_up` | 0.493 | 0.461 | -0.032 |
| `pedi_bronchiolitis` | 0.090 | 0.000 | **-0.090** (QUESTION'a düştü) |
| `pedi_otitis_media` | 0.090 | 0.000 | **-0.090** (QUESTION'a düştü) |

## Bulgu 1: LLM pediatri regresyonu (kritik)

**`pedi_bronchiolitis`** ("8 aylık bebeğim hırıltılı nefes alıyor, hafif ateşi var") ve **`pedi_otitis_media`** ("2 yaşındaki oğlum sabahtan beri kulağını çekiştiriyor") senaryolarında:
- DET mode: RESULT/pediatrics (Aşama A'da eklenen context injection sayesinde)
- LLM mode: **QUESTION** (routing hiç olmuyor)

Hipotez: LLM NLU Wiro prompt'una gönderilen canonical listesinde `bebek nefes hırıltısı` ve `kulak çekiştirme` yeterince görünür değil, LLM onları extract etmiyor → context injection tetiklenmiyor (injection koşulu: o canonical setinde olmalı) → pediatrics scoring yeterli gelmiyor → QUESTION.

**Aksiyon:** ya (a) context injection'u canonical yerine "text contains X" pattern'ine döktür, ya da (b) LLM prompt'unda bu pediatric canonical'ları özellikle vurgula. Takip PR'ı gerek.

## Bulgu 2: LLM güven artırıcı senaryolar

`uti`, `depression_chronic`, `pcos_irregular`, `ortho`, `panic_vs_cardio_edge` senaryolarında LLM **DET'i doğrulayıp** confidence'ı net artırıyor — özellikle `uti` (+0.298) kullanıcıya gösterilecek güven skorunu 0.39 → 0.69'a çıkarıyor, hiçbir routing kaybı olmadan. LLM'in NET katkısı burada olumlu.

## Bulgu 3 (ilk denemeden, çözüldü): Wiro HMAC signature auth

İlk koşumda 16/16 LLM çağrısı `401 Unauthorized` aldı. Kök neden: **`services/llm_nlu_client.py` ve `core/llm_client.py` sadece static `x-api-key` (+ opsiyonel `x-api-secret`) gönderiyordu** ama Wiro projesi HMAC imza zorunlu:

```python
# Wiro docs formülü
signature = HMAC-SHA256(key=API_KEY, message=API_SECRET + NONCE).hexdigest()
headers = {"x-api-key": KEY, "x-nonce": timestamp, "x-signature": signature}
```

Bu commit ile iki client'ta da implement edildi. Canlı Wiro endpoint'e `POST /v1/Run/google/gemini-2-5-flash` artık 200 OK dönüyor.

**Güvenlik:** HMAC imzası sayesinde `WIRO_API_SECRET` artık wire'da geçmiyor (replay attack koruması + log sızıntılarında secret sızmaz).

## Script bugfix (bu koşumla commit'lenen)

Önceki `_run_with_llm_flag` implementasyonu `patch("app.core.config.settings")` ile `MagicMock` kullanıyordu. llm_nlu_client yetmiş farklı attribute okuduğu için (`WIRO_API_KEY`, `WIRO_API_SECRET`, `WIRO_BASE_URL`, …) hepsi MagicMock objesi dönüyor ve çağrı sessizce fail oluyordu (`nlu_source: "deterministic"` — LLM hiç çağrılmamış gibi).

Fix: gerçek settings object üzerinde minimal mutasyon (`LLM_NLU_ENABLED`, `LLM_NLU_LOG_TO_SUPABASE`) + `try/finally` restore. Artık LLM fiilen çağrılıyor ve HTTP error gibi gerçek problemler raporda görünür.

## Sıradaki adımlar

- [x] ~~Wiro API key yenile~~ → key zaten valid, problem HMAC auth eksikliğiydi. ✅ Fix commit'lendi.
- [ ] **Pediatri LLM regresyonu**: `pedi_bronchiolitis` + `pedi_otitis_media` senaryolarında LLM context injection kaçırıyor. Ya context injection koşulunu "text contains X" pattern'ine döktür, ya da LLM prompt'una pediatric canonical'ları açıkça ekle. (ayrı PR)
- [ ] Canonical-level diff raporu: LLM DET'in ürettiği canonical'lara ek olarak ne getiriyor / ne eksik bırakıyor? `scripts/shadow_eval.py`'ye canonical-set diff sütunu eklenebilir. (nice-to-have)
- [ ] Auth error telemetrisi: `llm_http_error` oranı threshold'u geçerse alert (production observability).
