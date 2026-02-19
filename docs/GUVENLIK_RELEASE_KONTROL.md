# Release öncesi güvenlik kontrolü

7. madde (RELEASE_CHECKLIST) için kısa rehber: production’da CORS, güvenlik header’ları ve admin rate limit’in doğru yapılandırıldığını doğrulayın.

---

## 1. CORS — Production’da gerçek origin’ler

**Kontrol:** Production ortamında `CORS_ORIGINS` localhost listesi **değil**, yalnızca kullandığınız uygulama ve dashboard URL’leri olmalı.

| Nerede | Detay |
|--------|--------|
| **Backend config** | `backend/app/core/config.py`: `CORS_ORIGINS` (JSON array). Varsayılan: localhost:8081, 19006, 3000. |
| **Env** | Production’da `CORS_ORIGINS='["https://app.example.com","https://dashboard.example.com"]'` benzeri gerçek origin listesi. |
| **Doküman** | [DEPLOY_AND_ENV.md](DEPLOY_AND_ENV.md) — CORS_ORIGINS tablosu. README “CORS_ORIGINS” bölümü. |

**Yapılacak:** Production `.env` veya ortam değişkeninde `CORS_ORIGINS` değerinin sadece izin vermek istediğiniz origin’leri içerdiğini kontrol edin; `*` veya geniş localhost listesi kullanmayın.

---

## 2. Güvenlik header’ları (HSTS, X-Content-Type-Options vb.)

**Kontrol:** Backend production’da çalışırken güvenlik header’ları ekleniyor mu; HTTPS kullanılıyor mu?

| Nerede | Detay |
|--------|--------|
| **Backend middleware** | `backend/app/middleware/security_headers.py`: `APP_ENV=production` iken eklenir. |
| **Header’lar** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Strict-Transport-Security` (HSTS). |
| **Doküman** | [SECURITY_HEADERS_INTEGRATION.md](SECURITY_HEADERS_INTEGRATION.md), [PRIVACY_AND_SECURITY.md](PRIVACY_AND_SECURITY.md). |

**Yapılacak:** Production’da `APP_ENV=production` olduğundan emin olun. HSTS sadece HTTPS ile anlamlıdır; reverse proxy (nginx, Vercel vb.) HTTPS sonlandırıyorsa header’lar güvenle eklenebilir. İsteğe bağlı: bir production isteğinde response header’larını kontrol edin.

---

## 3. Admin API rate limit

**Kontrol:** Admin API için rate limit açık mı, dokümante mi?

| Nerede | Detay |
|--------|--------|
| **Backend** | `backend/app/rate_limit.py`: `ADMIN_WINDOW_SEC`, `ADMIN_MAX_REQ`. `main.py`: `admin_rate_limit_middleware` `/v1/admin/*` için. |
| **Env** | `ADMIN_RATE_LIMIT_WINDOW_SEC` (varsayılan 60), `ADMIN_RATE_LIMIT_MAX_REQ` (varsayılan 60 → 60 istek/dakika per IP). |
| **Doküman** | README “Admin” ve env tablosu; [API_EXAMPLES.md](API_EXAMPLES.md) — Admin rate limit notu. |

**Yapılacak:** Production’da admin rate limit’in etkin olduğunu (middleware ekli, Redis kullanılıyorsa admin limit’in de Redis’e gittiğini) ve gerekiyorsa limit değerlerinin dokümandaki ile uyumlu olduğunu doğrulayın. Ek IP kısıtı kullanıyorsanız (örn. firewall) dokümante edin.
