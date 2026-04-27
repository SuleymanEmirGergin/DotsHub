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
| `RATE_LIMIT_WINDOW_SEC` | Rate limit penceresi (sn) | `60` |
| `RATE_LIMIT_MAX_REQ` | Pencere başına istek | `20` |
| `SEND_SUMMARY_RATE_LIMIT_MAX_REQ` | send-summary ve export-summary limiti (örn. 5/dk) | `5` |
| `SEND_SUMMARY_EMAIL` | `1` ise özet e-postası açık | `0` veya `1` |
| `RESEND_API_KEY` | Resend API anahtarı (e-posta için) | — |

### Compliance ile ilgili flag'ler

Aşağıdaki flag'lerin değiştirilmesi yasal sonuç doğurabilir. Production'da değiştirmeden önce hukuk + DPO onayı şart. Tam liste: [`docs/COMPLIANCE_CHECK_2026_04.md`](COMPLIANCE_CHECK_2026_04.md).

| Flag | Default | Production'da değiştirme koşulu |
|------|---------|--------------------------------|
| `LLM_NLU_ENABLED` | `false` | **`true` yapmadan önce:** Wiro.ai (veya seçilen LLM provider) ile yazılı DPA + standart sözleşme hükümleri (SCC, AB→TR transfer için) imzalanmış olmalı; provider'ın zero-retention API politikası teyit edilmeli; [`docs/SUB_PROCESSORS.md`](SUB_PROCESSORS.md) güncellenmeli; aydınlatma metni güncel sub-processor listesini içermeli (Compliance KR-4). `false` iken pipeline tamamen deterministic — tek bir kullanıcı verisi dış servise gitmiyor. |
| `LLM_NLU_LOG_TO_SUPABASE` | `true` | Yalnızca `LLM_NLU_ENABLED=true` iken anlamlı. LLM çağrı logu `llm_calls` tablosuna yazılır; retention 30 gün ([`RETENTION_POLICY.md`](RETENTION_POLICY.md)). |
| `LLM_EXPLAIN_ENABLED` | `false` | Aynı DPA gereksinimi `LLM_NLU_ENABLED` ile. Açıklama katmanı da provider'a istek gönderir. |
| `PRIVACY_NOTICE_VERSION` | `v0.2` | Aydınlatma metni revize edildiğinde bump'la — mobile + dashboard ile lockstep. Bump = mevcut kullanıcılara in-app duyuru gerekir. |
| `CONSENT_VERSION_*` | `v1.0` | Bireysel rıza metni değiştiğinde bump'la. Bump → mobile bir sonraki açılışta kullanıcıyı yeniden onay almaya yönlendirir. |
| `IP_HASH_SALT` | — | Production'da rotate ETME — eski hash'lerle eşleşme bozulur, rate-limit ve audit trail kırılır. Yeni proje kurulurken set et, sonra dokunma. |

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
