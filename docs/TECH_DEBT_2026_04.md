# Tech Debt — Backend (`backend/app/`) — 2026-04

Audit kapsamı: `backend/app/` (live tree, archive hariç). 5 kategori: deprecated/experimental kod, rate-limit + auth fallback, Supabase/external error handling, test coverage, duplicate flows. Çıktı 1 sayfa, öncelikli.

**Skor:** Priority = (Impact + Risk) × (6 − Effort). Effort: S=1, M=3, L=5.

---

## P0 — Kritik (bu sprint içinde)

| # | Bulgu | Dosya | Neden | Eff | Risk | Skor |
|---|------|------|------|-----|------|------|
| 1 | **Duplicate `safety_guard`** — top-level (75 satır, deterministic) ile `agents/safety_guard.py` (171 satır, LLM-enhanced) paralel yaşıyor; ikisi de live (orchestrator agents'i kullanıyor, `scoring_v2.py:22` top-level'i import ediyor) | `app/safety_guard.py`, `app/agents/safety_guard.py` | Sağlık projesi; emergency rule kaçağı = klinik risk | M | 5 | 30 |
| 2 | **Duplicate scoring** — `scoring_v2.py` (pure fns) ve `agents/specialty_scorer.py` (singleton, JSON pre-load) | `app/scoring_v2.py`, `app/agents/specialty_scorer.py` | Specialty seçimi iki farklı yerden yapılıyor; davranış sapması sessiz olur | L | 4 | 9 |
| 3 | **`main.py` bare `except Exception: pass`** — line 81, 191, 235, 246 | `app/main.py:81,191,235,246` | Init/middleware başarısızlığı sessizce yutuluyor; production gözlemlenemez | S | 4 | 32 |

## P1 — Yüksek (1-2 sprint)

| # | Bulgu | Dosya | Neden | Eff | Risk | Skor |
|---|------|------|------|-----|------|------|
| 4 | **Rate-limit Redis→in-memory fallback gözlemlenemez** — 3 paralel bucket (triage / send-summary / admin), `_warn_redis_degraded_once()` sadece tek warning; multi-instance'ta in-memory race | `app/rate_limit.py:268-324` | Multi-instance Fly deploy'da limit aşımı sessiz; abuse riski | M | 4 | 18 |
| 5 | **Notifier fire-and-forget thread** — Slack/Discord webhook background thread, retry yok, lifespan join yok | `app/notifier.py:49-50` | Critical alert (rule rollback, guardrail fail) drop olabilir | S | 4 | 32 |
| 6 | **Test coverage gap** — `notifier.py`, `patchgen.py`, `patchgen_keywords.py`, `tuning_tasks.py`, `top_conditions_filter.py`, `runtime.py` için dedicated test yok | `backend/tests/` | Auto-patch + tuning loop guardrail'sız regress edebilir | M | 4 | 18 |
| 7 | **`agents/orchestrator.py` import patlaması** — 13 agent/service import 20 satırda; circular import + test izolasyonu zor | `app/agents/orchestrator.py:25-45` | Refactor maliyeti her geçen ay artıyor | M | 3 | 15 |
| 8 | **`specialty_scorer.py` module-level JSON load + sessiz fail** — schema validation yok | `app/agents/specialty_scorer.py:24-26` | Bozuk JSON / eksik dosya import-time crash; CI'da yakalanmaz, prod cold-start'ta patlar | S | 3 | 25 |

## P2 — Orta (fırsat doğunca)

| # | Bulgu | Dosya | Neden | Eff | Risk |
|---|------|------|------|-----|------|
| 9 | **`runtime.py` config path resolution `parent.parent.parent`** — symlink/non-standard layout sessiz fail | `app/runtime.py:31-38` | Deploy/Docker layout değişirse breaks | S | 2 |
| 10 | **`version_gating.py` lazy Prometheus import** — metrics yoksa sessizce skip | `app/version_gating.py:30-37` | Prod metrics drop, scrape boş; uyarı yok | S | 2 |
| 11 | **Hardcoded fallback specialty `"internal_gi"`** — iki yerde duplicate sabit | `app/scoring_v2.py:136`, `app/agents/specialty_scorer.py:274` | Taxonomy değişirse iki yer güncellenmeli | S | 2 |
| 12 | **Live tree → archive comment referansları** — `top_conditions_filter.py` docstring `orchestrator_v5.build_result`'a işaret ediyor | `app/top_conditions_filter.py` | Onboarding yanıltıcı; archive temizlense kırılır | S | 1 |

## P3 — Düşük (clean-up)

| # | Bulgu | Dosya | Eff |
|---|------|------|-----|
| 13 | `curated_conditions.json:7` içinde TODO string — JSON yorum desteklemiyor, dead string | `app/data/curated_conditions.json` | S |
| 14 | Repo root `openapi.yaml` deprecated; README'de "legacy reference contract" diyor — silinmeli veya gerçekten "legacy" header eklenmeli | `openapi.yaml` | S |
| 15 | `archive/` README iyi belgelenmiş ama live tree'den 1 referans var (madde 12); archive police "live tree'den import yok" diyor, comment'ler sayılmalı | `app/archive/README.md` | S |

---

## Faz planı (özellik geliştirmeyle paralel)

**Faz 1 (1 sprint, ~3-4 gün):**
- #3 (main.py except'leri) — explicit state tracking + observability counter; fail-fast yerine logged degradation flag
- #5 (notifier retry + lifespan join) — `httpx.AsyncClient` + 2 retry, FastAPI lifespan ile graceful shutdown
- #8 (specialty_scorer schema validation) — `jsonschema` veya manuel; startup'ta log + ENV check
- #1 (safety_guard consolidation) — interface kararı: tek dosyaya merge mı, yoksa "deterministic fast path + LLM enrichment" pipeline mı? **ADR konusu olabilir.**

**Faz 2 (1 sprint):**
- #4 (rate-limit observability) — Prometheus counter `rate_limit_fallback_total{bucket=}` + multi-instance constraint dokümante (zaten README'de var, kod tarafında metric yok)
- #6 (test coverage) — `notifier`, `patchgen`, `tuning_tasks` için happy path + 2 edge case (toplam ~15 test)
- #2 (scoring duplicate) — deprecation path: `scoring_v2.py` `agents/specialty_scorer.py`'a delegate edecek şekilde; 1 release sonrası silinir

**Faz 3 (sonraki):**
- #7 (orchestrator import refactor) — DI / factory pattern
- #9-12 (P2 clean-up) — fırsat tabanlı, refactor edilen dosyada değiştir

---

## Risk özeti (sağlık ürünü perspektifi)

- **Klinik risk:** #1 (duplicate safety_guard) — emergency hard-stop iki yerden geçiyor; biri yanlış güncellenirse rule kaçabilir.
- **Operasyonel risk:** #3, #5, #4 — sessiz başarısızlıklar; alert sistemi dahil çalışmıyorsa "her şey iyi görünüyor" yanılsaması.
- **Regresyon riski:** #6 — auto-patch / tuning loop test'siz; rule değişikliği prod'a sızabilir.

Audit tarihi: 2026-04-27. Bir sonraki audit önerisi: 2026-Q3.
