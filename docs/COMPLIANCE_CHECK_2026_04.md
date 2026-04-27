# KVKK + GDPR Uyum Kontrolü — 2026-04

**Kapsam:** Pre-Triage Agentic AI ürünü (FastAPI backend + Expo mobil + Next.js dashboard). İşlenen veri: serbest metin semptomlar, demografik (yaş/cinsiyet), oturum sonucu (branş + risk), feedback, e-posta (opsiyonel özet için), push token, IP hash, oturum ID.

**Sonuç:** ⚠️ **Proceed with conditions** — production'a açılmadan önce 4 kritik blocker (KR-1, KR-2, KR-3, KR-4) kapatılmalı. Mevcut teknik kontroller (erasure endpoint, IP hash, Sentry masking, tombstone pattern) iyi temel sağlıyor ama yasal zorunlulukları karşılamıyor.

> ⚠️ Bu doküman hukuki tavsiye değildir. Türkiye'de KVKK uzmanı, AB'de DPO/avukat onayı gerekir.

---

## 1. Uygulanabilir mevzuat

| Mevzuat | İlgisi | Temel yükümlülük |
|---------|--------|------------------|
| **KVKK** (Madde 6 — özel nitelikli kişisel veri) | Sağlık verisi işliyor; Türkiye'de mukim kullanıcı | **Açık rıza** zorunlu (genel kabul yetmez); aydınlatma yükümlülüğü; VERBİS kaydı |
| **KVKK** (Madde 10 — aydınlatma) | Tüm kullanıcılar | Veri sorumlusu kimliği, amaç, hukuki sebep, aktarım, haklar — açıkça yayınlanmalı |
| **KVKK** (Madde 12) | Tüm işlemler | Güvenlik tedbirleri + ihlal bildirim (en kısa sürede / 72 saat) |
| **GDPR Art. 9** | AB mukim kullanıcı | Sağlık verisi yasaktır; istisna gerekir (Art. 9(2)(a) explicit consent veya 9(2)(h) sağlık hizmeti sunumu) |
| **GDPR Art. 13/14** | Veri toplama anı | Privacy notice content requirements |
| **GDPR Art. 35** | Special-category + automated decision | DPIA zorunlu |
| **GDPR Art. 28 + Art. 46** | Sub-processors (Supabase, Resend, Sentry, LLM) | DPA + SCC (uluslararası aktarım için) |
| **e-Privacy / TR Elektronik Ticaret K.** | Ticari elektronik ileti olarak push/email | İzinli pazarlama yok ama transactional sınırı net olmalı |

---

## 2. Mevcut durum (uygun olanlar)

| # | Kontrol | Bulgu | Referans |
|---|---------|------|----------|
| ✅1 | **Erasure endpoint** | `DELETE /v1/me/sessions/{session_id}` — derived rows fully delete, session row tombstoned (id + timestamps korunur) | `backend/app/api/routes/data_rights.py` |
| ✅2 | **IP minimizasyonu** | Ham IP saklanmaz; SHA-256 + salt hash kaydedilir | `backend/app/db.py:hash_ip` |
| ✅3 | **PII log maskeleme** | Logs'ta serbest metin maskelenir | `backend/app/pii.py` |
| ✅4 | **Sentry Replay policy** | Politika dokümante; `maskAllInputs=true`; legitimate interest gerekçesi açık | `docs/SENTRY_REPLAY_POLICY.md` |
| ✅5 | **Mobil disclaimer** | "Bu uygulama tanı koymaz" 5 dilde | `mobile/i18n/*.json:disclaimer` |
| ✅6 | **Privacy link** | Dashboard `/privacy`, mobil `EXPO_PUBLIC_PRIVACY_URL` | `dashboard/app/privacy/`, `mobile/src/screens/IntroScreen.tsx` |
| ✅7 | **CORS + rate-limit + security headers** | Brute-force ve abuse'a karşı temel kontroller | `backend/app/main.py`, `rate_limit.py` |
| ✅8 | **Tombstone deletion strategy** | Audit integrity + erasure dengesi iyi tasarlanmış | `data_rights.py` docstring |
| ✅9 | **Email tek seferlik** | Send-summary için alınan e-posta marketing list'e taşınmaz | `services/email_summary.py`, README |
| ✅10 | **PII audit cycle** | Session 14'te local PII scanner + quarterly audit kuruldu | `docs/SENTRY_REPLAY_POLICY.md` |

---

## 3. Eksikler (KRİTİK — production blocker)

