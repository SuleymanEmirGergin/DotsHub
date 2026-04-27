# KVKK Veri İşleme Sözleşmesi / Data Processing Agreement — TEMPLATE

> **DISCLAIMER**
>
> Bu doküman bir başlangıç şablonudur — hukuki tavsiye değildir. KVKK / GDPR uzmanı bir avukatın imza öncesi review'undan geçirilmelidir. TriAIge bu şablonun yarattığı veya yaratabileceği yükümlülüklerden sorumlu değildir.
>
> *This document is a starting template, not legal advice. It must be reviewed by KVKK / GDPR-qualified counsel before signing. TriAIge accepts no liability for obligations arising from use of this template.*

---

## 1. Taraflar / Parties

**Veri Sorumlusu / Data Controller:**
`[HASTANE / HOSPITAL LEGAL NAME]`
`[Adres / Address]`
`[Vergi No / Tax ID]`
`[KVKK Veri Sorumluları Sicili (VERBIS) Kayıt No]`
İrtibat Kişisi / Contact: `[KVKK uyum sorumlusu / DPO ad-soyad, e-posta, telefon]`

**Veri İşleyen / Data Processor:**
TriAIge `[Ticari Unvan / Legal Entity to be confirmed]`
`[Adres / Address]`
`[Vergi No / Tax ID]`
İrtibat Kişisi / Contact: Emir Gergin — `emirgergin21@gmail.com`

İşbu sözleşme, Veri Sorumlusu ile Veri İşleyen arasında, Veri Sorumlusu adına işlenen kişisel veriler bakımından KVKK m.12 ve GDPR m.28 uyarınca yükümlülükleri düzenler.

*This Agreement governs, between the Data Controller and the Data Processor, the obligations under KVKK art. 12 and GDPR art. 28 in respect of personal data processed by the Processor on behalf of the Controller.*

---

## 2. Tanımlar / Definitions

| Terim / Term | Tanım / Definition |
| ------------ | ------------------ |
| **Kişisel Veri / Personal Data** | KVKK m.3(1)(d) ve GDPR m.4(1) uyarınca, kimliği belirli veya belirlenebilir bir gerçek kişiye ilişkin her türlü bilgi. / Any information relating to an identified or identifiable natural person. |
| **Özel Nitelikli Kişisel Veri / Special-Category Data** | KVKK m.6 uyarınca özel nitelikli kişisel veriler (sağlık verisi dahil). GDPR m.9 uyarınca "special categories of personal data" (health data). Bu sözleşme kapsamındaki **sağlık verisi explicitly özel nitelikli** sayılır. / Special-category personal data per KVKK art. 6 and GDPR art. 9, **including health data**, which is explicitly within scope of this DPA. |
| **Açık Rıza / Explicit Consent** | KVKK m.3(1)(a) uyarınca belirli bir konuya ilişkin, bilgilendirilmeye dayanan ve özgür iradeyle açıklanan rıza. GDPR m.4(11) uyarınca "explicit consent". Sağlık verisi işlemenin başat hukuki dayanağıdır. / Informed, freely given, specific consent. The primary lawful basis for processing health data here. |
| **Veri Sorumlusu / Data Controller** | Kişisel verilerin işlenme amacını ve vasıtalarını belirleyen taraf (Hastane). / The party that determines purpose and means of processing (the Hospital). |
| **Veri İşleyen / Data Processor** | Veri sorumlusunun verdiği yetkiye dayanarak, onun adına kişisel verileri işleyen taraf (TriAIge). / The party processing personal data on behalf of the Controller (TriAIge). |
| **Alt-İşleyen / Sub-processor** | Veri İşleyen tarafından, Veri Sorumlusu adına işleme faaliyetinin bir kısmını yürütmek üzere görevlendirilen üçüncü taraf. / A third party engaged by the Processor to carry out part of the processing on behalf of the Controller. |
| **İhlal / Breach** | Kişisel verilerin yetkisiz erişimi, açıklanması, değiştirilmesi, kaybı veya imhası ile sonuçlanan güvenlik olayı. / A security incident resulting in unauthorised access, disclosure, alteration, loss, or destruction of personal data. |

