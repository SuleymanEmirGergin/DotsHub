# Shadow Eval Report (B1)

**Tarih:** 2026-04-18
**Komut:** `WIRO_API_KEY=<env> LLM_NLU_RATE_LIMIT_MAX_REQ=500 python backend/scripts/shadow_eval.py`
**Kaynak:** 25 golden flow senaryosu (`tests/golden_flows/*.json`), Aşama A sonrası (commit `ed2acde`).

## TL;DR

- **Deterministic specialty accuracy: 100.0%** (25/25) — Aşama A fix'leri sonrası baseline.
- **LLM NLU mode aynı koşumda 16/16 HTTP error (401 Unauthorized)**, her senaryo deterministic fallback'e düştü. LLM'in gerçek kazanç/kayıp eğrisi bu koşumda ölçülemedi.
- **Graceful degradation doğrulandı**: LLM API başarısız → deterministic fallback → routing hâlâ %100 doğru.

## Ham metrikler

| Metric | Değer |
|---|---|
| Scenarios evaluated | 25/25 |
| Scenarios crashed | 0 |
| final_type agreement (DET vs LLM) | 100.0% |
| specialty agreement (DET vs LLM) | 100.0% |
| DET specialty accuracy | **100.0%** (24/24 with expected specialty; `emergency_chest` has no expected specialty) |
| LLM specialty accuracy | 100.0% (identical to DET — fell back) |
| DET avg latency | 169 ms |
| LLM avg latency | 344 ms (includes network round-trip to Wiro) |
| LLM max latency | 2497 ms |

## nlu_source dağılımı

| Source | LLM mode count |
|---|---|
| `llm_http_error` | 16 |
| `?` (EMERGENCY early-return, payload meta yok) | 9 |
| `llm` (başarılı gerçek çağrı) | **0** |
| `hybrid` | 0 |

## Bulgu: LLM NLU broken (ayrı iş)

Tüm LLM çağrıları `Wiro /v1/Run/google/gemini-2-5-flash` endpoint'inde **401 Unauthorized** aldı. Debug log örneği:

```
WARNING:app.services.llm_nlu:LLM NLU call failed (HTTPStatusError):
Client error '401 Unauthorized' for url
'https://api.wiro.ai/v1/Run/google/gemini-2-5-flash'
```

Olası sebep: env'deki `WIRO_API_KEY` süresi dolmuş veya iptal edilmiş. İkincil: header yapılandırması değişmiş olabilir (`WIRO_API_SECRET` + `WIRO_API_KEY` imza mantığı).

**Etkilenen production path:** canlı triage akışı `LLM_NLU_ENABLED=True` iken her turn LLM'e istek atıp 401 alacak, fallback deterministic çalışacak. Safety açısından risk yok (sistem zaten DET %100) ama LLM'e ödenen cost sıfır yararlı çıktı üretiyor.

**Önerilen aksiyon:** yeni Wiro API key alındıktan sonra shadow eval tekrar çalıştırılıp bu rapor güncellensin. Ayrıca `.env` rotasyonu + auth exception için alert kuralı eklenebilir.

## Script bugfix (bu koşumla commit'lenen)

Önceki `_run_with_llm_flag` implementasyonu `patch("app.core.config.settings")` ile `MagicMock` kullanıyordu. llm_nlu_client yetmiş farklı attribute okuduğu için (`WIRO_API_KEY`, `WIRO_API_SECRET`, `WIRO_BASE_URL`, …) hepsi MagicMock objesi dönüyor ve çağrı sessizce fail oluyordu (`nlu_source: "deterministic"` — LLM hiç çağrılmamış gibi).

Fix: gerçek settings object üzerinde minimal mutasyon (`LLM_NLU_ENABLED`, `LLM_NLU_LOG_TO_SUPABASE`) + `try/finally` restore. Artık LLM fiilen çağrılıyor ve HTTP error gibi gerçek problemler raporda görünür.

## Sıradaki adımlar

- [ ] Yeni Wiro API key al → shadow eval tekrar koş → bu raporu ek bir bölümle güncelle (LLM vs DET canonical diff, confidence delta dağılımı, LLM'in fix ettiği / kırdığı senaryo listesi).
- [ ] Production için: 401 sürekli alınıyorsa `LLM_NLU_ENABLED=False` flag'iyle maliyet sıfırlansın ta ki key yenilenene kadar.
- [ ] Auth error telemetrisi — `llm_nlu.py` `llm_http_error` oranı bir threshold'u geçerse alert.
