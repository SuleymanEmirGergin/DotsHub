# Güvenlik Header'ları Entegrasyonu

`app/middleware/security_headers.py` production'da aşağıdaki header'ları ekler:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` (sadece production)

## main.py'ye ekleme

1. Lifespan içinde `app.state.app_env = settings.APP_ENV` atayın (middleware env'e göre karar veriyor).
2. CORS'dan sonra middleware ekleyin:

```python
from app.middleware.security_headers import SecurityHeadersMiddleware

# CORS'dan sonra:
app.add_middleware(SecurityHeadersMiddleware)
```

Not: HSTS sadece HTTPS kullandığınızda etkinleştirilir; production'da reverse proxy HTTPS sağlıyorsa bu header güvenlidir.
