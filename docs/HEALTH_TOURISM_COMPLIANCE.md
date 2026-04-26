# Sağlık turizmi uyumluluk dokümanı

Bu doküman, projenin sağlık turizmi (Block D + E1/E3/E4/E6) ayağı için
**Türkiye'deki yasal yükümlülükleri**, **KVKK gereklerini**, **GDPR/uluslararası
hasta verisi** notlarını ve **operasyonel uygulamayı kod ile bağlayan referansları**
tek dosyada toplar. Şu anki proje durumunda kalan açıkları "**[BOŞLUK]**" etiketiyle
işaretledim — yasal danışman onayı veya operatör aksiyonu gerektirir.

> **Önemli:** Bu doküman bir hukuki görüş değildir. Uygulamaya almadan önce
> sağlık hukuku alanında yetkin bir avukatla, ilgili Sağlık Bakanlığı il
> müdürlüğü ile ve Sağlık Turizmi Daire Başkanlığı ile birebir doğrulanmalıdır.

## 1. Düzenleyici çerçeve

### 1.1 Sağlık Turizmi Yetki Belgesi (zorunlu)

* **Mevzuat:** Sağlık Bakanlığı **Uluslararası Sağlık Turizmi ve Turistin Sağlığı Hakkında Yönetmelik** (RG: 13.07.2017, 30123 sayılı; 2021 değişiklikleri).
* **Kapsam:** Yurt dışından gelen hastalara aracılık eden her tür tüzel kişilik (klinik, acente, dijital platform) için zorunludur. **Aracılık** = "yurt dışından sağlık hizmeti alıcısı temininde rol almak" — bizim `/v1/quote` ve `/v1/quote/lead` akışı bu tanıma girer.
* **Belge tipi:** Bu proje gibi bir aracı kuruluş için **Sağlık Turizmi Aracı Kuruluşu Yetki Belgesi**.
* **Ön koşullar (özet):**
  - TÜRSAB (A grubu seyahat acentesi) belgesi
  - En az %51 oranında sağlık veya turizm sektörü tecrübesine sahip ortaklık
  - Hastane, poliklinik veya tıp merkezi ile yazılı protokol (operatörün partner kliniklerle imzalı sözleşmeleri olmalı)
  - Çoklu dil (en az TR + EN) destek personeli
  - SBYS (Sağlık Bilgi Yönetim Sistemi) entegrasyon kapasitesi (USS — Ulusal Sağlık Sistemi'ne hasta kaydı zorunlu)
* **Operatör aksiyonu (BOŞLUK):** Yetki belgesi başvurusu Sağlık Bakanlığı **il müdürlüğü** üzerinden yapılır. Belge alınmadan **production'a alma**.

### 1.2 KVKK (Kişisel Verilerin Korunması Kanunu)

* **Mevzuat:** 6698 sayılı KVKK (RG: 07.04.2016) + bağlı yönetmelikler.
* **Veri kategorisi:** Sağlık turizmi sürecinde toplanan veriler **özel nitelikli kişisel veri**dir (Madde 6/3): tıbbi geçmiş, kronik hastalık, ilaç kullanımı, görsel kayıtlar.
* **Açık rıza zorunluluğu:** Özel nitelikli kişisel verilerin işlenmesi için **yazılı veya elektronik olarak alınmış açık rıza** şarttır (Madde 6/2). Bizim `/v1/quote/lead`'deki `consent_to_share` flag'i bu rızayı **iletişim verisi paylaşımı** için kapsar; **tıbbi profil verileri için ayrı bir rıza akışı eklemek operatör sorumluluğudur**.
* **VERBİS kaydı:** Veri sorumlusu olarak Veri Sorumluları Sicili Bilgi Sistemi'ne kayıt zorunludur. Operatör tüzel kişiliği üzerinden yapılır.

### 1.3 GDPR (AB hasta erişimi)

* AB vatandaşı bir hasta `/v1/quote` üzerinden teklif aldığında **GDPR Madde 9** (özel kategori sağlık verisi) uygulanır. KVKK'nın açık-rıza paralelliği büyük ölçüde örtüşür ama bazı farklar:
  - Veri Koruma Görevlisi (DPO) atama zorunluluğu (büyük ölçek)
  - Hasta tarafından "veri silme hakkı" (Right to Erasure) — projedeki `DELETE /v1/me/sessions/{session_id}` endpoint'i (Block A öncesi kuruldu) **uyarlamayla** GDPR'ı karşılar; sağlık turizmi için spesifik silme akışı eklenmeli.
* **Hukuki danışman aksiyonu (BOŞLUK):** AB pazarına açık satış yapılacaksa GDPR Madde 27 temsilcisi (EU Representative) ataması.

## 2. Veri akışı + KVKK haritası

| Akış | Toplanan veri | Veri sorumlusu | Açık rıza alındığı an | Yasal saklama süresi |
|------|---------------|----------------|----------------------|---------------------|
| `/v1/quote` request `profile` | Yaş, cinsiyet, BMI, kronik hastalık flag'leri (recent_mi, pregnancy, smoker_active vb.) | Operatör | İlk uygulama açılışında "Sağlık verilerimi anonim olarak işlenmesine açık rıza veriyorum" onayı **gereklidir** (BOŞLUK: mobile UI'da explicit onay ekranı henüz pivot kapsamında yapılmadı; oluşturulmalı) | Açık rıza geri alınmadıkça veya 10 yıl. Kayıt amacı: yönlendirme kalitesi denetimi. |
| `/v1/quote/itinerary` | Aynı + arrival_date | Operatör | Quote ile aynı | Aynı |
| `/v1/quote/lead` `consent_to_share=False` | İletişim verisi gönderilmez (sadece session_id + procedure + clinic) | Operatör | İletişim verisi paylaşımı için ayrıca onay gerekir; bu durumda paylaşım **yapılmaz** | Yalnızca operasyonel log (session_id) — 1 yıl |
| `/v1/quote/lead` `consent_to_share=True` | İsim, e-posta, telefon, tercih edilen iletişim | Operatör + alıcı klinik | Patient explicitly checks "İletişim bilgilerimin klinikle paylaşılmasına açık rıza veriyorum" | Klinik müdahale sonrası 5 yıl (Sağlık Turizmi Yönetmeliği Madde 10) veya hasta talep ederse derhal silme |
| Webhook payload (`LEAD_WEBHOOK_URL`) | `consent_to_share=True` ise iletişim, değilse `{redacted: true}` sentinel | Operatör (transmit) + alıcı CRM (receive) | Yukarıdaki ile aynı | Alıcı CRM'in saklama politikasına bağlı — sözleşmeyle bağlanmalı |

