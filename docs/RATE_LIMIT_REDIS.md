# Rate limiting ve Redis (çok instance)

Bu belge, backend API’deki rate limiting davranışını, ortam değişkenlerini ve çok instance ortamında Redis kullanımını tek bağlamda açıklar. Uygulama kodu: `backend/app/rate_limit.py`, `backend/app/main.py`.

---

## 1. Özet

- **Varsayılan:** Rate limit sayaçları **process içi bellek**te (in-memory) tutulur. Tek instance veya geliştirme için yeterlidir.
- **Çok instance:** Birden fazla API process’i (worker, pod, replica) çalışıyorsa her process kendi sayaçlarına sahip olur; etkili limit instance sayısıyla çarpan olur. **Paylaşılan limit** için Redis kullanılır.
- **Yapılandırma:** `REDIS_URL` ayarlandığında ve Redis erişilebilir olduğunda tüm rate limit türleri (triage/feedback, send-summary, admin) Redis üzerinden çalışır; aksi halde in-memory kullanılır.

---

## 2. Nerede uygulanıyor?

| Endpoint / alan | Limit türü | Anahtar | Amaç |
|-----------------|------------|---------|------|
| `POST /v1/triage/turn`, `POST /v1/triage/feedback` | Genel API | `device_id` (header `x-device-id`) varsa `d:{device_id}`, yoksa `ip:{ip}` | Kullanıcı/cihaz başına triage ve geri bildirim isteklerini sınırlamak |
| `POST /v1/triage/send-summary`, `POST /v1/triage/export-summary` | Send-summary | `ip:{ip}` (IP başına) | E-posta gönderim ve export’u IP bazlı sınırlamak |
| `GET/POST /v1/admin/*` | Admin API | `ip:{ip}` (IP başına) | Admin isteklerini IP bazlı sınırlamak |

Genel ve send-summary limiti `rate_limit_middleware`, admin limiti `admin_rate_limit_middleware` ile uygulanır. Her iki middleware de yanıtta `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` header’larını set eder. Limit aşıldığında HTTP 429 dönülür.

---

## 3. Ortam değişkenleri

Tüm değerler uygulama başlangıcında okunur (env veya `backend/app/core/config.py` varsayılanları). Rate limit sabitleri `rate_limit.py` içinde `os.getenv` ile alınır.

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| **REDIS_URL** | Redis bağlantı URL’i. Boş veya `redis://` içermiyorsa Redis kullanılmaz; in-memory fallback. | `redis://localhost:6379/0` (config); test/CI’da boş bırakılarak in-memory kullanılabilir. |
| **RATE_LIMIT_WINDOW_SEC** | Triage/feedback için sabit pencere süresi (saniye). | `60` |
| **RATE_LIMIT_MAX_REQ** | Triage/feedback penceresi başına izin verilen maksimum istek (cihaz veya IP başına). | `20` |
| **SEND_SUMMARY_RATE_LIMIT_WINDOW_SEC** | Send-summary / export-summary pencere süresi (saniye). | `60` |
| **SEND_SUMMARY_RATE_LIMIT_MAX_REQ** | Send-summary penceresi başına IP başına maksimum istek. | `5` |
| **ADMIN_RATE_LIMIT_WINDOW_SEC** | Admin API pencere süresi (saniye). | `60` |
| **ADMIN_RATE_LIMIT_MAX_REQ** | Admin API penceresi başına IP başına maksimum istek. | `60` |

---

## 4. Algoritma ve Redis anahtarları

- **Pencere türü:** Sabit pencere (fixed window). Pencere süresi dolunca sayaç sıfırlanır (Redis’te key’e TTL verilir).
- **Redis key önekleri:** Çakışmayı önlemek için ayrı prefix kullanılır:
  - Genel: `rl:{key}` (örn. `rl:d:device-123`, `rl:ip:1.2.3.4`)
  - Send-summary: `rl_send_summary:{key}` (örn. `rl_send_summary:ip:1.2.3.4`)
  - Admin: `admin_rl:{key}` (örn. `admin_rl:ip:1.2.3.4`)
- **In-memory:** Her limit türü için process içi bir sözlük (key → zaman damgaları kuyruğu) kullanılır; pencere dışındaki eski damgalar temizlenir.

