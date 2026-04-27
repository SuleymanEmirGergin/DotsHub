# TriAIge — Kurulum ve Çalıştırma Rehberi

Bu dokümanda projeyi sıfırdan ortam dosyaları, backend, dashboard, mobil ve Supabase entegrasyonu ile nasıl hazırlayıp çalıştıracağınız adım adım yer alır.

---

## 1. Gereksinimler

| Bileşen    | Gereksinim |
|-----------|------------|
| Python    | 3.10+ (backend) |
| Node.js   | 18+ (dashboard, mobil) |
| npm       | 9+ |
| Redis     | Opsiyonel; Docker ile veya boş bırakılırsa backend in-memory rate limit kullanır |
| Supabase  | Hesap + proje (triyaj, oturum, admin girişi için) |

---

## 2. Ortam Dosyalarını Hazırlama

### 2.1 Backend (`backend/.env`)

`backend` klasöründe `.env` yoksa `.env.example` dosyasını kopyalayın:

**Windows (PowerShell):**
```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

**Linux/macOS:**
```bash
cd backend
[ -f .env ] || cp .env.example .env
```

Sonra `.env` içinde en az şunları **gerçek değerlerle** güncelleyin:

| Değişken | Açıklama | Örnek / not |
|----------|----------|-------------|
| `SUPABASE_URL` | Supabase proje URL | `https://PROJE_REF.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase **service_role** (gizli) anahtar | Supabase Dashboard → Settings → API |
| `ADMIN_API_KEY` | Admin API için ortak parola | Dashboard ile aynı olmalı |
| `WIRO_API_KEY`, `WIRO_API_SECRET` | Wiro AI (triyaj) | Gerçek triyaj için gerekli |
| `REDIS_URL` | Redis bağlantı | `redis://localhost:6379/0` veya boş bırakın (in-memory) |

Placeholder (`xxxx`, `your_service_role_key`) kullanmayın; backend Supabase’e bağlanamaz.

### 2.2 Dashboard (`dashboard/.env.local`)

`dashboard` klasöründe `.env.local` yoksa örnekten oluşturun:

**Windows (PowerShell):**
```powershell
cd dashboard
if (!(Test-Path .env.local)) { Copy-Item .env.local.example .env.local }
```

**Linux/macOS:**
```bash
cd dashboard
[ -f .env.local ] || cp .env.local.example .env.local
```

`.env.local` içinde mutlaka güncelleyin:

| Değişken | Açıklama | Nereden |
|----------|----------|---------|
| `SUPABASE_URL` | Supabase proje URL | Backend ile aynı proje |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (sunucu tarafı) | Supabase → Settings → API |
| `NEXT_PUBLIC_SUPABASE_URL` | Aynı proje URL (client tarafı) | Backend ile aynı |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **anon** (public) key | Supabase → Settings → API |
| `NEXT_PUBLIC_API_BASE` | Backend adresi | Geliştirme: `http://127.0.0.1:8000` |
| `ADMIN_API_KEY` | Backend ile aynı admin anahtar | Backend `.env` ile aynı |

**Önemli:** `SUPABASE_SERVICE_ROLE_KEY` sadece sunucu tarafında kullanılır; client’a vermeyin. Magic link girişi için `NEXT_PUBLIC_SUPABASE_ANON_KEY` doğru (anon) anahtar olmalı.

### 2.3 Mobil (opsiyonel)

Mobil uygulama varsayılan olarak `http://localhost:8000` kullanır (`app.config.ts` / `extra.API_BASE`). Farklı bir backend için `.env` veya EAS Secrets ile `API_BASE` tanımlanabilir.

---

## 3. Redis (Opsiyonel)

Rate limiting için Redis kullanmak isterseniz (Docker açıksa):

```powershell
docker run -d --name triaige-redis -p 6379:6379 redis:alpine
```

Backend `.env` içinde `REDIS_URL=redis://localhost:6379/0` olsun. Redis çalıştırmazsanız bu satırı boş bırakabilirsiniz; backend in-memory rate limit kullanır.

---

## 4. Backend’i Başlatma

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Linux/macOS:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Port: **8000**
- Geliştirmede `--reload` eklenebilir; Windows’ta bazen multiprocessing hatası verirse `--reload` olmadan çalıştırın.

---

## 5. Dashboard’u Başlatma

Yeni bir terminalde:

```powershell
cd dashboard
npm install
npm run dev
```

- Port: **3000**
- Tarayıcı: http://localhost:3000

---

