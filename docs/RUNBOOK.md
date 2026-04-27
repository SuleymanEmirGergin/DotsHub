# Triaige — Operasyonel Müdahale Rehberi (RUNBOOK)

**Son güncelleme:** 2026-04-20 · **Sahip:** emirgergin21@gmail.com

Bu doküman bir alert düştüğünde / kullanıcı bir sorun bildirdiğinde **ne yapılacağının** sıralı cevabıdır. Bilmediğin komutları yazmaz — hepsi mevcut setup'ı kullanır. Panik anında açılır, okunur, uygulanır.

---

## 🚨 TL;DR — Tek kutu acil komutlar

Sistem "yanıyor" gibi hissettiğinde, önce **durumu oku**:

```bash
# 1. Backend canlı mı? Machine state + health check
flyctl status --app triaige-backend

# 2. Son 200 log satırı (hata avı)
flyctl logs --app triaige-backend --no-tail

# 3. Public health check (kendi laptop'undan)
curl -sS https://triaige-backend.fly.dev/health | jq

# 4. Supabase reachable mı? (above cevabın içinde: "supabase":"ok" vs. "unreachable")

# 5. Son deploy neydi?
flyctl releases --app triaige-backend | head -5
```

Hızlı karar ağacı:

- `flyctl status` machine **stopped / crashed** → [Flow A — Backend Crash](#flow-a--backend-crash-loop)
- `/health` **5xx veya timeout** → [Flow B — Backend 5xx Spike](#flow-b--backend-5xx-spike)
- `/health` `supabase:"unreachable"` → [Flow C — Supabase Outage](#flow-c--supabase-outage)
- Dashboard "CORS blocked" / login koptu → [Flow D — Frontend Connectivity](#flow-d--frontend-connectivity)
- Kullanıcı yok ama alert'te "rate-limit denied %X" → [Flow E — Rate-Limit Abuse](#flow-e--rate-limit-abuse-or-growth)

---

## İletişim & Rol

| Rol | Kişi / Kanal |
|-----|--------------|
| Primary on-call | Emir Gergin (`emirgergin21@gmail.com`) |
| Eskalasyon | (operator ekledikçe güncellenir) |
| Status sayfası | (gelecekte — `status.triaige.com` planlı) |
| Kullanıcı iletişimi | App Store / Play Store support email |
| Infra tedarikçiler | Fly.io support, Supabase support, Vercel support |

Alert düştüğünde **önce on-call'u tetikle** (şu an tek kişi), sonra playbook'u çalıştır.

---

## Alert → Playbook Eşlemesi

Grafana Cloud'dan düşen alert'ler (`config/grafana/alerts/backend-health.yaml`):

| Alert | Severity | Playbook |
|-------|----------|----------|
| `BackendHighErrorRate` (5xx > 2% × 5m) | critical | [Flow B](#flow-b--backend-5xx-spike) |
| `BackendScrapeDown` (`up == 0` × 2m) | critical | [Flow A](#flow-a--backend-crash-loop) |
| `BackendLatencyRegression` (p95 > 2s × 10m) | warning | [Flow G — Latency](#flow-g--latency-regression) |
| `RateLimitDeniedRateHigh` (>5% × 15m) | warning | [Flow E](#flow-e--rate-limit-abuse-or-growth) |
| `LLMNluRateLimitSaturated` (>0 × 10m) | warning | [Flow F — LLM NLU](#flow-f--wiro-llm-nlu-outage-or-quota) |
| `EmergencyEnvelopeSpike` (3× baseline × 15m) | warning | [Flow H — Triage Rule Regression](#flow-h--triage-rule-regression) |
| `CapabilityGateStripRateUnusuallyHigh` (>50% × 24h) | info | `docs/OPS_VERSION_GATE_ROLLOUT.md` — warn→block rollout kararı |

Alert'ler **dün kurulu, bugün canlı** — 401 token fix'i yapıldığında sırlar da bağlanır, bu liste tam çalışır duruma geçer.

---

## Flow A — Backend Crash Loop

**Sinyal:** `BackendScrapeDown` · `flyctl status` → `stopped` · log'da `Main child exited normally with code: 1` + Python traceback.

### Adım 1 — Hatayı oku

```bash
flyctl logs --app triaige-backend --no-tail
```

Son traceback'in **en alt satırlarını** oku:
- `json.decoder.JSONDecodeError: Expecting value` → Bir secret (CORS_ORIGINS, ...) yanlış formatta. `flyctl ssh console` + `env | grep <VAR>` ile kontrol.
- `ModuleNotFoundError` → Dockerfile'da eksik dep. Son deploy'dan sonra requirements bozulmuşsa rollback.
- `sqlite3.OperationalError: unable to open database file` → `DATABASE_URL` in-memory değil. `flyctl secrets set DATABASE_URL="sqlite+aiosqlite:///:memory:"`.
- `redis.exceptions.ConnectionError` → Upstash Redis erişilemiyor. Fallback in-memory otomatik devreye girer; bu **blocker değil** ama log'lar kirli.

### Adım 2 — Hızlı rollback (5 dk)

En basit müdahale: son bilinen-iyi deploy'a dön.

```bash
flyctl releases --app triaige-backend
# çıktıda yeşil bir önceki release id'sini seç
flyctl releases rollback <release-id> --app triaige-backend
```

Supabase schema değişikliği içeren bir deploy'dan geri dönüyorsan, `backend/sql/` altındaki en son migration'ı geriye alıp almayacağını **mutlaka kontrol et** — kod rollback ediyor ama DB şeması rollback etmiyor.

### Adım 3 — Machine elle başlat (son çare)

```bash
flyctl machines list --app triaige-backend
flyctl machines start <id> --app triaige-backend
flyctl logs --app triaige-backend   # live tail; Ctrl+C ile çık
```

Hâlâ crash ederse [Flow I — Nuke & Pave](#flow-i--nuke--pave) son adım.

---

## Flow B — Backend 5xx Spike

**Sinyal:** `BackendHighErrorRate` · `curl /health` 500 · Sentry'de exception rush (eğer DSN set'liyse).

### Adım 1 — Son deploy / son değişiklik

```bash
flyctl releases --app triaige-backend | head -5
# Son release 30 dk içindeyse: yüksek ihtimalle yeni kod kırdı
```

Eğer son 30 dk içinde deploy yapıldıysa → **rollback** ([Flow A Adım 2](#adım-2--hızlı-rollback-5-dk)).

### Adım 2 — Sentry'de exception filtrele

`https://sentry.io/organizations/<org>/issues/?project=<id>&statsPeriod=1h` — son 1 saatteki en sık exception:
- `sqlalchemy.exc.*` → DB sorunu → [Flow C](#flow-c--supabase-outage)
- `httpx.ConnectTimeout` + Wiro URL → [Flow F](#flow-f--wiro-llm-nlu-outage-or-quota)
- Pydantic validation → client'tan kötü payload; ya regresyon ya saldırı

Sentry DSN henüz set edilmediyse: `flyctl logs --app triaige-backend --no-tail` + `Select-String -Pattern "ERROR|Exception"` (PowerShell) ya da `| grep -iE "error|exception"` (Unix).

### Adım 3 — Canlı trafiğe etki

Eğer 5xx + downstream (Supabase) OK + sadece belirli endpoint'te patlıyorsa: **feature flag** devreye al (ileride; şu an backend'de değişken manuel):
- `LLM_NLU_ENABLED=false` → Wiro'yu devreden çıkar
- `RATE_LIMIT_ALERT_ENABLED=false` → gürültü azalt

```bash
flyctl secrets set LLM_NLU_ENABLED=false --app triaige-backend
```

---

## Flow C — Supabase Outage

**Sinyal:** `/health` → `"supabase":"unreachable"` · tüm triage turn'leri 500 · Sentry'de `httpx.HTTPStatusError` SupabaseUrl içeriyor.

### Adım 1 — Supabase status sayfası

https://status.supabase.com — sistem outage mı, yoksa sadece bizim proje mi?

### Adım 2 — Secret check

```bash
flyctl ssh console --app triaige-backend
echo "URL=$SUPABASE_URL"
echo "KEY_LEN=${#SUPABASE_SERVICE_ROLE_KEY}"   # ~200+ karakter normal
exit
```

URL boş / anon key kısa ise → secret yeniden yatır:

```bash
flyctl secrets set --app triaige-backend \
  "SUPABASE_URL=https://<your-project>.supabase.co" \
  "SUPABASE_SERVICE_ROLE_KEY=<service-role-jwt>"
```

### Adım 3 — Direct PG fallback (eğer REST down ama PG up)

Supabase PostgREST tarafı tıkalı ama direct PG sağlıklı ise (pek yaygın değil):
- `SUPABASE_DB_URL` veya `SUPABASE_DB_POOLER_URL` secret'ı zaten yatırılmış (bkz `flyctl secrets list`).
- Backend koduna direct PG'ye düşüş henüz yok — uzun outage'ta feature-flag ekleme notu.

### Adım 4 — Kullanıcı iletişimi

Supabase 30+ dk out ise:
- Mobile app'de "maintenance" banner göster (feature flag ile)
- Dashboard'da üst bar "Sistem bakımda" 

Bu iki feature flag şu an **yok** — gelecek iyileştirme.

---

## Flow D — Frontend Connectivity

**Sinyal:** Dashboard login ol'muyor / "CORS blocked" browser console'da / mobile "NETWORK_ERROR".

### Adım 1 — Backend canlı mı

```bash
curl -sS https://triaige-backend.fly.dev/health
```

Yanıt gelmiyorsa → [Flow A](#flow-a--backend-crash-loop).

### Adım 2 — CORS_ORIGINS içinde gerçek URL var mı

```bash
flyctl ssh console --app triaige-backend
python -c "from app.core.config import settings; print(settings.cors_origins_list)"
exit
```

Vercel URL (`https://triaige.vercel.app`) veya mobile callback origin listede yoksa → ekle:

```bash
flyctl secrets set --app triaige-backend \
  "CORS_ORIGINS=http://localhost:3000,http://localhost:8081,https://triaige.vercel.app,https://yeni-url.vercel.app"
```

> CSV format. JSON array de kabul ediliyor ama PowerShell'de tırnak drama eder. CSV tercih edilir.

### Adım 3 — Mobile `API_BASE` doğru mu

Mobile app'te prod URL'i okumak:
- `mobile/.env` → `API_BASE=https://triaige-backend.fly.dev` olmalı
- Expo'yu `--clear` ile restart: `cd mobile && npx expo start --clear`

### Adım 4 — Supabase Auth Redirect

Magic link callback `localhost:3000`'e dönüyorsa:
- Supabase Dashboard → Authentication → URL Configuration → **Site URL**: `https://triaige.vercel.app`
- **Redirect URLs**: `https://triaige.vercel.app/**` + `http://localhost:3000/**` (dev için)

---

## Flow E — Rate-Limit Abuse or Growth

**Sinyal:** `RateLimitDeniedRateHigh` · `rate_limit_hits_total{outcome="denied"}` > %5.

### Adım 1 — Hangi bucket tıkalı?

Grafana Cloud → Explore:
```promql
sum by (bucket) (rate(rate_limit_hits_total{outcome="denied"}[10m]))
```

- `default` → IP/device başına 60s/20req cap (genel API) → çoğunlukla abuse
- `admin` → admin endpoint cap → genelde bizim hata
- `send_summary` → email/PDF 5/min → normal spike
- `llm_nlu` → global Wiro quota → [Flow F](#flow-f--wiro-llm-nlu-outage-or-quota)

### Adım 2 — Abuse mu büyüme mi?

Sentry / Fly logs → hangi IP'ler en çok? Tek IP 100req/s → muhtemelen abuse. 20 IP'ye dağılmış → gerçek büyüme.

### Adım 3 — Karar

**Abuse:**
- Kısa vade: IP'yi Fly edge'den block — mümkün değil şu an (CDN yok); backend içinde `CORS_ORIGINS` dışındaki origin'leri filtreler ama IP bazında değil.
- Uzun vade: Cloudflare / CDN önüne koymak gerek (gelecek iyileştirme).

**Büyüme:**
```bash
# Mevcut: RATE_LIMIT_MAX_REQ=20 / WINDOW=60
flyctl secrets set --app triaige-backend \
  RATE_LIMIT_MAX_REQ=50 \
  RATE_LIMIT_WINDOW_SEC=60
```

`ADMIN_RATE_LIMIT_MAX_REQ` ve `SEND_SUMMARY_RATE_LIMIT_MAX_REQ` aynı prensiple.

---

## Flow F — Wiro (LLM NLU) Outage or Quota

**Sinyal:** `LLMNluRateLimitSaturated` veya Sentry'de Wiro HTTP timeout/401.

### Adım 1 — Wiro status

https://wiro.ai (yoksa Twitter / kendi dashboard'ın). LLM quota mı exhausted, endpoint mi down?

### Adım 2 — Backend tarafı fallback

Backend'de `LLM_NLU_ENABLED=true` ise Wiro'yu NLU için kullanıyor. Deterministic canonical extract her zaman çalışır (fallback). Yani Wiro down olsa bile **triage akışı kırılmaz, sadece NLU zenginliği düşer**.

Hızlı müdahale — Wiro'yu kapat:

```bash
flyctl secrets set --app triaige-backend LLM_NLU_ENABLED=false
```

Deploy sonrası 30 sn içinde tüm turn'ler deterministic NLU'ya düşer. Triage doğruluğu biraz düşer (canonical extraction daha kısıtlı) ama hiçbir şey 500 atmaz.

### Adım 3 — Quota artırımı

`LLM_NLU_RATE_LIMIT_MAX_REQ` backend'de (default 30/dk). Wiro plan'ı quota'yı belirler, ayrı iş.

---

## Flow G — Latency Regression

**Sinyal:** `BackendLatencyRegression` (p95 > 2s × 10m).

### Adım 1 — Kaynağı bul

Grafana dashboard → "HTTP latency p95" panel. Hangi endpoint?
- `/v1/triage/turn` → LLM NLU yavaş → [Flow F](#flow-f--wiro-llm-nlu-outage-or-quota)
- `/admin/sessions` → Supabase pagination yavaş → DB query optimize
- `/health` → Supabase REST latency → [Flow C](#flow-c--supabase-outage)

### Adım 2 — Son deploy

```bash
flyctl releases --app triaige-backend | head -5
```

Son deploy'da yeni bir N+1 query yazdıysan → geri rollback.

### Adım 3 — Makineyi büyüt (kısa vade)

```bash
flyctl scale vm shared-cpu-2x --memory 1024 --app triaige-backend
```

Bu tek seferlik kısayol. Asıl çözüm kod + query optimize.

---

## Flow H — Triage Rule Regression

**Sinyal:** `EmergencyEnvelopeSpike` (3× baseline × 15m). Yani ani EMERGENCY count artışı — ya gerçek felaket ya config hatası.

### Adım 1 — Son config değişikliği

```bash
git log --since="6 hours ago" -- config/emergency_rules.json
git log --since="6 hours ago" -- backend/app/emergency_router.py
```

Son 6 saatte değişiklik var mı? Varsa → eski `config/emergency_rules.json` değerine dön, deploy.

### Adım 2 — Envelope breakdown

```promql
sum by (envelope_type) (rate(triage_envelope_total[15m]))
```

EMERGENCY abnormally artmış ama RESULT/QUESTION aynı → rule over-triggering. `config/emergency_rules.json` içindeki son eklenen rule'u şüphelen.

### Adım 3 — Değişikliği geri al

```bash
git checkout <previous-commit> -- config/emergency_rules.json
git commit -m "revert: emergency rule regression (see alert)"
git push
# Backend'de config baked olduğu için redeploy gerek:
flyctl deploy --app triaige-backend
```

---

## Flow I — Nuke & Pave

Son çare. Tüm machines'i yok et + fresh deploy.

```bash
flyctl machines list --app triaige-backend
# her machine için:
flyctl machines destroy <id> --app triaige-backend --force
flyctl deploy --app triaige-backend
```

Secret'lar app-level'da kalır → kaybolmaz. `flyctl deploy` yeni machine yaratır, fly.toml'daki `min_machines_running=1` ile tek machine ayağa kalkar.

⚠️ Bu 5-10 dk downtime demek. Sadece başka çözüm iflas ettiğinde.

---

## Komut Kataloğu

### Fly.io

```bash
# Durum
flyctl status --app triaige-backend
flyctl machines list --app triaige-backend
flyctl checks list --app triaige-backend

# Log
flyctl logs --app triaige-backend --no-tail    # son 200 satır
flyctl logs --app triaige-backend              # live tail (Ctrl+C)

# Deploy
flyctl deploy --app triaige-backend
flyctl releases --app triaige-backend
flyctl releases rollback <id> --app triaige-backend

# Secret
flyctl secrets list --app triaige-backend
flyctl secrets set --app triaige-backend "KEY=value"
flyctl secrets unset --app triaige-backend KEY

# SSH
flyctl ssh console --app triaige-backend --select

# Scale
flyctl scale count 1 --app triaige-backend
flyctl scale vm shared-cpu-2x --memory 1024 --app triaige-backend

# Machine-level
flyctl machines start <id> --app triaige-backend
flyctl machines restart <id> --app triaige-backend
flyctl machines destroy <id> --app triaige-backend --force
```

### Health probes (operator laptop'undan)

```bash
# Public health
curl -sS https://triaige-backend.fly.dev/health | jq
curl -sS https://triaige-backend.fly.dev/v1/config/features | jq
curl -sS https://triaige-backend.fly.dev/metrics | head -30

# Admin stats (ADMIN_API_KEY gerek)
curl -sS -H "x-admin-key: $ADMIN_API_KEY" \
  https://triaige-backend.fly.dev/admin/stats/overview | jq
```

### Supabase

```bash
# SQL editor: supabase.com/dashboard → proje → SQL Editor
# Auth URL config: Authentication → URL Configuration
# Kullanıcılar: Authentication → Users

# Direct PG (acil debug):
psql "$SUPABASE_DB_URL"   # veya pooler URL
```

### Vercel

```bash
# Redeploy (UI): Deployments → en son → ⋯ → Redeploy
# Env var değişiklikleri sonrası mutlaka redeploy — Next.js build-time'da inline ediyor
# CLI alternatif:
vercel --prod --force
```

### Grafana Cloud

- Dashboards: `https://<slug>.grafana.net/dashboards`
- Alerts: `Alerting → Alert rules → triaige-backend`
- Explore: `Explore` → query: `up{service="backend"}`
- Access Policies (token rotate): `My Account → Access Policies`

---

## Incident Communication Şablonu

Her P0/P1 incident için:

```
[Tespit zamanı] 2026-04-20 14:30 UTC
[Etki] Backend 5xx rate %8, dashboard + mobile kullanıcıları etkilendi
[Root cause ilk hipotez] Son deploy (commit abc123) yeni DB query ekledi, N+1
[Mitigation] Rollback yapıldı (<id>), error rate <1%'e düştü
[Süre] 14:30 → 14:52 UTC = 22 dk
[Kullanıcı etkisi tahmini] ~X session başarısız oldu (Supabase count)
[Follow-up] N+1'i kodda çöz, feature flag arkasına al, tekrar deploy
```

Slack / email template olarak kullanılabilir. Kullanıcı sayıları için Supabase'de:

```sql
SELECT COUNT(*) 
FROM triage_sessions 
WHERE created_at BETWEEN '2026-04-20 14:30' AND '2026-04-20 14:52'
  AND envelope_type = 'ERROR';
```

---

## Post-Mortem Şablonu

İncident 30 dk+ sürdüyse post-mortem yaz. `docs/incidents/YYYY-MM-DD-kisa-aciklama.md`:

```markdown
# Incident — 2026-04-20 — Backend 5xx Spike

## Özet
22 dakika süren 5xx spike. Kök neden: yeni deploy'daki N+1 query.

## Zaman Çizelgesi (UTC)
- 14:25 — Deploy commit abc123 (feature X)
- 14:30 — BackendHighErrorRate alert düştü
- 14:31 — On-call (Emir) Slack'ten görürldü
- 14:33 — `flyctl logs` → DB timeout gördü
- 14:40 — Rollback başladı
- 14:45 — Rollback tamamlandı, error rate düştü
- 14:52 — %1 altına indi, alert kapandı

## Neden Oldu
`feature X`'de eklenen `get_user_sessions()` her oturum için ayrı Supabase call attı. 50 oturumlu bir liste için 50 round-trip.

## Neden Daha Erken Yakalanmadı
Staging'de test verisi küçüktü, N+1 görünmedi. Perf benchmark yoktu.

## Aksiyon
1. `feature X`'i N+1'siz re-implement et (tek query, JOIN)
2. Staging seed'ini gerçekçi boyuta çıkar (>1000 row)
3. Backend'e `pytest-benchmark` ekle, p99 regression threshold CI'da

## Kimin Hatası
Süreç eksikliği. Staging perf test yoktu.
```

Blameless tutmaya dikkat — neden süreç hatası veya tooling eksikliği olduğunu bul.

---

## Bakım Takvimi

| Periyot | İş | Referans |
|---------|-----|---------|
| Haftalık | Grafana dashboard kontrol — anormal trend | Grafana UI |
| Aylık | Alert rule'ları gözden geçir | `config/grafana/alerts/*.yaml` |
| 3 ay | Credential rotation (admin key, Wiro key) | `docs/OPS_ROTATION.md` |
| 3 ay | RUNBOOK.md revizyon — güncel komutlar, yeni senaryolar | Bu dosya |
| 6 ay | Fly image + requirements.txt sec upgrade | `backend/requirements.txt`, Dockerfile'lar |
| Yıllık | Backup stratejisi review (Supabase PITR, export snapshot) | Supabase Dashboard → Backups |

---

## İlgili Dokümanlar

- [`docs/DEPLOY_FLY.md`](DEPLOY_FLY.md) — ilk deploy + Fly hazırlık
- [`docs/DEPLOY_AND_ENV.md`](DEPLOY_AND_ENV.md) — tüm env var referans
- [`docs/OBSERVABILITY.md`](OBSERVABILITY.md) — Grafana Cloud + metrics detay
- [`docs/OPS_ROTATION.md`](OPS_ROTATION.md) — credential rotasyon prosedürü
- [`docs/OPS_STAGING_SETUP.md`](OPS_STAGING_SETUP.md) — staging env
- [`docs/OPS_VERSION_GATE_ROLLOUT.md`](OPS_VERSION_GATE_ROLLOUT.md) — mobile version enforcement
