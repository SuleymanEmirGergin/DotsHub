# IP Transfer Plan — TriAIge

> **Disclaimer.** Bu doküman bir avukat metni değildir. Tüm imzalanacak sözleşmeler (Founder IP Assignment, Trademark başvuru dilekçeleri, ortaklar sözleşmesi maddeleri) bir Türkiye-qualified avukat tarafından nihayetlendirilmelidir. Aşağıdaki şablon yapıları sadece içeriksel checklist'tir, hukuki metin değildir.

---

## 1. Niçin önemli — bir cümlede

Bir healthtech şirketi, kendi temel IP'sine sahip olmadan **ne yatırım turu kapatabilir, ne de ciddi bir hastane sözleşmesi imzalayabilir**. Pre-Series-A due diligence'ın ilk %20'si "şirket kodun, marka adının, domain'in, hosting'in sahibi mi?" sorusuna cevap arar. Şu an TriAIge'in cevabı **"hayır — kurucu kişisel hesaplar"** olduğu için bu standart bir cleanup'tır.

**Zamanlama: AŞ kuruluşundan hemen sonra, ilk müşteri sözleşmesinden önce.**

---

## 2. Ne devredilmeli? — kapsamlı envanter

### 2.1 Kaynak kod
- **GitHub repo (ana monorepo):** `backend/`, `mobile/`, `dashboard/`, `docs/`, `scripts/`, `config/`
- Repo adı: yakın gelecekte değişecek (bkz. `docs/EXTERNAL_RENAME_CHECKLIST.md`); rebrand ile birlikte transfer planlayın
- İlişkili repolar (varsa): infrastructure-as-code, marketing site, vb.

### 2.2 Marka & alan adları
- **Wordmark:** "TriAIge" — TPMK marka tescili (bkz. §6)
- **Logo / görsel kimlik:** SVG/PNG asset'leri (mevcut tasarımcı dosyaları, Figma kütüphanesi varsa)
- **Domain'ler:** kontrol edilmesi gereken liste:
  - `triaige.com`
  - `triaige.co`
  - `triaige.com.tr`
  - `triaige.app`
  - `triaige.io`
  - `triaige.ai`
  - rakip / yanlış-yazım defansif alan adları (örn. `triage.com.tr`)
  - Bunlardan hangisi alındı? Hangisinin sahibi hangi kurucunun adı/kart bilgisi?
- **Sosyal handle'lar:** Twitter/X, LinkedIn (company page + personal pages link'lenmesi), Instagram, YouTube — şirket adına geçirilmeli

### 2.3 Veri ve veri tabanı hakları
- **Curated medical data:**
  - `backend/app/data/curated_conditions.json` (varsa) — orijin: Kaggle ingestion + manuel curation
  - ICD-10 mapping'leri — orijin: WHO ICD-10 (kamuya açık ama versiyon bağımlılığı sorgulanmalı)
  - Symptom-to-condition graph'ları
- Üçüncü taraf lisans şartları kontrolü:
  - Kaggle dataset'ler: hangi lisans? (CC0, CC-BY-NC, vb.) — `docs/KAGGLE_INGEST_AUTOMATION.md` ve `docs/KAGGLE_DESCRIPTION_TRANSLATION_DECISION.md` referansta
  - "Non-Commercial" lisanslı veri varsa **şu an pilot için sorun değil ama Series A öncesi temizlenmelidir**
- **Kullanıcı verisi (PII / sağlık verisi):** kuruluş öncesi gerçek hasta verisi YOK olmalı — varsa, KVKK ihlali olduğu için ayrı bir mesele; kurulum aşamasında pilot başlamadan önce siliniyor olmalı