---

## 3. İşleme amacı ve kapsamı / Purpose and scope

Veri İşleyen kişisel verileri yalnızca aşağıdaki amaçla işler:

- Hastaya semptom temelli **pre-triyaj yönlendirmesi** (uygun branş, aciliyet zarfı, risk seviyesi).
- Kullanıcı tarafından talep edildiğinde oturum özetinin e-posta ile iletilmesi.
- Servis güvenliği, hata izleme, audit ve KVKK m.12 kapsamında alınan güvenlik tedbirlerinin işletilmesi.

İşleme **kesinlikle** aşağıdakileri kapsamaz:

- Tıbbi tanı koyma / *medical diagnosis*.
- Tedavi önerisi / *treatment recommendation*.
- İlaç veya doz önerisi / *medication or dosage advice*.
- Pazarlama, profilleme veya üçüncü taraflara ticari amaçla aktarım.

*The Processor processes personal data solely for symptom-based **pre-triage routing** (specialty suggestion, urgency envelope, risk level), optional summary email delivery on user request, and operational security / audit obligations. Processing **explicitly excludes** medical diagnosis, treatment recommendation, medication advice, marketing, profiling, and onward commercial transfer.*

---

## 4. İşlenen veri kategorileri / Categories of data

| Kategori / Category | Örnek / Example | Özel Nitelikli mi? / Special-category? |
| ------------------- | --------------- | -------------------------------------- |
| Serbest metin semptom açıklaması / Free-text symptom description | "göğsümde sıkışma var" | **EVET — Sağlık verisi / YES — Health data** (KVKK m.6 / GDPR m.9) |
| Yapılandırılmış semptom cevapları / Structured symptom answers | Soru loop'undaki Evet/Hayır seçimleri | **EVET — Sağlık verisi / YES — Health data** |
| Oturum metaverisi / Session metadata | `session_id`, `request_id`, zaman damgası, locale | Hayır / No (ancak sağlık verisiyle ilişkili olduğu için aynı koruma altında işlenir) |
| Hash'lenmiş cihaz tanımlayıcısı / Hashed device ID | `x-device-id` (hash öncesi cihazda; backend'e hash'li gider) | Hayır / No |
| (Opsiyonel) Konum / (Optional) Location | Tesis araması için lat/lon (tesis bulma akışı tetiklendiğinde) | Hayır / No |
| (Opsiyonel) İletişim e-postası / (Optional) Contact email | Kullanıcı özet gönderimi talep ettiğinde | Hayır / No (münferit olarak; oturum özetiyle ilişkilendirildiğinde sağlık verisi koruması uygulanır) |

İşlenen kategorilerden en az biri (serbest metin semptom + yapılandırılmış cevaplar) **özel nitelikli sağlık verisi** olduğundan, işbu sözleşme genelinde KVKK m.6 ve GDPR m.9 koruma rejimi uygulanır.

*At least one processed category (free-text symptom + structured answers) is **special-category health data**; the higher protection regime under KVKK art. 6 and GDPR art. 9 applies throughout.*

---

## 5. Saklama süreleri / Retention

- Triyaj oturumu (semptom + cevaplar + sonuç) / *Triage session (symptoms + answers + result)*: `[X gün/ay — örn. 90 gün, hastane tarafından belirlenir]`
- Olay timeline / *Event timeline*: `[X gün/ay]`
- E-posta gönderim kaydı (sadece transmisyon kaydı) / *Email delivery log (transmission record only)*: `[X gün]`
- Push token (varsa) / *Push token if any*: kullanıcı çıkışı veya bildirim kapatma anında silinir / *deleted on user logout or notification opt-out*
- Audit / observability log'ları / *Audit / observability logs*: `[X ay]`

