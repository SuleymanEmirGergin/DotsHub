# Bağımlılık güncellemeleri raporu

Bu belge, `pip list --outdated` ve `npm outdated` çıktılarına göre güncellenebilir paketleri özetler. **Otomatik güncelleme yapılmaz;** güvenlik ve minor güncellemeler önceliklendirilir.

**Son kontrol:** 2026-02-19

---

## Backend (pip)

| Paket | Mevcut | En son | Öncelik |
|-------|--------|--------|---------|
| **cryptography** | 46.0.4 | 46.0.5 | **Yüksek** (güvenlik yamaları) |
| cachetools | 6.2.6 | 7.0.1 | Düşük |
| fastapi | 0.128.6 | 0.129.0 | Düşük |
| openai | 2.17.0 | 2.21.0 | Düşük |
| pip | 25.3 | 26.0.1 | Orta (`python -m pip install --upgrade pip`) |
| postgrest / realtime / storage3 / supabase / supabase-auth / supabase-functions | 2.27.3 | 2.28.0 | Düşük (Supabase SDK) |
| pyiceberg | 0.10.0 | 0.11.0 | Düşük |
| pydantic-settings | 2.12.0 | 2.13.0 | Düşük |
| psycopg / psycopg-binary | 3.3.2 | 3.3.3 | Düşük |
| redis | 7.1.1 | 7.2.0 | Düşük |
| uvicorn | 0.40.0 | 0.41.0 | Düşük |
| websockets | 15.0.1 | 16.0 | Düşük (major) |

**Öneri:** Önce `pip install --upgrade cryptography`; ardından ihtiyaca göre `pip install --upgrade fastapi openai` vb.

---

## Mobil (npm)

| Paket | Mevcut | Wanted / Latest | Not |
|-------|--------|-----------------|-----|
| @react-native-community/netinfo | (yüklü değil) | 11.4.1 / 11.5.2 | `npx expo install @react-native-community/netinfo` ile yükle. |
| @types/jest | 29.5.14 | 29.5.14 / 30.0.0 | Major atlama dikkatli. |
| @types/react | 19.1.17 | 19.1.17 / 19.2.14 | Minor güvenli. |
| expo-location | 18.0.10 | 18.0.10 / 19.0.8 | Expo SDK ile uyum kontrolü. |
| jest / jest-expo | 29.7.0 / 52.0.6 | 30.x / 54.x | Major atlama test gerekir. |
| react / react-dom | 19.1.0 | 19.1.0 / 19.2.4 | Minor güncelleme genelde güvenli. |
| react-native | 0.81.5 | 0.81.5 / 0.84.0 | Major; Expo sürümü ile uyumlu olanı seç. |
| react-native-screens | 4.16.0 | 4.16.0 / 4.23.0 | Minor güncelleme. |

**npm audit (2026-02-19):** 39 açık (1 moderate, 38 high); çoğu ajv, minimatch, tar ve jest/expo/glob zincirinde. `npm audit fix` kısmi düzeltme; tam düzeltme `npm audit fix --force` (Expo sürümü değişebilir, breaking). Önce `npm audit fix` denenebilir.

**Öneri:** Expo projelerinde `npx expo install` ile uyumlu sürümleri yükle; major atlamadan önce release notlarını kontrol et.

---

## Dashboard (npm)

| Paket | Mevcut | Wanted | Latest |
|-------|--------|--------|--------|
| @supabase/ssr | 0.6.1 | 0.6.1 | 0.8.0 |
| @types/node | 22.19.10 | 22.19.11 | 25.2.3 |
| @types/react | 19.2.13 | 19.2.14 | 19.2.14 |
| next | 15.5.12 | 15.5.12 | 16.1.6 |

**Öneri:** `@types/react` patch güncellemesi güvenli; Next.js 16’ya geçiş major, test ve dokümantasyon gerekir.

---

## Rutin

- **Haftalık/aylık:** `cd backend && pip list --outdated`; `cd mobile && npm outdated`; `cd dashboard && npm outdated`.
- **Güvenlik:** Önce `cryptography` ve diğer güvenlik duyurularına göre güncelleme.
- **Major sürüm:** Changelog ve breaking change’lere göre planlı güncelleme.