### 2.1 Kod ↔ politika eşlemesi

| Politika maddesi | İlgili kod | Notu |
|------------------|------------|------|
| Açık rıza gate | `LeadRequest.consent_to_share` ([backend/app/models/schemas.py](backend/app/models/schemas.py)) | `False` ise `lead_dispatcher.build_payload` contact alanını `{redacted: true}` ile değiştirir |
| PII redaksiyonu (LLM çağrıları) | `app.pii.redact_pii` + `llm_nlu_client.NLUDirectClient.call` ([backend/app/services/llm_nlu_client.py:312](backend/app/services/llm_nlu_client.py:312)) | Procedure-intent LLM fallback `redact_pii(user)` üzerinden geçer |
| Webhook gönderim disiplini | [backend/app/services/lead_dispatcher.py](backend/app/services/lead_dispatcher.py) | Tek noktadan dispatch; consent gate burada |
| Soft-delete (klinik çıkışı) | `health_tourism_clinics.is_active` ([backend/sql/20260426_health_tourism_clinics.sql](backend/sql/20260426_health_tourism_clinics.sql)) | Klinik partner çıkardığında `false`; eski quote_id'ler hâlâ resolve olur |
| Veri silme talebi | `DELETE /v1/me/sessions/{session_id}` ([backend/app/api/routes/data_rights.py](backend/app/api/routes/data_rights.py)) | KVKK Madde 11 (silme hakkı). **Sağlık turizmi lead'leri** için ayrı bir `DELETE /v1/me/leads/{lead_id}` endpoint'i eklenmesi planlanmalı (BOŞLUK) |

## 3. Klinik güvenlik vs ticari öncelik

Sağlık turizmi operatörleri için en yüksek itibar riski:
**hastayı yolculuğa çıkarmak için sağlık riskini görmezden gelmek.**

Bu projede mimari olarak aşağıdaki şekilde **kasıtlı kısıtlanmıştır**:

* `services/fit_to_travel.py` block-tipi kuralları **ticari teklif yerine
  EMERGENCY zarfı** döndürür ([backend/app/api/routes/quote.py](backend/app/api/routes/quote.py)).
  Klinik teklifi gösterilmez. Hastaya "lokal bakım önerilir" mesajı verilir.
* `fit_to_travel_rules.json`'daki kurallar **en az 5 dilli** (TR/EN/DE/RU/AR)
  reason + recommendation içerir; Türkçe-bilmeyen hastaya hala anlamlı uyarı.
* `/v1/quote/itinerary` da fit_to_travel'ı **yeniden çalıştırır** — quote ile
  itinerary arasında haftalar geçebilir, sağlık durumu değişmiş olabilir.
* `KNOWN_TRIGGER_KEYS` ([backend/app/services/fit_to_travel.py](backend/app/services/fit_to_travel.py))
  import-time validation — yeni rule'a typo trigger_key yazılırsa server
  başlatılamaz; "kuralı sessizce no-op'a düşürme" hatasına karşı koruma.

## 4. Reklam ve pazarlama kısıtları

* **Tıbbi tanıtım yasakları:** Sağlık Bakanlığı'nın **Tıbbi Tanıtım ve Bilgilendirme Kılavuzu** (2018) before/after fotoğrafları, garanti vaadi, "en iyi" ifadeleri yasaklar.
* **Bizim kontekste:** `clinics.json` `before_after_count` alanı **sayısal değerdir** (içerik değil) — kılavuza uyumlu. Ancak operatörün dış pazarlama materyallerinde (landing page, Google Ads) bu sayıya görsel eşlik ettirmesi **kılavuh ihlali olabilir** ve KVKK ihlali doğurur. Operatör pazarlama uyumlu mu emin olmalı.
* **`why_recommended_tr` çıktısı:** `quote_engine` "X klinik dilinizi destekliyor", "Sertifikalar: JCI" gibi ifadeler üretir; bunlar **olgusal** ve uyumlu. "En iyi", "garanti", "%100 başarı" gibi ifadeler **kod tarafından üretilmez**, operatör template'i değiştirirken **ihlal yaratmamalı**.

## 5. Klinik partneri sözleşmesi: minimum maddeler

`clinics.json` veya `health_tourism_clinics` tablosuna bir klinik eklemeden önce
operatörün her klinikle imzalaması gereken sözleşmede şu maddeler **olmalıdır**:

1. **Sertifikasyon kanıtı:** JCI / ISO 9001 / IFSO_COE / TURSAB belgelerinin aslı.
2. **Yetki belgesi:** Klinik kendi başına da sağlık turizmi yetki belgesine sahip olmalı (operatörün belgesi tek başına yeterli değil).
3. **Veri işleyici sözleşmesi:** Klinik, hasta verilerini KVKK Madde 12 işleyici-veri sorumlusu sözleşmesi çerçevesinde işler.
4. **Komplikasyon yönetimi:** Hasta kompleksiyon yaşarsa klinik dünyanın neresinde olursa olsun maliyetsiz takibi taahhüt eder (sağlık turizmi yönetmeliği Madde 13).
5. **Şikayet kanalı:** Klinik 7/24 ulaşılır TR ve EN destek verir; şikayet işleme süresi 5 iş gününü aşmaz.
6. **Reklam onayı:** Klinik logosu/adı operatörün pazarlama materyallerinde kullanılırken her seferinde yazılı onay alır.

`scripts/seed_health_tourism_clinics.py` çalıştırılmadan önce **her klinik için
sözleşme arşiv numarasını `metadata.contract_id` alanına yazma** (operatör
aksiyonu, BOŞLUK).

## 6. Acil durum müdahale akışı

Hasta Türkiye'de iken acil tıbbi durum yaşarsa:

1. Operatör **ilk müdahaleyi yapan klinik** ile aynı sertifikasyon seviyesinde
   bir kuruma transfer için **24/7 hat** bulundurmalıdır.
2. Konsolosluk bildirimi (yabancı hasta vefat eder ya da uzun süreli yatış
   gerekirse) — Sağlık Turizmi Yönetmeliği Madde 14.
3. Sigorta — yurt dışından gelen hasta seyahat sağlık sigortasız ise klinik
   minimum 30,000 EUR teminatlı bir poliçe gerektirebilir; operatör bunu
   `/v1/quote` cevabında bildirmelidir (BOŞLUK: payload'a
   `insurance_required_min_eur` alanı eklenmeli).

