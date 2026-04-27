# Privacy Notice — Aydınlatma Metni

> ⚠️ **Hukuk onayı bekliyor (DRAFT).** Bu metin KVKK Md.10 + GDPR Art.13 zorunlu içeriğine göre yazılmıştır ve `dashboard/messages/{tr,en}.json:privacy.*` anahtarlarından birebir türetilebilir; ancak production'a alınmadan önce **Türkiye'de KVKK uzmanı bir hukuk danışmanı** + **AB tarafı için DPO/avukat** onayı şarttır.

Compliance lineage: [`COMPLIANCE_CHECK_2026_04.md:KR-2`](COMPLIANCE_CHECK_2026_04.md). Risk: [`RISK_REGISTER_2026_04.md:H-1`](RISK_REGISTER_2026_04.md).

---

## Source of truth

Live metinler — kullanıcının uygulamada/dashboard'da gördüğü içerik:

- **Türkçe:** [`dashboard/messages/tr.json`](../dashboard/messages/tr.json) → `privacy.*` ve `terms.*` key'leri
- **İngilizce:** [`dashboard/messages/en.json`](../dashboard/messages/en.json) → aynı key seti

JSON canlı kaynaktır. Bu doküman ise **hukuk review için bütünleşik metin** + **change-management notları** içerir. JSON'u güncellediğinizde bu dokümanı da güncellemeniz **şart**: özellikle "What changed" bölümünü.

---

## Coverage / locales

| Locale | Status | Source | Notlar |
|--------|--------|--------|-------|
| 🇹🇷 Türkçe (`tr`) | ✅ DRAFT | `messages/tr.json` | Canonical. KVKK Md.10 zorunlu içerik tam. |
| 🇬🇧 English (`en`) | ✅ DRAFT | `messages/en.json` | TR ile yapısal parity (35 key). GDPR Art.13 zorunlu içerik tam. |
| 🇩🇪 Deutsch (`de`) | ❌ Yok | — | Mobile destekliyor, dashboard'da yok. **Slice 2B** kapsamında profesyonel çeviri. |
| 🇷🇺 Русский (`ru`) | ❌ Yok | — | Aynı şekilde. |
| 🇸🇦 العربية (`ar`) | ❌ Yok | — | RTL ek dikkat. |

DE/RU/AR locale'leri olmadığında dashboard `/privacy` sayfası `en` fallback'ine düşer (bkz. `dashboard/app/privacy/page.tsx:getLocale`). Bu KVKK aydınlatma yükümlülüğünü tam karşılamaz — DE/RU/AR mobil kullanıcı için aydınlatma metni anladığı dilde olmalı. Slice 2B'ye kadar bilinçli bir kabul.

---

## KVKK Madde 10 zorunlu içerik haritası

| KVKK Md.10 maddesi | Karşılayan section (key) |
|---|---|
| (a) Veri sorumlusunun ve varsa temsilcisinin kimliği | `dataControllerTitle/Body` |
| (b) Kişisel verilerin hangi amaçla işleneceği | `purposeTitle/Body/List` |
| (c) İşlenen kişisel verilerin kimlere ve hangi amaçla aktarılabileceği | `sharingTitle/Body/List` + `dataTransferTitle/Body` |
| (ç) Kişisel veri toplamanın yöntemi ve hukuki sebebi | `dataCollectedTitle/Body/List` + `legalBasisTitle/Body` |
| (d) Madde 11'de sayılan haklar | `rightsTitle/Body/List/Contact` |

## GDPR Art.13 zorunlu içerik haritası

| GDPR Art.13 maddesi | Karşılayan section (key) |
|---|---|
| Identity + contact (1)(a)(b) | `dataControllerTitle/Body` |
| Purposes + legal basis (1)(c) | `purposeTitle/Body` + `legalBasisTitle/Body` |
| Recipients (1)(e) | `sharingTitle/Body/List` |
| International transfers (1)(f) | `dataTransferTitle/Body` |
| Retention (2)(a) | `storageTitle/Body` (numbers from `RETENTION_POLICY.md`) |
| Data subject rights (2)(b) | `rightsTitle/Body/List` |
| Right to lodge complaint (2)(d) | `rightsList` (KVKK Kurumu / DPA) |
| Art.22 automated decision-making | `automatedDecisionTitle/Body` |
| Special category (Art.9(2)) | `legalBasisBody` (explicit consent under 9(2)(a)) |

---

## Hukuk gözden geçirme için tam metin (TR)

Aşağıdaki metin `messages/tr.json:privacy.*` anahtarlarından satır-by-satır türetilmiştir. JSON güncellenirse bu blok da güncellenmeli (`scripts/sync_privacy_doc.py` — şu an manuel; otomasyon TODO).

### Gizlilik Politikası

**Son güncelleme:** 27 Nisan 2026