### 2.4 SaaS / hosting / cloud hesapları
| Sağlayıcı | Kullanım | Şu anki sahibi (tipik) | Yeni sahibi |
|---|---|---|---|
| GitHub | Source code | Kurucu kişisel | TriAIge AŞ Org |
| Fly.io | Backend hosting | Kurucu kişisel | TriAIge AŞ |
| Vercel | Dashboard / web hosting | Kurucu kişisel | TriAIge AŞ |
| Supabase | DB + auth | Kurucu kişisel | TriAIge AŞ Organization |
| Sentry | Error monitoring | Kurucu kişisel | TriAIge AŞ Organization |
| Grafana Cloud | Metrics / observability | Kurucu kişisel | TriAIge AŞ |
| Expo (EAS) | Mobile build/submit | Kurucu kişisel | TriAIge AŞ |
| Apple Developer Program | iOS App Store | **Kurum hesabı zorunlu** — DUNS gerekli | TriAIge AŞ (DUNS kayıt ettir) |
| Google Play Console | Android | Geliştirici hesabı | TriAIge AŞ |
| Domain registrar (Cloudflare / Namecheap / GoDaddy) | DNS + domain | Kurucu kişisel | TriAIge AŞ |
| Email (Google Workspace) | İş e-postası | Varsa kurucu kişisel | TriAIge AŞ Workspace |
| LLM sağlayıcısı (Anthropic / OpenAI / vs.) | API key + billing | Kurucu kart | TriAIge AŞ kart |
| Notion / Linear / Slack | İç dokümantasyon + iletişim | Kurucu kişisel | TriAIge AŞ workspace |
| Figma | Design | Kurucu kişisel | TriAIge AŞ |
| Cloudflare | DNS + CDN + WAF | Kurucu kişisel | TriAIge AŞ |

> **"Auxiliary account leak" gotcha:** Sentry, Grafana, EAS, Cloudflare — küçük hesaplar — devir sırasında en sık atlananlardır. Devir sonrası kurucu kişisel e-postasından "TriAIge production crashed" alert'i geldiğinde DD reviewer için kötü sinyal. Tam liste tutun, her birini tek tek geçirin.

### 2.5 Kontratlar / yazılı taahhütler
- Şu anda imzalanmış 3rd-party herhangi bir NDA, MoU, LOI var mı? (Acıbadem / Eczacıbaşı tarafıyla yazışma seviyesinde mi yoksa imzalı bir şey var mı?)
  - İmzalı bir şey varsa: kurucunun şahsında mı şirket adına mı? Şirket adına değilse novation (sözleşme yenilemesi) gerekir
- Mevcut sales-sheet (`docs/templates/SALES_SHEET.md`) ve LOI template (`docs/templates/LOI_TEMPLATE.md`) — yeni AŞ adına revize edilmeli

---

## 3. Mekanik — adım adım nasıl devredilir

### 3.1 Founder IP Assignment Agreement (kurucu IP devir sözleşmesi)

Her kurucu, kuruluş öncesinde yaptığı **tüm fikri mülkiyet işini** şirkete devreder. Şablon yapısı:

```
SÖZLEŞMENİN TARAFLARI
- Devreden (kurucu kişi): [İsim, T.C. Kimlik No, adres]
- Devralan: TriAIge AŞ [vergi no, ticaret sicil no, adres]

1. KAPSAM
- 1.1 "Pre-incorporation IP" — şirket kuruluşundan önce kurucu tarafından
  yaratılan, TriAIge ürün/hizmetiyle ilgili tüm:
    a) kaynak kod ve yazılım eserleri
    b) tasarım, grafik, içerik, metin
    c) marka, logo, isim, alan adı
    d) veri tabanı içerikleri ve seçim/düzenleme hakları
    e) ticari sırlar, know-how
    f) patentlenebilir veya patentlenmiş buluşlar (varsa)
- 1.2 İlişkili tüm hesaplar (§2.4 envanteri)

2. DEVİR
- 2.1 Kurucu, yukarıda tanımlı tüm IP'yi mali ve manevi haklarıyla
  birlikte (FSEK m.48 ve m.52 uyarınca yazılı şekilde) şirkete
  süresiz, kayıtsız, geri alınamaz şekilde devreder.
- 2.2 Kurucu, üçüncü tarafların hak iddiası olmadığını taahhüt eder.

3. GELECEK ESERLERİN OTOMATİK DEVRİ
- 3.1 Kurucu hizmet ilişkisi süresince yarattığı, şirket faaliyet
  alanına giren tüm IP'nin mali haklarının doğduğu anda şirkete
  intikal edeceğini kabul eder. (FSEK m.18/2 hizmet eseri çerçevesi)

4. BEDEL
- 4.1 Devir bedeli: kurucunun şirketteki pay sahipliği ile karşılıklıdır.
  (Veya: cüzi nominal bedel, ortaklar sözleşmesi ile çakışmamak için.)

5. TEMSİL VE TAAHHÜTLER
- 5.1 Kurucu, devre konu IP'nin tek/münhasır sahibi olduğunu, üçüncü
  taraf lisans/iş ilişkisi nedeniyle çatışan bir hak bulunmadığını
  beyan eder.

6. UYUŞMAZLIK ÇÖZÜMÜ
- 6.1 İstanbul mahkemeleri (veya ortaklar sözleşmesinde belirtilen
  forum / tahkim).
```

