# Runbook: Rate-Limit Redis Down / Degraded

Risk lineage: `RISK_REGISTER_2026_04.md:H-3`. Tech-debt: `TECH_DEBT_2026_04.md:#4`.

## Quick checklist (incident → green)

- [ ] Sentry/Slack alert: `rate_limit_fallback_total > 0` (5dk window)
- [ ] Backend `/health` → `redis` field değerini gör
- [ ] Multi-instance deploy mu? (Fly.io scale > 1) — eğer evet, abuse pencere AKTİF
- [ ] Redis sağlayıcı status sayfası (Upstash, Fly Redis, vb.)
- [ ] Hızlı kontrol: `redis-cli -u $REDIS_URL PING` → `PONG` mu?
- [ ] Karar: provider'ı bekle / restart / yeni Redis URL / scale=1'e indir
- [ ] Post-incident ticket (alt)

## Symptoms

- Backend logs: `Redis unavailable; using in-memory rate limit: <error>` warning (`main.py:67-68`).
- Prometheus: `rate_limit_fallback_total{bucket=triage|send_summary|admin}` artar.
- `_warn_redis_degraded_once()` her instance'ta TEK warning üretir; sürekli spam yok ama **silent persistence** var (event'ten sonraki her dakika boyunca in-memory'de kalır).
- 429 oranı **azalır** (her process kendi bucket'ı = etkili limit N×). Abuse açısından bu kötü işaret.

## Severity

- **Single instance (Fly scale=1):** **P3** — In-memory bucket Redis ile fonksiyonel olarak benzer; sadece restart'ta sıfırlanır.
- **Multi-instance (Fly scale>1):** **P1** — Her process kendi bucket'ında; gerçek limit `N × MAX_REQ`. Abuse cuzdanı dolu.
- **Auth path (admin) etkilendiyse:** otomatik **P0** (admin endpoint brute-force riski).

## Immediate mitigation (< 5 min)

1. **Scale'i kontrol et:** `fly scale show -a triage-backend`. Eğer >1 ise:
   - **En hızlı çözüm:** `fly scale count 1 -a triage-backend` (geçici tek instance). Performans düşer ama abuse penceresi kapanır.
   - Alternatif: trafik düşükse beklemek; Redis recovery hızlıysa tercih edilebilir.
2. **Redis durumunu doğrula:**
   ```bash
   redis-cli -u $REDIS_URL PING            # PONG bekleniyor
   redis-cli -u $REDIS_URL INFO clients    # connected_clients sayısı
   ```
3. **Backend logs (Fly):**
   ```bash
   fly logs -a triage-backend | grep -i "redis\|rate_limit"
   ```
4. **Eğer credential rotation kazası:** `REDIS_URL` env değerini doğrula, `fly secrets list -a triage-backend`. Düzelt, redeploy.

## Data integrity

- **Bucket sayımları kayıp:** Redis döndüğünde sayaçlar in-memory'den senkronize EDİLMEZ. Yeni gelen istekler Redis'e yazılır, eski in-memory state çöp olur. Bu **abuse açısından kabul edilebilir** — yeni window zaten birkaç saniyede sıfırlanırdı.
- **429 oranı ani değişir:** Recovery'den sonra 429 oranı toparlanır; geçici "kullanıcı saldırıya uğradı mı" yanlış alarmları olabilir. Recovery sonrası 5dk içinde ignore.
- **Audit log:** Rate-limit event'leri Sentry'ye breadcrumb olarak akar; `triage_events`'e gitmez. Bu yüzden Supabase tarafında bir tutarsızlık ÇIKMAZ.

## Recovery

1. Redis döndüğünde, `/health` endpoint'i `redis: ok` dönmeli.
2. Backend restart **gerekli değil** — `rate_limit.py` her istekte connection sağlığını yeniden değerlendirir (lazy retry pattern). Yine de cleanlik için 1 instance restart önerilir.
3. Multi-instance'a geri çık: `fly scale count <prev_count> -a triage-backend`.
4. Prometheus: `rate_limit_fallback_total` 0'a düşmeli (en azından artmamalı). Counter sıfırlanmaz; oran (rate) düşer.
5. 24 saat içinde abuse pattern taraması: aynı IP'den anormal yoğunluk var mı? Sentry → "RateLimited" event aggregation.

## Troubleshooting

| Belirti | Olası neden | Çözüm |
|---------|-------------|-------|
| `PING` çalışıyor ama backend yine fallback'te | Connection pool exhaustion / TLS sertifika sorunu | Backend container restart; logs'ta `ConnectionPool` veya `SSL` hatası ara |
| Sadece bir bucket fallback'te (örn. admin) | Ayrı Redis DB / namespace sorunu | `REDIS_URL` path'inde `/0` `/1` `/2` ayrı mı kullanılıyor kontrol et |
| Recovery sonrası 429'lar dakikalarca devam ediyor | Eski in-memory bucket TTL | 60-90 saniye bekle; window aşımıyla temizlenir |

## Rollback

In-memory'ye düşmek zaten "rollback" durumudur — Redis'siz çalışmak güvenli ama sınırlı. Daha agresif rollback: `RATE_LIMIT_MAX_REQ`'i geçici **agresif düşür** (20 → 5) tüm bucket'larda; abuse penceresi kapanır.

## Escalation

| Durum | Kontak | Yöntem |
|-------|--------|--------|
| P0/P1 onaylanırsa | On-call eng | PagerDuty veya Slack `@here #dotshub-ops` |
| 30 dk içinde Redis dönmedi | Provider support | Upstash/Fly Redis dashboard ticket |
| Abuse pattern tespit edildi | Security lead | `SECURITY_INCIDENT.md` runbook'una geç |

## Post-incident ticket

- Süre, scale değeri, hangi bucket'lar etkilendi, abuse tespit edildi mi, eylem (`fly scale`, env reset).
- **Root cause kategorisi:** provider outage / network / credential / pool exhaustion.
- **Action item:** TECH_DEBT #4 (rate-limit observability) tamamlanmamışsa öncele.

## History

| Tarih | Çalıştıran | Notlar |
|-------|-----------|--------|
| _ilk yazıldığında çalıştırılmadı_ | | Şablon — ilk gerçek olay sonrası doldur |