Triaige olarak gizliliğinize önem veriyoruz. Bu politika, uygulamayı kullanırken hangi verilerin toplandığını, nasıl işlendiğini, saklandığını ve kullanıcı olarak haklarınızı açıklar. Triaige Türkiye'de KVKK (6698 sayılı Kişisel Verilerin Korunması Kanunu) ve AB kullanıcıları için GDPR ile uyumlu şekilde hazırlanmıştır. Triaige sağlık verisi işlediği için işleme açık rızaya dayanır.

#### Veri Sorumlusu

Triaige uygulamasının veri sorumlusu kimliği: Emir Gergin · İletişim: emirgergin21@gmail.com. Bu e-posta adresi tüm gizlilik sorgulama ve talepleri için tek yetkili kanaldır.

> **Hukuk notu:** Veri sorumlusu kimliği gerçek kişi olarak listelenmiş. Türkiye'de VERBİS kayıt eşiği aşılırsa kayıt zorunlu olabilir; KVKK uzmanı ile teyit edilmeli (`COMPLIANCE_CHECK_2026_04.md:Y-3`).

#### Toplanan Veriler

Uygulamayı kullanırken aşağıdaki veri kategorileri toplanır:

- Triaj oturumu verileri: girdiğiniz belirtiler, cevapladığınız sorular, değerlendirme sonucu, önerilen branş ve aciliyet seviyesi
- Cihaz bilgileri: cihaz kimliği (anonim UUID), uygulama sürümü, platform (iOS/Android), dil tercihi
- İsteğe bağlı geri bildirim: triaj sonrası derecelendirmeniz ve yazılı yorumlarınız
- İsteğe bağlı özet e-postası: özet gönderim istediğinizde verdiğiniz e-posta adresi
- Push bildirim tokenları: cihazınızdaki bildirim sistemi için anonim tanımlayıcı
- Kullanım telemetrisi: kaç istek gönderildi, hata oranları (anonim, IP hash'lenir)

#### Hukuki Dayanak

Triaige sağlık verisi işler — bu KVKK Madde 6 ve GDPR Madde 9 kapsamında "özel nitelikli kişisel veri" sayılır. İşlemenin hukuki dayanağı KVKK Madde 6(2) ve GDPR Madde 9(2)(a) çerçevesinde **açık rızanızdır**: uygulamayı ilk açtığınızda intro ekranında bu rızayı ayrıca alırız ve dilediğinizde geri çekebilirsiniz. Rızanın geri çekilmesi geçmiş işlemenin hukuka aykırılığını oluşturmaz; yalnızca o andan sonraki işlemeyi durdurur. İsteğe bağlı alanlar (geri bildirim, özet e-postası, push bildirim) için ek rıza alınır.

> **Hukuk notu:** Açık rıza UI'ı henüz uygulanmadı (Slice 3 = `COMPLIANCE_CHECK:KR-1`). Bu metnin yayınlanması, mobil intro'daki açık rıza ayrımının (2 ayrı checkbox + versiyon kaydı) production'da olmasından sonra geçerli olur.

#### Saklama ve Konum

Triaj oturumları Supabase veritabanında (AB sunucuları) saklanır. Veri kategorisine göre saklama süreleri: oturum içeriği 90 gün sonra anonimleştirilir (kullanıcı silme talebiniz aynı süreyi tetikler), ardından 90 gün daha geçtikten sonra fiziksel olarak silinir; LLM çağrı logları 30 gün; geri bildirim 365 gün; push token'lar 90 gün hareketsizlik sonrası; özet e-postası adresleri gönderim sonrası 7 gün içinde silinir. Yedeklemeler en fazla 30 gün saklanır — silme talebiniz yedek arşivinden bu pencere içinde tamamen silinir.

> **Hukuk notu:** Bu sayılar [`docs/RETENTION_POLICY.md`](RETENTION_POLICY.md) + `backend/app/core/config.py:RETENTION_DAYS_*` ile birebir aynı. Üçü de **lockstep** güncellenmek zorunda.

#### Üçüncü Taraflarla Paylaşım

Verileriniz hiçbir şekilde satılmaz veya reklam amaçlı paylaşılmaz. Aşağıdaki hizmet sağlayıcılar işlem görevleri kapsamında sınırlı erişime sahiptir:

- Supabase (DB hosting, EU)
- Fly.io (backend, EU)
- Vercel (dashboard, EU edge)
- Sentry (error + replay, PII masking aktif)
- Resend (özet e-posta, sadece gönderim anı)
- Expo Push (bildirim altyapısı, anonim token)
- Wiro.ai (LLM, opsiyonel; sadece anonim semptom metni)

> **Hukuk notu:** Her sağlayıcı için DPA + SCC durumu [`docs/SUB_PROCESSORS.md`](SUB_PROCESSORS.md)'da listelenmeli (compliance Y-2 — bu doküman henüz yok). Slice 4'te yapılacak.

#### Yurt Dışı Aktarım

Bazı hizmet sağlayıcıların altyapısı kısmen veya tamamen Türkiye/AB dışında olabilir. Özellikle LLM (Wiro.ai) kullanılırken, anonimleştirilmiş semptom metni provider'ın işlem sunucularına gönderilir. KVKK Madde 9 ve GDPR Madde 46 kapsamında: (a) sağlayıcılarla yazılı veri işleme sözleşmesi (DPA) ve standart sözleşme hükümleri (SCC) imzalanır; (b) provider DPA durumu kullanıcı için şeffaftır ve talep üzerine paylaşılır; (c) yeterli korumanın bulunmadığı durumlarda LLM özelliği uygulamanın bir kısmında devre dışı bırakılabilir.

> **Hukuk notu:** Bu compliance KR-4'ün metin tarafıdır; LLM provider DPA/SCC fiziksel olarak imzalanmadan production'da bu metin yanıltıcı olur. Hukuk + ürün ekibi imzalamadan production'a geçmez.

#### Haklarınız

KVKK ve GDPR kapsamında: erişim, düzeltme, silme, itiraz, taşınabilirlik, şikâyet (KVKK Kurumu / EU DPA). Talepleriniz emirgergin21@gmail.com — 30 gün içinde yanıt.

#### Otomatik Karar Verme ve Profilleme

Triaige, deterministic kurallar ve algoritmik skorlama ile size bir uzmanlık branşı önerir. Bu öneri **tıbbi tanı niteliği taşımaz** ve hekim kararının yerine geçmez — yalnızca yönlendirme amacıyladır. Nihai sağlık hizmeti seçimi her zaman size aittir; sistem sizi bir karara zorlamaz. Bu nedenle GDPR Madde 22 anlamında "yalnızca otomatik karar verme" uygulanmaz.

#### Güvenlik Önlemleri, Çocuk Kullanıcılar, Politika Değişiklikleri, Tıbbi Uyarı

Bu sectionlar JSON'da tam olarak yer alır; kısa olduğu için burada tekrarlanmamıştır. `messages/tr.json:privacy.{security,children,changes,disclaimer}*` anahtarlarına bakın.

---

## Change-management

Privacy notice'da yapılan her değişiklik için PR'da kontrol listesi:

- [ ] `messages/tr.json:privacy.*` güncellendi
- [ ] `messages/en.json:privacy.*` aynı key'lerle güncellendi
- [ ] TR/EN parity test'i geçiyor (Slice 2B'de eklenecek; `scripts/check_dashboard_privacy_contract.cjs`)
- [ ] `messages/tr.json:privacy.lastUpdated` ve `en.json` aynı tarihe set
- [ ] Bu doküman ("Hukuk gözden geçirme için tam metin" bölümü) güncellendi
- [ ] CHANGELOG'a "[Privacy] " prefix'li giriş
- [ ] Hukuk danışmanı imzası (önemli değişiklikte)
- [ ] Mevcut kullanıcılara in-app banner duyurusu (önemli değişiklikte)
- [ ] Aydınlatma metni versiyonu güncellendi (consent versiyonu ile birlikte; Slice 3)