> **Lawyer flag — kritik:**
> 1. **FSEK manevi hak**: TR Fikri Mülkiyet hukukunda manevi haklar (eserin sahibi olma hakkı) **devredilemez** — sadece kullanma hakkı verilebilir. Sözleşmenizde bu nüansı doğru ifade edin.
> 2. **3.1 — gelecek eserler clause**: bu cümle olmadan, kuruluş sonrası kurucu commit'lerinin şirkete vest etmesi otomatik değildir. Yatırımcı DD bunu özellikle arar.
> 3. **5.1 — third-party clean check**: kurucuların bir önceki işyerinden taşınan kod yok mu? (önceki işveren mülkiyet iddiası)

### 3.2 GitHub repo devri

`Settings → Transfer ownership` ile mevcut kişisel hesaptan **TriAIge AŞ GitHub Organization**'a transfer.

Adımlar:
1. AŞ kuruluş tamamlandıktan sonra TriAIge AŞ adına yeni GitHub Organization oluştur
2. Billing kart bilgisi şirket kartı olsun
3. Eski private repo → Settings → Transfer → yeni org seç
4. Tüm kurucuları yeni org'a "Owner" rolüyle ekle
5. Eski personal account'tan repo erişimi kaldırılır (otomatik)
6. CI/CD secret'lar yeniden bağlanır (GH Actions secrets her org'a özel)

> **Gotcha:** GitHub Actions secrets transfer edilmez. Yeni org'da elle yeniden eklenmesi gerekir. CI green olana dek staging'i kapalı tutun.

### 3.3 SaaS hesap devri (her biri için)

Genel pattern:
1. Yeni AŞ adına yeni hesap aç (kurumsal e-posta: founders@triaige.com vb.)
2. Eski hesaptan billing'i kapatma + verileri export
3. Yeni hesapta production setup'ı çoğalt (config, secret'lar, integrations)
4. DNS / API endpoint switchover
5. Eski hesabı kapatma — **24 saat bekleyip alert akışını gözle**, sonra kapat

