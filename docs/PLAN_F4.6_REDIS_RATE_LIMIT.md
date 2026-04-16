# F4.6 Plan: Backend Redis rate limit dokümantasyonu

**Tamamlandı.** Detaylı bağlam için tek kaynak: [docs/RATE_LIMIT_REDIS.md](RATE_LIMIT_REDIS.md). README’de rate limiting bölümüne link eklendi; PLAN_SONRAKI_FAZ F4.6 güncellendi.

---

## Mevcut durum

- **Kod:** Redis desteği zaten var.
  - `backend/app/rate_limit.py`: In-memory (varsayılan) + Redis fonksiyonları (genel triage/feedback, send-summary, admin).
  - `backend/app/main.py`: Startup’ta `REDIS_URL` set ve geçerliyse Redis’e bağlanıyor; middleware `app.state.redis` varsa Redis, yoksa in-memory kullanıyor. Redis başarısız olursa in-memory’e düşüyor (fail-open), log’a uyarı yazılıyor.
- **README.md:** "Rate limiting (multi-instance)" paragrafı `REDIS_URL` ve çok instance davranışını anlatıyor.
- **Bağımlılık:** `backend/requirements.txt` içinde `redis>=5.2` mevcut.

Yani **uygulama tarafı tamam**; F4.6 sadece dokümantasyonu netleştirmek / tek yerde toplamak.

---

## Hedef

Çok instance ortamında rate limit’in Redis ile nasıl kullanıldığını ve yapılandırmayı tek dokümanda toplamak; isteğe bağlı olarak README’ye kısa referans eklemek.

---

## Adımlar

### 1. `docs/RATE_LIMIT_REDIS.md` oluştur (önerilen)

İçerik önerisi:

- **Özet:** Rate limit varsayılan olarak process içi bellek kullanır; birden fazla API instance’ı (worker/pod) varsa limitler instance başına olur. Paylaşılan limit için `REDIS_URL` ayarlanır.
- **Env değişkenleri tablosu:**

  | Değişken | Açıklama | Varsayılan |
  |----------|----------|------------|
  | `REDIS_URL` | Redis bağlantı URL’i. Boş veya geçersizse in-memory kullanılır. | `redis://localhost:6379/0` (config); boş bırakılırsa in-memory |
  | `RATE_LIMIT_WINDOW_SEC` | Triage/feedback pencere süresi (sn) | 60 |
  | `RATE_LIMIT_MAX_REQ` | Triage/feedback pencere başına max istek | 20 |
  | `SEND_SUMMARY_RATE_LIMIT_WINDOW_SEC` | Send-summary pencere (sn) | 60 |
  | `SEND_SUMMARY_RATE_LIMIT_MAX_REQ` | Send-summary max istek (IP başına) | 5 |
  | `ADMIN_RATE_LIMIT_WINDOW_SEC` | Admin API pencere (sn) | 60 |
  | `ADMIN_RATE_LIMIT_MAX_REQ` | Admin API max istek (IP başına) | 60 |

- **Davranış:** Redis erişilemezse uygulama in-memory’e düşer, başlangıçta log’a uyarı yazılır; istek reddedilmez (fail-open).
- **Referans:** Detaylı mantık `backend/app/rate_limit.py` ve `backend/app/main.py` (lifespan + middleware).

İsteğe bağlı: “Yerel test için Redis” (örn. `docker run -d -p 6379:6379 redis:7-alpine`) tek cümle.

### 2. README.md’yi güncelle (isteğe bağlı)

Mevcut “Rate limiting (multi-instance)” paragrafının sonuna ekle:

- “Ayrıntılı env değişkenleri ve davranış için bkz. [docs/RATE_LIMIT_REDIS.md](docs/RATE_LIMIT_REDIS.md).”

### 3. PLAN_SONRAKI_FAZ.md F4.6 satırını güncelle

F4.6 tamamlandığında tabloda:

- Örnek: “Tamamlandı: docs/RATE_LIMIT_REDIS.md eklendi; README’ye link verildi.”

---

## Alternatif (minimal)

Sadece README’deki mevcut paragrafı yeterli sayıp F4.6’yı “Tamamlandı: README’de zaten dokümante (Rate limiting multi-instance).” şeklinde işaretlemek. Ayrı dosya açmak istenmiyorsa bu yeterli.

---

## Özet

| Adım | Ne yapılacak | Zorunlu? |
|------|----------------|----------|
| 1 | `docs/RATE_LIMIT_REDIS.md` oluştur (env tablosu + davranış) | Önerilen |
| 2 | README’de “Rate limiting” bölümüne doc linki ekle | İsteğe bağlı |
| 3 | PLAN_SONRAKI_FAZ.md F4.6’yı tamamlandı olarak güncelle | Evet (F4.6 bitince) |

Kod veya dependency değişikliği gerekmez; sadece dokümantasyon.
