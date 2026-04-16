# Bugün yapılacaklar – Kısa plan

Bu dosya tek bir günlük oturum için öncelikli maddeleri listeler. Plan dokümanlarından (PLAN_KALAN_ADIMLAR, SONRAKI_ADIMLAR_DETAYLI) seçilmiştir.

---

## 1. CodeQL uyarısını giderme (yapıldı)

- **Script:** `scripts/clean-codeql-databases.ps1` — Cursor kapalıyken çalıştırın.
- **Doc:** `docs/CURSOR_CODEQL_MULTIPLE_DATASETS.md` güncellendi; script ile temizleme öneriliyor.
- **Sizin yapacaklarınız:** Cursor'ı kapatıp `.\scripts\clean-codeql-databases.ps1` çalıştırın, onaylayın. Cursor'ı açın; uyarı kaybolmuş olmalı.

---

## 2. Mobil – Özet e-posta + metin indirme

**Durum: Zaten yapılmış.** `ResultScreen` içinde "Özeti e-postaya gönder" (e-posta alanı + buton) ve "Metni indir" (export-summary → Share) mevcut. `summaryClient.ts`, i18n key'leri (tr, en, ar, de, ru) ve loading/hata mesajları ekli. Ek bir iş gerekmiyor.

---

## 3. Backend – send-summary / export-summary rate limit

**Durum: Yapıldı.** 5/dk benimsendi; send-summary ve export-summary aynı bucket ile birlikte limitlendi (IP başına toplam 5 istek/dk). Varsayılan `SEND_SUMMARY_RATE_LIMIT_MAX_REQ=5`; export-summary middleware'e eklendi.

---

## 4. Test veya dokümantasyon

- send-summary / export-summary rate limit testleri güncellendi (5/dk, export-summary 429 testi eklendi).
- Test ve dokümantasyon: `docs/TESTING.md` eklendi; backend/dashboard/mobil test komutları ve summary testlerinin açıklaması.

---

## Sıra önerisi

1. CodeQL scriptini çalıştırıp uyarıyı giderin.
2. Mobilde ResultScreen'e "Özeti e-postaya gönder" ve "Metni indir" akışını ekleyin (2.1–2.5).
3. İsterseniz rate limit veya test/doküman ile devam edin.
