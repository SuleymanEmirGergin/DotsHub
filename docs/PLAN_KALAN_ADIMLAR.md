# Kalan adımlar – Ayrıntılı plan (sırayla, atlama yok)

Bu belge, kalan tüm maddeleri tek tek alt adımlara böler. Her madde tamamlandıkça işaretlenir.

---

## Adım 1: Mobil – Dil tercihi saklama + varsayılan dil

### 1.1 AsyncStorage ile locale saklama

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 1.1.1 | AsyncStorage key sabiti | `mobile/constants.ts` veya `mobile/i18n/storage.ts`: `LOCALE_STORAGE_KEY = "@dotshub/locale"` |
| 1.1.2 | Kaydetme | `I18nProvider` içinde `setLocale` çağrıldığında `AsyncStorage.setItem(LOCALE_STORAGE_KEY, next)` (async, fire-and-forget veya await) |
| 1.1.3 | Okuma | Uygulama açılışında (layout veya I18nProvider mount) `AsyncStorage.getItem(LOCALE_STORAGE_KEY)` → geçerli locale ise state’e yükle |
| 1.1.4 | Bağımlılık | `expo` ile gelen `@react-native-async-storage/async-storage` veya `expo-secure-store`; yoksa paket ekle |

**Kod noktaları:**
- `mobile/i18n/I18nProvider.tsx`: `defaultLocale` prop’u yerine ilk render öncesi/sonrası AsyncStorage’dan oku (state başlangıç `null` → okunduktan sonra `tr` veya okunan).
- Layout’ta `defaultLocale` artık kullanılmayacak veya sadece fallback; asıl kaynak AsyncStorage + expo-localization.

### 1.2 expo-localization ile varsayılan dil (ilk açılış)

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 1.2.1 | Paket | `expo-localization` (Expo SDK’da genelde var) — `getLocales()` |
| 1.2.2 | İlk açılış mantığı | AsyncStorage’da locale yoksa: `getLocales()[0].languageCode` (veya `localeCode`) al; "tr", "en", "de", "ru", "ar" ile eşleştir; ilk eşleşen yoksa `"tr"` |
| 1.2.3 | I18nProvider’a besleme | Root layout’ta: önce AsyncStorage’dan oku; boşsa expo-localization’dan türet; bu değeri `defaultLocale` olarak I18nProvider’a ver (veya I18nProvider içinde oku) |

**Dosya listesi:**
- `mobile/i18n/storage.ts` (yeni): `getStoredLocale()`, `setStoredLocale(locale)` — AsyncStorage wrapper.
- `mobile/i18n/defaultLocale.ts` (yeni): `getDefaultLocale(): Promise<Locale>` — AsyncStorage + getLocales() mantığı.
- `mobile/app/_layout.tsx`: AsyncStorage + locale hazır olana kadar splash beklet; sonra `I18nProvider defaultLocale={resolved}`.
- `mobile/i18n/I18nProvider.tsx`: setLocale’de AsyncStorage’a yaz; ilk state AsyncStorage/localization’dan gelen değer.

### 1.3 Tamamlanma kriteri

- Uygulama kapatılıp açıldığında son seçilen dil korunur.
- İlk kurulumda cihaz dili TR/EN/DE/RU/AR ise o dil seçilir; değilse TR.

**✅ Adım 1 tamamlandı:** `i18n/storage.ts`, `i18n/defaultLocale.ts`, I18nProvider setStoredLocale, _layout getDefaultLocale + initialLocale, package.json bağımlılıkları.

---

## Adım 2: Mobil – Error boundary + retry

### 2.1 React Error Boundary

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 2.1.1 | Error boundary bileşeni | `mobile/src/components/ErrorBoundary.tsx`: class component veya react-error-boundary kütüphanesi; `componentDidCatch` / `getDerivedStateFromError` ile state’e hata yaz; children yerine fallback UI render et |
| 2.1.2 | Fallback UI metni | i18n: "Bir hata oluştu. Yeniden dene." (örn. `error.boundaryMessage`), buton "Yeniden dene" (sayfayı veya ağacı yenile / resetSession + state temizle) |
| 2.1.3 | Sarmalama yeri | `mobile/app/_layout.tsx`: I18nProvider içinde, Stack’i `<ErrorBoundary fallback={...}>` ile sarmala |
| 2.1.4 | Yeniden deneme davranışı | Fallback’te buton: Error boundary state’ini sıfırlayıp çocukları tekrar mount etmek (key değiştirerek) veya kullanıcıyı ana ekrana yönlendirip resetSession |