## 6. Mobil (Opsiyonel)

Üçüncü terminalde:

```powershell
cd mobile
npm install
npx expo start
```

- Backend: `http://localhost:8000` (emülatör veya aynı ağdaki cihaz).

---

## 7. Supabase Entegrasyonunu Doğrulama

### Backend

Backend çalışırken:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing | Select-Object -ExpandProperty Content
```

Beklenen: `"supabase":"ok"`. `"not_configured"` veya `"error"` ise `backend/.env` içindeki `SUPABASE_URL` ve `SUPABASE_SERVICE_ROLE_KEY` değerlerini kontrol edin (placeholder olmamalı).

### Dashboard

Dashboard kökünde:

```powershell
cd dashboard
node scripts/check_supabase_connection.cjs
```

Beklenen çıktı: `OK`. Hata alırsanız `.env.local` içindeki `SUPABASE_URL` ve `SUPABASE_SERVICE_ROLE_KEY` (ve gerekirse `NEXT_PUBLIC_*`) değerlerini kontrol edin.

### Admin Status sayfası

Giriş yaptıktan sonra: http://localhost:3000/admin/status  
Backend API, Supabase ve admin istatistikleri burada özetlenir.

---

## 8. Başlatma Sırası Özeti

1. (Opsiyonel) Redis container
2. Backend (port 8000)
3. Dashboard (port 3000)
4. (Opsiyonel) Mobil: `npx expo start`

---

## 9. Hızlı Kontrol Listesi

| Kontrol | Komut / adres |
|--------|----------------|
| Backend canlı mı? | http://localhost:8000/health |
| Backend Supabase? | Health cevabında `"supabase":"ok"` |
| Dashboard açılıyor mu? | http://localhost:3000 |
| Dashboard Supabase? | `cd dashboard && node scripts/check_supabase_connection.cjs` |
| API dokümantasyonu | http://localhost:8000/docs |

---

## 10. Sık Karşılaşılan Sorunlar

- **ERR_NAME_NOT_RESOLVED (xxxx.supabase.co):** `.env` / `.env.local` içinde hâlâ placeholder var. Gerçek Supabase proje URL ve anahtarlarını kullanın.
- **Backend port 8000 kullanımda:** 8000’i kullanan işlemi kapatın veya farklı port verin (`--port 8001`).
- **Magic link girişi çalışmıyor:** Supabase’te anon key ile service_role key’i karışmış olabilir. `NEXT_PUBLIC_SUPABASE_ANON_KEY` = anon (public), `SUPABASE_SERVICE_ROLE_KEY` = service_role (secret). Supabase Dashboard → Settings → API’den kontrol edin.
- **429 / "email rate limit exceeded":** Supabase Auth limitleri:
  - **Aynı kullanıcı (e-posta):** Magic link / OTP için **60 saniye** bekleme (yeni istek aynı kullanıcıya 60 sn sonra). Dashboard’ta özelleştirilebilir: **Authentication → Rate limits**.
  - **Toplam e-posta:** Varsayılan SMTP ile **saatte 2 e-posta** (tüm signup/recover/magic link toplamı). Daha fazlası için özel SMTP gerekir.
  Bu hatayı alırsanız en az 60 saniye bekleyin; “too many” sık sürüyorsa saatlik 2 e-posta limitine takılmış olabilirsiniz, 1 saat sonra tekrar deneyin. Login sayfasında rate limit sonrası buton 60 saniye devre dışı kalır.
- **401 Unauthorized — auth/callback:** Magic link tıklanınca giriş tamamlanmıyor ve konsolda 401 görüyorsanız:
  1. **Redirect URL:** Supabase Dashboard → **Authentication** → **URL Configuration** → **Redirect URLs** listesine tam adresi ekleyin: `http://localhost:3000/auth/callback` (production için `https://yourdomain.com/auth/callback`).
  2. **Anon key:** `NEXT_PUBLIC_SUPABASE_ANON_KEY` değeri Supabase → **Project Settings** → **API** → **anon public** anahtarı olmalı (service_role değil).
- **Dashboard’ta “Supabase yapılandırılmamış”:** `.env.local` içinde `NEXT_PUBLIC_SUPABASE_URL` ve `NEXT_PUBLIC_SUPABASE_ANON_KEY` gerçek değerlerle dolu olmalı; `xxxx` veya `your_anon_key` kalmamalı.

---

Bu rehber proje kökündeki `README.md` ve `docs/DEPLOY_AND_ENV.md` ile birlikte kullanılabilir.