## 7. Loglama ve audit gereklilikleri

* **Quote / itinerary / lead her isteğinde** `request_id` üretilir (mevcut
  middleware). Loglar JSON formatlı + structured fields ile Sentry/Loki'ye akar.
* **PII'siz audit:** `app.pii.redact_pii` her LLM çağrısında, summary email akışında
  ve `logging_config.py`'da formatter seviyesinde uygulanır. Sentry replay
  KVKK-safe modda çalışır ([docs/SENTRY_REPLAY_POLICY.md](docs/SENTRY_REPLAY_POLICY.md)).
* **Saklama:** Loglarda 30 gün rotation; `triage_sessions` tablosu 365 gün;
  `health_tourism_leads` (henüz tablo yok — BOŞLUK) için **5 yıl** saklama Sağlık
  Turizmi Yönetmeliği Madde 10 gereği.

## 8. Eylem listesi (operatör için)

| # | Aksiyon | Sahip | Durum |
|---|---------|-------|--------|
| 1 | Sağlık Turizmi Aracı Kuruluşu Yetki Belgesi başvurusu | Operatör (Sağlık Bakanlığı il müdürlüğü) | **BOŞLUK** |
| 2 | KVKK VERBİS kaydı | Operatör tüzel kişiliği | **BOŞLUK** |
| 3 | DPO ataması (GDPR + büyük ölçek KVKK) | Operatör | **BOŞLUK** |
| 4 | Mobile UI'da açık rıza onay ekranı (özel nitelikli sağlık verisi + iletişim verisi paylaşımı için ayrı ayrı) | Frontend ekibi | **BOŞLUK** |
| 5 | ~~`DELETE /v1/me/leads/{lead_id}` endpoint'i (KVKK silme hakkı için lead-spesifik)~~ | Backend ekibi | ✅ [backend/app/api/routes/data_rights.py](backend/app/api/routes/data_rights.py) `delete_my_lead` — soft-delete via lead_repository, contact + notes nulled, deleted_at stamped, 5-yr retention için row preserved |
| 6 | ~~`health_tourism_leads` Supabase tablosu + 5 yıl retention politikası~~ | Backend ekibi | ✅ Tablo: [backend/sql/20260426_health_tourism_leads.sql](backend/sql/20260426_health_tourism_leads.sql); persistence: [backend/app/services/lead_repository.py](backend/app/services/lead_repository.py); soft-delete = is_deleted=true (5 yıl retention için row korunur, contact + notes nulled) |
| 7 | Her klinik partneri için yazılı sözleşme + `metadata.contract_id` | Operatör + Hukuk | **BOŞLUK** |
| 8 | Acil durum müdahale prosedürü (24/7 hat, konsolosluk bildirimi) | Operasyon ekibi | **BOŞLUK** |
| 9 | Yurt dışı pazarlama uyumluluk denetimi (Tıbbi Tanıtım Kılavuzu) | Pazarlama + Hukuk | **BOŞLUK** |
| 10 | EU Representative (GDPR Madde 27) — AB pazarı açılırsa | Operatör | **BOŞLUK** |

## 9. İlgili kod referansları

* [backend/app/services/fit_to_travel.py](backend/app/services/fit_to_travel.py) — klinik güvenlik kuralları
* [backend/app/services/lead_dispatcher.py](backend/app/services/lead_dispatcher.py) — KVKK consent gate
* [backend/app/data/fit_to_travel_rules.json](backend/app/data/fit_to_travel_rules.json) — 12 kural, 5 dilli
* [backend/app/data/procedures.json](backend/app/data/procedures.json) — gerçek post-op no-fly + complexity verileri
* [backend/sql/20260426_health_tourism_clinics.sql](backend/sql/20260426_health_tourism_clinics.sql) — soft-delete + audit-friendly tablo
* [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md) — proje genel KVKK + GDPR
* [docs/SENTRY_REPLAY_POLICY.md](docs/SENTRY_REPLAY_POLICY.md) — replay KVKK-safe ayarları

---

**Sürüm:** v0.1 (2026-04-26) — Sağlık turizmi pivotu Block D + E1/E3/E4/E6 ile
birlikte. Yeni bir endpoint, yeni bir veri kategorisi veya yeni bir partner
klinik tipi geldiğinde bu doküman güncellenmelidir.