**Dosya listesi:**
- `mobile/src/components/ErrorBoundary.tsx` (yeni).
- `mobile/app/_layout.tsx`: ErrorBoundary kullanımı.
- `mobile/i18n/*.json`: `error.boundaryMessage`, `common.retry` (zaten var).

### 2.2 Retry (mevcut)

- ErrorScreen zaten "Tekrar dene" ve "Yeni Değerlendirme" içeriyor; sadece Error Boundary fallback’te de aynı terminoloji kullanılacak.

### 2.3 Tamamlanma kriteri

- Render sırasında fırlayan bir hata Error Boundary tarafından yakalanır, kullanıcıya mesaj ve "Yeniden dene" gösterilir.

**✅ Adım 2 tamamlandı:** `src/components/ErrorBoundary.tsx`, _layout’ta ErrorBoundary ile Stack sarmalama.

---

## Adım 3: Mobil – Push bildirimleri

### 3.1 İzin ve token

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 3.1.1 | İzin | `expo-notifications.requestPermissionsAsync()` — ayarlar ekranında veya ilk sonuç ekranından sonra (tek seferlik) |
| 3.1.2 | Token | `getExpoPushTokenAsync()` — Expo Go’da sınırlı; development build’de tam destek |
| 3.1.3 | Saklama | Token’ı AsyncStorage’da veya backend’e gönderip orada kullanıcı/session ile eşle |

### 3.2 Backend’e gönderme

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 3.2.1 | Endpoint | Backend’de `POST /v1/triage/push-token` veya mevcut bir kullanıcı/session endpoint’ine body’de `expo_push_token` ekle |
| 3.2.2 | Mobil client | `mobile/src/api/pushClient.ts`: `registerPushToken(token: string, sessionId?: string)` → POST |
| 3.2.3 | Çağrı yeri | İzin alındıktan ve token alındıktan sonra registerPushToken çağır |

### 3.3 Politika dokümanı

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 3.3.1 | Doküman | `docs/PUSH_NOTIFICATIONS_POLICY.md`: Ne zaman bildirim gönderileceği (örn. sonuç hazır, hatırlatma), veri saklama, abonelik iptali |

### 3.4 Tamamlanma kriteri

- Kullanıcı izin verirse push token alınır ve backend’e kaydedilir (endpoint + client + politika metni).

**✅ Adım 3 tamamlandı:** Backend `POST /v1/triage/push-token`, `mobile/src/api/pushClient.ts`, `usePushRegistration` hook, ResultScreen’de kullanım, `docs/PUSH_NOTIFICATIONS_POLICY.md`, package.json expo-notifications.

---

## Adım 4: Dashboard – i18n + dil değiştirici + error sayfası

### 4.1 i18n kullanımı (mevcut kontrol)

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 4.1.1 | Mesaj dosyaları | `dashboard/messages/tr.json`, `en.json` — zaten var; eksik key’leri sayfalara göre tamamla |
| 4.1.2 | getText kullanımı | Sayfalarda `getText(locale, "nav.sessions")` gibi; locale cookie veya header’dan |

### 4.2 Dil değiştirici

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 4.2.1 | Cookie | Locale tercihi: `locale` cookie (örn. `NEXT_LOCALE=tr` veya `locale=tr`); okuma: server component’te cookies(), client’ta document.cookie veya middleware |
| 4.2.2 | Header UI | Header’da TR / EN seçimi (dropdown veya toggle); tıklanınca cookie set et + sayfayı yenile veya client state güncelle |
| 4.2.3 | Layout | `app/layout.tsx`: html lang={locale}; header’a dil değiştirici bileşeni ekle |

### 4.3 Hata sayfası

| # | Yapılacak | Dosya / Detay |
|---|-----------|----------------|
| 4.3.1 | Global error | Next.js App Router: `app/error.tsx` — global error boundary; "Bir hata oluştu" + "Yeniden dene" butonu |
| 4.3.2 | not-found | İsteğe bağlı: `app/not-found.tsx` |

### 4.4 Tamamlanma kriteri