## Versiyon

| Versiyon | Tarih | Değişiklik özeti |
|---------|-------|-----------------|
| v0.1 | 2026-04-20 | İlk yayın (incomplete — drift mevcut) |
| **v0.2** | **2026-04-27** | **Bu commit: retention sayıları (RETENTION_POLICY ile lockstep), sub-processor expansion (Sentry/Resend/Expo eklendi), KVKK Md.6(2) + GDPR Art.9(2)(a) açık rıza dayanağı, dataTransfer section (LLM cross-border), automatedDecision section (Art.22)** |
| v0.3 | TBD | DE/RU/AR çevirileri (Slice 2B) |
| v1.0 | TBD | Hukuk onayı + Slice 3 (consent UI) entegrasyonu sonrası ilk production yayını |

---

## Kanonik metni güncellemek için workflow

1. Hukuk danışmanı ile değişiklik kararı al.
2. `messages/tr.json:privacy.*` güncelle (canonical).
3. `messages/en.json:privacy.*` aynı key'lerle güncelle.
4. Bu dokümanı (Versiyon tablosu + Change-management checklist) güncelle.
5. PR aç; reviewer hukuk + ürün.
6. Merge sonrası: dashboard'da `/privacy` sayfasında göründüğünü doğrula.
7. Mobile `EXPO_PUBLIC_PRIVACY_URL` zaten dashboard'a deep-link verir; ayrı deploy gerekmez.

---

Bu doküman: `docs/PRIVACY_NOTICE.md`. Son güncelleme: 2026-04-27.