Redis kullanıldığında: `INCR` ile sayaç artırılır, ilk artışta key’e `expire(..., WINDOW_SEC)` atanır. Limit aşılırsa istek reddedilir ve sayaç geri alınır (`DECR`). Detay: `backend/app/rate_limit.py` içindeki `check_*_redis` fonksiyonları.

---

## 5. Başlangıç ve Redis bağlantısı

- **Lifespan** (`main.py`): Uygulama ayağa kalkarken `REDIS_URL` set ve `redis://` içeriyorsa `Redis.from_url()` ile bağlantı denenir, `ping()` başarılıysa `app.state.redis` set edilir ve log’a “Redis connected for rate limiting” yazılır.
- **Redis başarısız veya URL boş:** `app.state.redis = None`; middleware her istekte Redis yerine in-memory fonksiyonları kullanır. Bağlantı hatası durumunda log’a uyarı yazılır (“Redis unavailable; using in-memory rate limit”).
- **Kapanış:** Lifespan sonunda `app.state.redis.aclose()` çağrılır.

Yani **Redis zorunlu değildir**; yoksa veya hatalıysa uygulama in-memory ile çalışmaya devam eder.

---

## 6. Hata davranışı (fail-open)

- **Redis’e bağlanılamıyorsa (startup):** In-memory kullanılır; istekler reddedilmez.
- **Redis kullanılırken bir istekte Redis hatası (örn. timeout, bağlantı koptu):** `check_*_redis` fonksiyonları exception yakalar ve **isteği kabul eder** (remaining/reset değerleri tahmini döner). Yani rate limit **fail-open**: Redis arızalarında servis kesintisi yerine geçici olarak limit gevşer.

Bu davranış kodu: `rate_limit.py` içinde `except Exception: return True, ...` blokları.

---

## 7. Yanıt header’ları

Rate limit uygulanan isteklerde (başarılı veya 429):

- **X-RateLimit-Limit:** Pencere başına maksimum istek (sayı).
- **X-RateLimit-Remaining:** Kalan izin verilen istek sayısı (429’da 0).
- **X-RateLimit-Reset:** Pencere sıfırlanana kalan saniye (tahmini).

429 gövdesi örneği: `{"detail": "Rate limit exceeded", "reset_in_sec": 42}` (genel/send-summary) veya `{"detail": "Admin API rate limit exceeded", "reset_in_sec": 42}` (admin).

---

## 8. Yerel geliştirme ve test

- **Redis kullanmadan:** `REDIS_URL` boş bırakılır veya export edilmez; in-memory kullanılır. Regression testlerinde genelde `REDIS_URL=""` tercih edilir (ör. `backend/scripts/run_backend_regression.py`).
- **Redis ile yerel test:** Örneğin  
  `docker run -d -p 6379:6379 --name redis-ratelimit redis:7-alpine`  
  Sonrasında `REDIS_URL=redis://localhost:6379/0` ile API’yi başlatmak yeterli.

---

## 9. Üretim notları

- **Çok instance (worker/pod):** Paylaşılan limit için `REDIS_URL` mutlaka ayarlanmalı (örn. managed Redis servisi).
- **Güvenlik:** Redis şifre veya TLS kullanıyorsa URL içinde verilir (örn. `redis://:password@host:6379/0`, `rediss://...`).
- **Yüksek kullanılabilirlik:** Redis tarafında cluster/sentinel kullanımı uygulama kodunu değiştirmez; `redis-py` uyumlu bir URL yeterlidir.
- **Bağımlılık:** `backend/requirements.txt` içinde `redis>=5.2` (async kullanım: `redis.asyncio`).

---

## 10. Kod referansları

| Konu | Dosya / yer |
|------|-------------|
| Limit sabitleri, in-memory ve Redis fonksiyonları | `backend/app/rate_limit.py` |
| Redis bağlantısı, lifespan | `backend/app/main.py` (lifespan) |
| Genel ve send-summary middleware | `backend/app/main.py` (`rate_limit_middleware`) |
| Admin middleware | `backend/app/main.py` (`admin_rate_limit_middleware`) |
| Config varsayılanı (REDIS_URL) | `backend/app/core/config.py` |

---

**Özet:** Tek instance için Redis opsiyonel; çok instance’ta paylaşılan limit için `REDIS_URL` set edin. Tüm detaylar bu belge ve yukarıdaki dosyalarda tutarlı şekilde geçerlidir.