Saklama süresi sonunda Veri İşleyen, ilgili kayıtları geri dönülemeyecek şekilde **siler veya anonimleştirir**. Saklama süresi, hastanenin yasal yükümlülükleri (örn. tıbbi kayıt mevzuatı) gerektirdiğinde bu sözleşmede belirlenen süreden uzun olabilir; bu durumda süre Ek-1'de yazılı olarak güncellenir.

> **Not / Note:** TriAIge'in mevcut gizlilik dokümanı (`docs/PRIVACY_AND_SECURITY.md`), saklama süresi ve silme politikasının "operasyonel gereklere göre tanımlanmalı" olduğunu belirtir. İşbu sözleşmede süreler Veri Sorumlusu (hastane) tarafından imza öncesi yazılı olarak doldurulur.

*Retention periods must be filled in by the Hospital prior to signature. The Processor's current privacy posture flags retention as operationally defined; this DPA is the place where it is contractually fixed.*

---

## 6. Güvenlik tedbirleri / Security measures

Veri İşleyen, KVKK m.12 ve GDPR m.32 uyarınca aşağıdaki teknik ve idari tedbirleri **mevcut olarak** uygular:

- **Aktarım sırasında şifreleme / Encryption in transit:** TLS (Fly.io edge tarafından sonlandırılır; `docs/DEPLOY_FLY.md`).
- **Saklama sırasında şifreleme / Encryption at rest:** Supabase managed Postgres (AES-256 at rest, sağlayıcı tarafında).
- **Kimlik tabanlı izolasyon / Identity isolation:** Cihaz tanımlayıcılar **hash'lenir**; doğrudan kimlik (TCKN, telefon, e-posta) log'lara yazılmaz. PII maskeleme `backend/app/core/pii.py` ve `mobile/src/observability/redact.ts`'de zorunludur.
- **Yapılandırılmış audit izi / Structured audit trail:** Her oturum için olay timeline'ı (`triage_events.insert`); admin panelinde session-level replay; `request_id` her HTTP yanıtında.
- **KVKK uyumlu Sentry Replay / KVKK-safe Sentry Replay:** Mobil session replay'de tüm `<Text>` ve `<TextInput>` görsel olarak maskelenir; serbest metin patient input'u (`user_input_tr`, `answers`, `doctor_ready_summary_tr`, vb.) `beforeSend` hook'unda `[SCRUBBED]` ile değiştirilir; URL path'lerinde session UUID `/v1/session/[id]/...` şeklinde toplulaştırılır. Politika dokümanı: [`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md). Çeyreklik PII denetimi yürürlüktedir.
- **Rate limit ve DoS koruması / Rate limit and DoS protection:** Triage, send-summary, admin, LLM bucket'larında ayrı rate limit; çok-instance ortamlarda Redis-tabanlı paylaşımlı sayaç.
- **Erişim kontrolü / Access control:** Admin API ayrı Bearer token ile korunur; CORS production'da explicit origin listesi ile kısıtlanır.
- **Operasyonel gözlemlenebilirlik / Operational observability:** Prometheus `/metrics`, Grafana Cloud dashboard ve alarm kuralları (`docs/OBSERVABILITY.md`); Sentry crash + performance; sağlık probu (`/health`) Supabase reachability'sini doğrular.
- **Çeyreklik PII tarama / Quarterly PII scan:** Mobil ve backend Sentry event'lerinde local PII scanner (`scripts/sentry_event_pii_scan.py`).

Ek tedbirler veya hastane-özel kontroller Ek-2'de listelenebilir.

---

## 7. Alt-işleyenler / Sub-processors

İşbu sözleşmenin imzalandığı tarihte, Veri İşleyen aşağıdaki alt-işleyenlerden hizmet almaktadır:

| Alt-İşleyen / Sub-processor | Rol / Role | Lokasyon / Location |
| --------------------------- | ---------- | ------------------- |
| Supabase | Yönetilen Postgres veritabanı + auth (oturum + olay timeline'ı) | `[Bölge / Region — örn. eu-central-1]` |
| Sentry | Hata, performans ve KVKK-uyumlu Session Replay gözlemlenebilirliği | `[Bölge / Region]` |
| Grafana Cloud | Metrik dashboard'ları ve alarm kuralları (Prometheus remote_write) | `[Bölge / Region — örn. eu-west-X]` |
| Fly.io | Backend uygulama hosting (HTTPS edge, ams region) | Amsterdam (ams) |
| Vercel | Admin dashboard hosting (Next.js) | `[Bölge / Region]` |
| Upstash Redis | Multi-instance rate-limit bucket'ları (opsiyonel; backend `REDIS_URL` set ise) | `[Bölge / Region]` |
| `[E-posta sağlayıcı / Email provider — örn. Resend]` | Kullanıcı talep ettiğinde özet e-postası iletimi | `[Bölge / Region]` |

Veri İşleyen yukarıdaki listede değişiklik yapmadan önce Veri Sorumlusu'nu **en az `[30] gün** önceden yazılı olarak bilgilendirir. Veri Sorumlusu, makul gerekçeyle önerilen alt-işleyene itiraz hakkına sahiptir; uzlaşma sağlanamadığı takdirde Veri Sorumlusu sözleşmeyi feshetme hakkını kullanabilir.

*The Processor will notify the Controller in writing at least `[30] days` before any change to the sub-processor list. The Controller may object on reasonable grounds; failing resolution, the Controller may terminate.*

---

## 8. Veri sahibi hakları / Data subject rights

Veri İşleyen, Veri Sorumlusu'nun KVKK m.11 (bilgi alma, silme, düzeltme, itiraz, vb.) ve GDPR m.15-22 (access, rectification, erasure, restriction, portability, objection) kapsamındaki yükümlülüklerini yerine getirmesine destek olur.

**Somut mekanizma:**
- **Silme talebi / Erasure request:** TriAIge backend'inde `DELETE /v1/me/sessions/{session_id}` endpoint'i mevcuttur (CHANGELOG 4.6.0). Kullanıcı veya Veri Sorumlusu adına bu endpoint çağrıldığında ilgili oturumun semptom verileri, cevaplar ve özetleri silinir.
- **Erişim talebi / Access request:** Admin panelinde session-level event timeline replay'i mevcuttur; talep üzerine `[X iş günü]` içinde JSON export edilir.
- **Düzeltme / Rectification:** Triyaj oturumu kullanıcı kaynaklı serbest metin olduğundan düzeltme silme + yeniden oturum şeklinde uygulanır.

Veri sahibi başvurusu doğrudan Veri İşleyen'e ulaştığında, Veri İşleyen bu başvuruyu **`[3] iş günü** içinde Veri Sorumlusu'na iletir ve Veri Sorumlusu'nun talimatına göre hareket eder.

*Where a data subject contacts the Processor directly, the Processor forwards the request to the Controller within `[3] business days` and acts on the Controller's instruction. Concrete erasure mechanism: `DELETE /v1/me/sessions/{session_id}` (shipped in CHANGELOG 4.6.0).*

---

## 9. Veri ihlali bildirim / Data breach notification

Veri İşleyen, bir ihlalden haberdar olduktan sonra **`[72] saat` içinde** Veri Sorumlusu'na yazılı bildirimde bulunur. Bildirim aşağıdakileri içerir (KVKK İhlal Bildirim Formu + GDPR m.33(3) parametreleriyle uyumlu):

- İhlalin niteliği, tahmini etkilenen veri sahibi sayısı, etkilenen kayıt kategorileri.
- Olası sonuçlar.
- Alınan veya alınması planlanan önlemler.
- İrtibat noktası.

Veri Sorumlusu, KVKK m.12(5) uyarınca KVK Kurulu'na ve etkilenen veri sahiplerine bildirim yapma yükümlülüğüne sahiptir; Veri İşleyen bu bildirimde teknik detayları sağlamakla yükümlüdür.

*The Processor notifies the Controller in writing within `[72] hours` of becoming aware of a breach, with the parameters required by KVKK art. 12 and GDPR art. 33(3). Onward notification to the regulator is the Controller's responsibility, supported by the Processor.*

---

## 10. Denetim hakları / Audit rights

Veri Sorumlusu, makul önceden yazılı bildirimle (en az **`[30] gün`**) yılda bir kez Veri İşleyen'in işbu sözleşmeye uyumunu denetleme veya bağımsız üçüncü tarafa denetlettirme hakkına sahiptir. Denetim:

- Çalışma saatleri içinde yapılır.
- Veri İşleyen'in operasyonlarına orantısız müdahale yaratmaz.
- Diğer müşterilerin verilerini açığa çıkarmaz.

Acil ihlal durumunda bu süre kısaltılabilir.

*The Controller may audit the Processor's compliance no more than once per year on at least `[30] days'` written notice, during business hours, and without disproportionate disruption. Shorter notice applies to active breaches.*

---

## 11. Sorumluluk sınırı / Liability cap

Veri İşleyen'in işbu sözleşmeden kaynaklanan toplam sorumluluğu, ihlal kasti veya ağır kusur içermediği sürece, ana sözleşme tahtında geçerli olan **`[12 ay sözleşme bedeli]`** ile sınırlıdır. KVKK ve GDPR'nin emredici hükümleri, veri sahiplerine karşı doğrudan sorumluluk ve ağır ihmal halleri saklıdır.

*The Processor's aggregate liability under this Agreement is capped at `[12 months of fees under the master agreement]`, save for wilful misconduct, gross negligence, and direct statutory liability to data subjects under KVKK and GDPR.*

---

## 12. Süre ve fesih / Term and termination

İşbu sözleşme, Veri Sorumlusu ile Veri İşleyen arasındaki ana hizmet sözleşmesi (master agreement) ile **eş süreli** (co-terminus) olarak yürürlüktedir. Ana sözleşme sona erdiğinde:

- Veri İşleyen, Veri Sorumlusu'nun seçimine göre kişisel verileri **`[30] gün`** içinde geri verir veya silinmesini sağlar (anonimleştirme dahil).
- Veri İşleyen, silmenin tamamlandığına dair yazılı teyit verir.
- Mevzuatın gerektirdiği saklama yükümlülükleri (örn. yasal kayıt) bu hükümden istisnadır; bu kayıtların kapsamı ve süresi yazılı olarak Veri Sorumlusu'na bildirilir.

*Co-terminus with the master agreement. On termination, the Processor returns or deletes data within `[30] days` per Controller's choice, with written confirmation. Statutory retention is the only carve-out and must be disclosed.*

---

## 13. Geçerli hukuk ve uyuşmazlık / Governing law and disputes

İşbu sözleşme **Türkiye Cumhuriyeti hukukuna** tabidir ve **`[İSTANBUL]` Mahkemeleri ve İcra Daireleri** münhasıran yetkilidir. AB veri sahiplerini etkileyen meselelerde GDPR'nin doğrudan uygulanabilir hükümleri saklıdır.

*Governed by the laws of the Republic of Turkey; exclusive jurisdiction of the courts and execution offices of `[İSTANBUL]`. Directly applicable GDPR provisions are reserved for matters affecting EU data subjects.*

---

## 14. İmzalar / Signatures

**Veri Sorumlusu / Data Controller**
İmza / Signature: __________________________
Ad-Soyad / Name: `[ ]`
Unvan / Title: `[ ]`
Tarih / Date: `[ ]`

**Veri İşleyen / Data Processor (TriAIge)**
İmza / Signature: __________________________
Ad-Soyad / Name: `[ ]`
Unvan / Title: `[ ]`
Tarih / Date: `[ ]`

---

### Ekler / Annexes

- **Ek-1 / Annex 1:** Saklama süreleri tablosu (Madde 5'in detaylı dökümü).
- **Ek-2 / Annex 2:** Hastane-özel ek güvenlik kontrolleri (Madde 6 üzerine).
- **Ek-3 / Annex 3:** Veri sahibi başvuru süreci akış şeması.
- **Ek-4 / Annex 4:** İhlal bildirim şablonu (KVKK Kurulu formu + iç akış).