| # | Eksik | KVKK/GDPR atfı | Risk | Aksiyon |
|---|-------|----------------|------|---------|
| 🔴**KR-1** | **Açık rıza akışı yok** — sağlık verisi için intro ekranındaki "Anladım, kabul ediyorum" KVKK Madde 6(2) açık rıza tanımını karşılamıyor (özel nitelikli veri için ayrı, açık, bilgilendirilmiş, geri alınabilir rıza gerekir) | KVKK Md.6(2), GDPR Art.9(2)(a) | **Yüksek** — denetimde tüm veri işleme hukuksuz sayılabilir | Mobil intro'ya 2 ayrı checkbox: (a) genel kullanım koşulları, (b) sağlık verisi işlenmesi için açık rıza. Rıza zaman damgası + locale + versiyon ile kaydedilmeli (audit trail). Geri çekme akışı (delete-my-data ile birleşik). |
| 🔴**KR-2** | **Aydınlatma metni yayınlı değil** — `docs/PRIVACY_AND_SECURITY.md` "yayımlanmalıdır" diyor ama metin yok | KVKK Md.10, GDPR Art.13 | **Yüksek** — yasal yükümlülüğün doğrudan ihlali | KVKK Md.10 + GDPR Art.13 zorunlu içeriği: veri sorumlusu kimliği, vekil, amaçlar, hukuki sebepler, aktarılan üçüncü taraflar (Supabase, Resend, Sentry, LLM provider), saklama süreleri, haklar, başvuru kanalı. Türkçe + EN + 3 dil. `dashboard/app/privacy/page.tsx`'i bu içerikle doldur, mobil intro'dan link ver. |
| 🔴**KR-3** | **Saklama süreleri tanımsız** — "operasyonel gereklere göre" yetersiz | KVKK Md.7, GDPR Art.5(1)(e) | **Orta-Yüksek** — silme talebine cevap verilemez, denetimde defansif değil | Tablo: `triage_sessions` 90 gün → tombstone, 180 gün → fully purge; `triage_events` 90 gün; `llm_calls` 30 gün; `triage_feedback` 365 gün; `push_tokens` 90 gün inactive ise sil. Cron job + Supabase scheduled function. |
| 🔴**KR-4** | **LLM çağrılarında sağlık verisi cross-border transferi** — provider OpenAI/Anthropic/vb. ise serbest metin semptomlar AB/Türkiye dışına çıkıyor; SCC + Transfer Impact Assessment yok | GDPR Art.46, KVKK Md.9 | **Yüksek** — özel kategori veri için ek koruma şart | (a) LLM provider DPA + SCC (2021 versiyonu) imzalı mı doğrula; (b) zero-retention API kullanılıyor mu (provider'ın no-train policy'si); (c) kullanıcıyı "verileriniz X şirketine işlenmek üzere gönderilebilir" diye aydınlat; (d) opsiyonel: deterministic-only mode (LLM yok) toggle'ı |
| 🔴**KR-5** | **DPIA / Veri Koruma Etki Değerlendirmesi yok** | GDPR Art.35 (high-risk processing for special-category, automated profiling) | **Orta** — denetim ister, blocker değil ama önce dolduran kazanır | Şablon doldur: işlem tanımı, gereklilik testi, risk matrisi, mitigations. Ürünün emergency-rule + deterministic-scoring tasarımı zaten "automated decision" minimizasyonu için iyi argüman. |

## 4. Eksikler (YÜKSEK — kritik değil ama hızlıca yapılmalı)

| # | Eksik | Risk | Aksiyon |
|---|-------|------|---------|
| 🟠**Y-1** | **İhlal bildirim SOP yok** — ihlal yaşanırsa 72 saat içinde KVKK + ilgili kişiye bildirim gerekir, prosedür yok | Yüksek | `docs/runbooks/SECURITY_INCIDENT.md` mevcut ama KVKK Madde 12(5) bildirim akışı (kim, hangi formla, ne sürede) eklenmemiş. KVKK form + içerik şablonu ekle. |
| 🟠**Y-2** | **Sub-processor envanteri yok** — Supabase, Resend, Sentry, LLM provider, Fly.io, Expo, GitHub için DPA durumu belgelenmemiş | Orta | `docs/SUB_PROCESSORS.md` oluştur: ad, lokasyon, veri kategorisi, DPA imza tarihi, SCC modülü (C2P), sertifikalar (SOC2 vb.) |
| 🟠**Y-3** | **VERBİS kaydı durumu belirsiz** — sağlık verisi işleyen kuruluşlar için zorunluluk var mı kontrol edilmeli | Orta | Veri sorumlusu kim (ürün sahibi şirket)? Kayıt eşiği bu yapıyı kapsıyor mu? Hukuki danışman ile teyit. |
| 🟠**Y-4** | **Erişim ve taşınabilirlik hakları endpoint'i yok** — sadece DELETE var | Orta | KVKK Md.11(b)(c) + GDPR Art.15/20: `GET /v1/me/sessions/{id}/export` (JSON+PDF) ekle. Tombstone'lanmış ise 410 Gone döner. |
| 🟠**Y-5** | **Çocuk verisi (yaş gate) yok** | Orta | <16 yaş kullanıcılar için ebeveyn rızası akışı; KVKK 11/2018 sayılı karar + GDPR Art.8. Asgari: intro'da "16 yaş üstüyüm" onay kutusu. |