- Dashboard’da dil TR/EN seçilebilir, cookie’de saklanır, sayfalar bu locale’e göre metin gösterir.
- Beklenmeyen hata durumunda error.tsx devreye girer.

**✅ Adım 4 tamamlandı:** Layout’ta cookies() ile locale, html lang={locale}, LocaleSwitcher (TR/EN) header’da, common.errorTitle + common.retry mesajları, app/error.tsx global error boundary.

---

## Adım 5: Test, dokümantasyon, güvenlik (özet plan)

### 5.1 Test

- send-summary / export-summary E2E (backend).
- Mobil kritik akış E2E (isteğe bağlı).
- Unit: email_summary, i18n getText.

### 5.2 Dokümantasyon

- Deploy runbook (backend, dashboard, mobil; env; rollback).
- Mimari diyagram (Mermaid).
- CHANGELOG [Unreleased].

### 5.3 Güvenlik

- KVKK/GDPR: gizlilik metni, saklama süreleri, silme talebi.
- Push token: güvenli saklama, çıkışta silme.

**✅ Adım 5 tamamlandı:** CHANGELOG [Unreleased] güncellendi; backend tests/test_summary_export_route.py içinde send-summary testleri (404, 200) eklendi; docs/DEPLOY_AND_ENV.md, docs/ARCHITECTURE.md (Mermaid), docs/PRIVACY_AND_SECURITY.md eklendi.

---

## Mobil paket kurulumu (Adım 1 ve 3)

Plan uygulandığında `package.json`'a eklenen paketler için proje kökünde şu komutları çalıştırın:

```bash
cd mobile
npx expo install @react-native-async-storage/async-storage expo-localization expo-notifications
```

(Sandbox dışında çalıştırmanız gerekebilir.)

---

## Uygulama sırası

1. **Adım 1** (Mobil dil saklama + varsayılan)  
2. **Adım 2** (Mobil Error boundary)  
3. **Adım 3** (Mobil Push)  
4. **Adım 4** (Dashboard i18n + dil + error)  
5. **Adım 5** (Test / dokümantasyon / güvenlik — özet veya ayrı oturumda)

Her adım bitince bu dosyada ilgili bölüm "✅ Tamamlandı" ile işaretlenecek.

---

## Sonraki / İsteğe bağlı

Zorunlu adımlar tamamlandı. Aşağıdakiler iyileştirme veya sonraki sprint için önerilir. **Detaylı sonraki faz planı:** [PLAN_SONRAKI_FAZ.md](PLAN_SONRAKI_FAZ.md).

| Öncelik | Yapılacak | Detay |
|--------|-----------|--------|
| Orta | Mobil push uyumu | ✅ Kontrat dokümante edildi (PUSH_NOTIFICATIONS_POLICY, API_EXAMPLES); device_id guard mobilde eklendi. |
| Düşük | Dashboard sayfa i18n | ✅ tuning-tasks, tuning-metrics, tuning-report, session replay getText ile; sessions, analytics, deployments, live zaten i18n. |
| Düşük | Mobil E2E | ✅ Maestro triage_flow_smoke.yaml (intro → semptom → sonuç ekranı "Yeni Değerlendirme Başlat"); TESTING.md güncellendi; CI’da opsiyonel job eklendi. |
| Orta | Gizlilik linki | ✅ Mobil giriş ekranında EXPO_PUBLIC_PRIVACY_URL ile gizlilik politikası linki; DEPLOY_AND_ENV, PRIVACY_AND_SECURITY güncellendi. |
| Düşük | Mobil ResultScreen i18n | ✅ Tüm sabit metinler result.* / common.* (Evet/Hayır, özet, uyarılar, feedback) tr/en/de/ru/ar. |
| Bakım | CHANGELOG | ✅ 4.4.0 kesildi; [Unreleased] sıfırlandı. Release zamanı sürüm kesme devam eder. |
| Bakım | Plan dokümanı | Bu tablo güncellendi; PLAN_SONRAKI_FAZ ile uyumlu. |
| Bakım | RELEASE_CHECKLIST + regression + bağımlılık | ✅ RELEASE_CHECKLIST genişletildi (0. Sürüm öncesi, 4–7, checkbox’lar). Backend regression: send-summary/export-summary testleri REDIS_URL="" ile geçiyor. DEPENDENCY_UPDATES 2026-02-19 güncellendi; mobil npm audit notu eklendi. |
