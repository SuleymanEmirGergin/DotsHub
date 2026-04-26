# Deploy ve ortam değişkenleri

Backend, Dashboard ve Mobil uygulama için deploy adımları ve ortam değişkenleri özeti.

---

## Backend (FastAPI)

### Çalıştırma (geliştirme)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Ortam değişkenleri

| Değişken | Açıklama | Örnek |
|----------|----------|--------|
| `APP_ENV` | production / development | `development` |
| `SUPABASE_URL` | Supabase proje URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | — |
| `CORS_ORIGINS` | İzin verilen origin’ler (virgülle ayrılmış) | `http://localhost:3000,https://app.example.com` |
| `REDIS_URL` | Rate limit için Redis (opsiyonel). **Çok instance:** Birden fazla API worker/pod kullanıyorsanız paylaşılan limit için tanımlayın; yoksa her instance kendi in-memory limitine sahip olur. | `redis://localhost:6379` |
| `RATE_LIMIT_WINDOW_SEC` | IP/device rate limit penceresi (sn) | `60` |
| `RATE_LIMIT_MAX_REQ` | IP/device rate limit — pencere başına istek | `20` |
| `SESSION_RATE_LIMIT_WINDOW_SEC` | Session bazlı rate limit penceresi (sn). NAT arkasında adil paylaşım için IP bucket'ına ek olarak çalışır; `X-Session-Id` header'ı ile aktif olur. | `3600` |
| `SESSION_RATE_LIMIT_MAX_REQ` | Session başına pencere başına istek | `30` |
| `IDEMPOTENCY_TTL_SEC` | `Idempotency-Key` cache TTL (sn) — **triage** (`/v1/triage/turn`) için. Retry timeout/packet-loss network-katmanı; 5 dk yeterli. | `300` |
| `IDEMPOTENCY_QUOTE_TTL_SEC` | `Idempotency-Key` cache TTL — **quote** (`/v1/quote*`) için. Hasta teklifi okur, dakikalarca düşünür, accept eder; daha uzun pencere lazım. | `900` |
| `IDEMPOTENCY_MEMORY_MAX` | In-memory idempotency cache azami giriş sayısı (LRU). Redis yoksa kullanılır. | `1024` |
| `LLM_PROCEDURE_INTENT_ENABLED` | `1` ise sağlık turizmi `/v1/quote` deterministik sinonim eşleyici düşük confidence ya da miss verdiğinde LLM fallback'i çağırır. | `0` |
| `LLM_PROCEDURE_INTENT_MIN_CONFIDENCE` | Deterministik match'in altında LLM tetiklendiği eşik (0.0–1.0). | `0.40` |
| `LEAD_WEBHOOK_URL` | `/v1/quote/lead` kabul edildiğinde JSON POST gönderilen URL. Slack incoming webhook, Make/Zapier veya generic CRM olabilir. Boşsa lead webhook devre dışı; route 200 dönmeye devam eder ama payload `webhook_configured: false` olur. | — |
| `LEAD_WEBHOOK_AUTH_TOKEN` | Set edilirse `Authorization: Bearer <token>` header'ı gönderilir. | — |
| `LEAD_WEBHOOK_TIMEOUT_SECONDS` | Tek istek için timeout. | `5.0` |
| `LEAD_WEBHOOK_MAX_RETRIES` | 5xx ya da network hatasında deneme sayısı (4xx tek deneme). | `3` |
| `SEND_SUMMARY_RATE_LIMIT_MAX_REQ` | send-summary ve export-summary limiti (örn. 5/dk) | `5` |
| `SEND_SUMMARY_EMAIL` | `1` ise özet e-postası açık | `0` veya `1` |
| `RESEND_API_KEY` | Resend API anahtarı (e-posta için) | — |

### Rollback

1. Önceki sürüm image/artifact’a dön (ör. container tag veya binary).
2. Veritabanı şeması geriye uyumlu tutulmalı; migration geri alınacaksa yedek al.
3. Ortam değişkenleri aynı kalsın; gerekirse `APP_ENV` kontrol et.
4. Health check (`/health`) ile canlılığı doğrula.

---

## Dashboard (Next.js)

### Çalıştırma (geliştirme)

```bash
cd dashboard
npm install
npm run dev
```

### Ortam değişkenleri

- Next.js ortam değişkenleri: `.env.local` (örn. Supabase, API URL).
- Build: `npm run build` → `npm start` veya platforma göre deploy.

### Cookie

- `NEXT_LOCALE`: Dil tercihi (`tr` | `en`). Header’daki dil değiştirici ile set edilir.

### Deploy (Vercel / benzeri)

- **Build:** `npm run build`; output `out` (static export) veya `.next` (server).
- **Env:** Vercel proje ayarlarında `NEXT_PUBLIC_*`, `SUPABASE_*` vb. tanımla.
- **Rollback:** Vercel’de önceki deployment’a “Promote to Production” veya git’te önceki commit’e revert.

---

## Mobil (Expo)

### Çalıştırma (geliştirme)

```bash
cd mobile
npm install
npx expo install @react-native-async-storage/async-storage expo-localization expo-notifications
npx expo start
```

### Ortam / yapılandırma

- `app.config.ts` → `extra.API_BASE`, `extra.USE_MOCK`, `extra.PRIVACY_URL`.
- EAS Build için `EXPO_PUBLIC_PROJECT_ID` (push token) gerekebilir.
- Giriş ekranında "Gizlilik politikası" linkinin açılması için `EXPO_PUBLIC_PRIVACY_URL` (dashboard `/privacy` veya statik sayfa URL'i) tanımlanabilir; boşsa link gösterilmez.

### Store / dağıtım

- iOS: TestFlight / App Store.
- Android: internal track / Play Store.
- OTA güncelleme: EAS Update (isteğe bağlı).

### EAS Build (Expo Application Services)

- **Kurulum:** `npm install -g eas-cli`; `eas login`.
- **Yapılandırma:** `eas.json` (build profiles: development, preview, production).
- **Build:** `eas build --platform ios` veya `--platform android` veya `--platform all`.
- **Env:** EAS Secrets veya `app.config.ts` içinde `extra`; `EXPO_PUBLIC_PROJECT_ID` push için; `EXPO_PUBLIC_PRIVACY_URL` giriş ekranı gizlilik linki için (isteğe bağlı).
- **Rollback:** Store’da önceki sürümü yayına al veya EAS Update ile önceki OTA’ya dön.

---

## Özet

- **Backend:** Uvicorn + env; Redis opsiyonel; Supabase zorunlu (oturum/feedback).
- **Dashboard:** Next.js build + env; cookie ile dil.
- **Mobil:** Expo; AsyncStorage + expo-localization + expo-notifications; API_BASE ayarlı olmalı.

Detaylı env listesi için proje kökündeki `README` ve `backend/.env.example` (varsa) kullanılabilir.