## 5. Eksikler (ORTA — clean-up)

| # | Eksik | Aksiyon |
|---|-------|---------|
| 🟡 O-1 | Push token retention belirsiz ("isteğe bağlı") | İnaktif 90 gün sonra otomatik sil; uninstall'da temizle |
| 🟡 O-2 | Veri minimizasyon politikası kod tarafında yok — serbest metin LLM'e gitmeden önce isim/TC/adres regex stripping yapılmıyor | `core/pii.py`'a önişleme adımı ekle, LLM input öncesi çağır |
| 🟡 O-3 | Email log retention belirsiz — Resend webhook event'lerinin saklanma süresi | Resend dashboard config + 30 gün max |
| 🟡 O-4 | Cookie banner yok (dashboard) | Dashboard sadece admin/staff kullanıyorsa düşük öncelik; public açılırsa zorunlu |

---

## 6. Hızlı kazanımlar (1 sprint)

1. **`docs/PRIVACY_NOTICE_TR.md` + `EN/DE/RU/AR`** — KVKK Md.10 zorunlu içeriği yaz, dashboard `/privacy` sayfasını bununla doldur. (KR-2)
2. **`docs/RETENTION_POLICY.md`** — tablo + Supabase cron SQL örnek. Saklama sürelerini kod sabiti yap (`backend/app/core/config.py`'a `RETENTION_DAYS_*`). (KR-3)
3. **`docs/SUB_PROCESSORS.md`** — mevcut providers tablosu, her biri için DPA + SCC durumu. (Y-2)
4. **`docs/runbooks/DATA_BREACH.md`** — 72 saat akışı, KVKK ihlal bildirim formu şablonu, kullanıcı bildirimi şablonu. (Y-1)
5. **Mobil intro consent ayrımı** — açık rıza ayrı checkbox + ayrı UI; rıza versiyonu (`v1`) ile birlikte session'a yaz. (KR-1)

## 7. Blocker'lar (release öncesi)

- KR-1, KR-2: kullanıcı görür, hemen yapılabilir
- KR-4: LLM provider seçimi + DPA durumu net olmadan production'a Türk/AB kullanıcı verisi akıtılmamalı
- KR-3: saklama süreleri Supabase migration ile birlikte gelmeli (orphan veri 12 ay birikirse temizleme operasyonu daha pahalı)

## 8. Onay gereken paydaşlar

| Paydaş | Neden | Durum |
|--------|------|--------|
| Hukuk danışmanı (KVKK uzmanı) | Aydınlatma + açık rıza metinleri onayı, VERBİS kaydı kararı | Bekliyor |
| AB tarafı için DPO veya temsilci | GDPR Art.27 — eğer AB'ye satış yapılıyorsa AB içinde temsilci atanmalı | Bekliyor |
| Ürün sahibi (veri sorumlusu) | KVKK Md.3 tanımı — kim "veri sorumlusu"? | Tanımlanmalı |

---

## 9. Daha derin değerlendirme önerilen alanlar

- **Otomatik karar verme** (GDPR Art.22): Ürün "şu uzmanlığa git" diyor — bu bir otomatik karar mı? "Sadece bilgilendirme" olarak nitelenirse Art.22 dışında, ama tartışmalı. Hukuki görüş alın.
- **Klinik denetim çerçevesi**: Türkiye'de Sağlık Bakanlığı'nın "yapay zeka destekli sağlık uygulamaları" yönergesi var mı? Tıbbi cihaz sınıflandırmasına girer mi (MDR/MDCG)?
- **Sigorta**: Hatalı yönlendirme sonucu klinik zarar oluşursa ürün sorumluluğu sigortası gerekir.

---

Audit tarihi: 2026-04-27. Sonraki review: production launch öncesi + her major feature ekleyişinde.