Sağlayıcıya özel notlar:
- **Apple Developer Program**: kurucu kişisel hesaptan kurumsala devir **mümkün değil**, yeni Organization Account oluşturulur ve uygulama "transfer app" akışıyla geçirilir. **DUNS numarası gerekir** (D&B'den, ücretsiz, ~2 hafta)
- **Google Play Console**: "Account transfer" formu doldurulur, Google manuel onaylar (~1-2 hafta)
- **Supabase**: Organization devir destekleniyor, ama branch/staging environment'lar için ek setup
- **Stripe (varsa)**: yeni Stripe hesabı zorunlu, eski hesapla account merge yok
- **Anthropic API / OpenAI**: yeni org account aç, eski API key'leri rotate et (zaten security best practice)

### 3.4 Domain devri

- Cloudflare/Namecheap → Account transfer
- Veya: domain'i kurucu hesabında bırak ama "registrant" kontağı şirkete değiştir + admin contact'ı şirkete değiştir
- En temizi: tam transfer

### 3.5 Email / Google Workspace

- Yeni Workspace tenant'ı `triaige.com` domain'inde aç
- Eski kurucu kişisel e-postalarındaki TriAIge yazışmalarını arşivle (forward + label)
- Kurucu e-postaları artık `firstname@triaige.com`

---

## 4. Marka tescili — TPMK

### 4.1 Aciliyet
**Yüksek.** "TriAIge" ismi şu an açık (rebrand sonrası) — ama bir rakip / squatter dosyalarsa yeniden marka değiştirmek **kuruluştan daha pahalıdır**. Pilot konuşmaları başlamadan dosyalanmalı.

### 4.2 Süreç
1. **Ön araştırma (preliminary search)** — TPMK Marka Araştırma Sistemi üzerinden ücretsiz benzerlik taraması
   - "TriAIge", "Triaige", "Triajai", "Triag-AI", "AI Triage TR" varyasyonlarını tara
2. **Sınıflandırma** — Nice Sınıflandırması:
   - **Sınıf 9**: bilgisayar yazılımı, mobil uygulamalar
   - **Sınıf 42**: yazılım hizmetleri, SaaS, teknik danışmanlık
   - **Sınıf 44**: sağlık hizmetleri (eğer doğrudan sağlık hizmeti pazarlaması yapılacaksa — dikkat: bu §5.2'de tanımlanan "biz pre-triage'iz, tıbbi cihaz değiliz" pozisyonu ile çelişebilir; sınıf 44 sınırlı talepedilmeli)
   - Genelde 9 + 42 yeter
3. **Başvuru** — TPMK online portal; başvuru ücreti (~₺1.500–3.000, verify current)
4. **Yayın ve itiraz süresi** — 2 ay
5. **Tescil** — itiraz yoksa ~6-12 ay; itiraz varsa daha uzun

### 4.3 International extension
- **Madrid Protokolü** üzerinden uluslararası başvuru — TR tescili sonrası 6 ay içinde priority date korur
- Pilot AB ülkelerine açılırken (Almanya, Hollanda) ayrı başvuru + EUIPO (Avrupa Birliği Marka Ofisi)
- ABD: USPTO ayrı; "intent to use" başvurusu yapılabilir

> **Lawyer flag:** Marka avukatı (specialised) farklıdır — şirket avukatı her marka avukatı değil. TPMK'ya ön tescil + lokalizasyon birikimi olan biriyle çalışın.

### 4.4 Maliyet ballpark
| Kalem | TL aralığı (verify current) |
|---|---|
| TPMK başvuru ücreti (sınıf 9 + 42) | 3.000 – 6.000 |
| Avukat ücreti (başvuru + takip) | 5.000 – 15.000 |
| Madrid başvurusu (sonradan) | $1.000+ baz + sınıf başına |
| **Toplam TR-only** | **~₺10.000 – ₺20.000** |

---

## 5. Sıralama ve zamanlama

```
Hafta 0:  AŞ kuruluş tamamlanır
Hafta 1:  Founder IP Assignment imzalanır (3 kurucu × 1 sözleşme)
Hafta 1:  GitHub Org devri başlatılır
Hafta 2:  SaaS hesap devirleri (paralel: Vercel, Fly, Supabase, Sentry, vd.)
Hafta 2:  Domain registrant değişikliği
Hafta 2:  Apple/Google developer hesap devir başvuruları (uzun sürer; başlatmak önemli)
Hafta 3:  TPMK marka başvurusu
Hafta 3:  Açık/kapalı kontrat envanteri (NDA'lar, MoU'lar) → şirket adına novation
Hafta 4:  Tüm cutover doğrulanır; eski personal hesaplar arşivlenir
Hafta 4:  IP Cleanup Memo — DD ready (yatırımcıya gösterilebilir özet)
```

---

## 6. Sıkça yapılan hatalar (don't list)

1. **Auxiliary account leak** — Sentry, Grafana, EAS gibi küçük hesaplar atlanır; aylar sonra "founder@gmail.com" alert'i gelir
2. **"Future inventions" clause yokluğu** — kuruluş sonrası kod commit'leri otomatik şirkete vest etmez; explicit clause gerekir (§3.1 / Madde 3)
3. **Marka başvurusunu erteleme** — pilot konuşmaları başlamadan dosyalanmalı; "yatırım sonrası" deyince 6 ay kaybedersin
4. **Domain registrar billing kart bilgisi kurucuda kalır** — kart süresi dolduğunda domain expire eder; horror story
5. **Kaggle / 3rd-party veri lisansının taranmaması** — Series A DD'sinde "non-commercial license veri kullandınız mı?" sorusuna cevap olmalı
6. **Open-source license review yapmama** — bkz. §7
7. **Manevi hak / FSEK m.48 nüansının atlanması** — TR'de "her şeyi devrettim" demek kafi değil; doğru dil önemli (lawyer flag)

---

## 7. Open-source license review

Mevcut bağımlılıkların hızlı taraması (TriAIge repo'su):

### 7.1 Backend (`backend/requirements.txt`)
| Paket | Lisans | Risk |
|---|---|---|
| fastapi | MIT | Temiz |
| uvicorn | BSD-3-Clause | Temiz |
| pydantic | MIT | Temiz |
| sqlalchemy | MIT | Temiz |
| asyncpg | Apache-2.0 | Temiz |
| redis (py client) | MIT | Temiz |
| supabase (py client) | MIT | Temiz |
| sentry-sdk | BSD-2-Clause | Temiz |
| prometheus-client | Apache-2.0 | Temiz |
| **fpdf2** | LGPL-3.0+ | **Yumuşak Copyleft** — dynamic linking ile kullanım sorun değil ama uyarı: requirements.txt'de **explicit not** "reportlab GPL-adjacent olduğu için fpdf2 seçildi" diyor; bu doğru bir refleks ama LGPL'in kendisi de DD'de bir not düşürür. Genellikle problem değil; "embedded library only, no static linking" pozisyonu yeterli |
| httpx, tenacity, psycopg | MIT/BSD | Temiz |

**Aksiyon:** fpdf2'nin LGPL durumu Series A öncesi avukat onayından geçirilmeli. **Kullanım dynamic linking + ayrı paket** olduğu için "sadece kullanım, kapsamına alma yok" pozisyonu büyük ihtimalle savunulabilir.

### 7.2 Dashboard (`dashboard/package.json`)
Tüm paketler — Next.js, React, Radix UI, Supabase, Tailwind, Playwright, recharts, axe-core — **MIT veya Apache-2.0**. Temiz.

### 7.3 Mobile (`mobile/package.json`)
Tüm paketler — Expo, React Native, Sentry, expo-* aileleri, zustand — **MIT veya Apache-2.0**. Temiz.

### 7.4 Genel sonuç
**Yüksek riskli (GPL/AGPL/SSPL) bağımlılık yok.** Tek bayrak: fpdf2 LGPL. Bu mevcut haliyle ürünü etkilemez ama DD memo'da not edilebilir.

> **Aksiyon (Hafta 3):** `audit-licenses` script'i (örn. `pip-licenses`, `npx license-checker`) CI'ya eklenip every-PR taraması açılırsa, gelecekte yeni copyleft bağımlılık eklenmesi önlenir.

---

## 8. DD-ready "IP Cleanup Memo" — özet şablonu

```
TriAIge AŞ — IP Cleanup Memo
Tarih: [date]

1. Kuruluş tarihi: [date]
2. Kurucu IP devir sözleşmeleri: 3/3 imzalı ([date])
3. GitHub Organization: triaige-org, billing AŞ kartı
4. Aktif marka başvuruları: TPMK [başvuru no], sınıf 9+42, [tarih]
5. Domain envanteri: [N] alan adı, hepsi AŞ registrant
6. SaaS hesap envanteri: tam (ek dosya)
7. Kullanılan 3rd-party veri: [Kaggle X dataset, lisans Y]
8. OSS lisans incelemesi: temiz (Hi̇gh-risk copyleft yok); LGPL not düşülmüş
9. Önceki işveren çatışması: yok (kurucu beyanı, sözleşme m.5.1)
10. Bekleyen IP işlemleri: [Madrid Protokolü TBD]
```

Bu memo Series A öncesi yatırımcıya `data room`'da `01-corporate/IP-cleanup.md` olarak konur.

---

**Son not.** Bu doküman bir checklist'tir, hukuki sözleşme değildir. Founder IP Assignment, marka başvurusu, ortaklar sözleşmesi entegrasyonu — hepsi avukat tarafından nihayetlendirilmelidir.
