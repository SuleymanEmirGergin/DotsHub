# TR Entity Setup — TriAIge

> **Disclaimer.** This document is an internal founder playbook, not legal advice. Every step labelled below as "lawyer" or "notary" must be confirmed by a Türkiye-qualified avukat / mali müşavir. Numbers (capital floors, fees, timelines) are sourced from public guidance and founder-network ballparks; **verify current figures with KGK, Hazine ve Maliye Bakanlığı, and Ticaret Sicil Müdürlüğü before signing anything**.

Audience: TriAIge'in 3 kurucu ortağı. Hedef: AŞ kurulumunu sıfırdan, sırayla, healthtech-spesifik gotcha'lar ile birlikte planlamak.

---

## 1. Karar: LtdŞti vs AŞ

**Öneri: Anonim Şirket (AŞ).**

| Boyut | LtdŞti | AŞ | Bizim için |
|---|---|---|---|
| Min. sermaye | ₺50K (ballpark — verify current) | ₺250K (2024 zammı sonrası — verify current) | AŞ sermayesi yüksek ama yatırımcı sözleşmeleri için gerekli |
| Pay devri | Notarial + Sicil + ortaklar onayı; ağır | Pay defterine kayıt yeter; hızlı | AŞ — Series A için kritik |
| Sorumluluk | Sermaye ile sınırlı + bazı vergi-borç istisnaları kurucuya rücu eder | Sermaye ile sınırlı, daha temiz kalkan | AŞ |
| Pay sınıfları | Tek sınıf | İmtiyazlı / adi pay ayrımı yapılabilir | AŞ — kurucu vesting + yatırımcı preferred için lazım |
| ESOP | Pratik değil | Standart | AŞ |
| Halka açılma | Kapalı | Açılabilir | Uzak ihtimal ama yine AŞ lehine |

LtdŞti'nin tek somut avantajı düşük min. sermaye. Sermaye toplamayı hedefleyen bir healthtech için bu marjinal kazanç, sonradan AŞ'ye dönüşüm maliyetinin (notarial işlemler + tip-değişikliği vergisi + 6-12 ay gecikme) yanında eridir.

**Karar:** AŞ olarak kur.

---

## 2. Sermaye yapısı

### 2.1 Tutar
- AŞ asgari sermaye: **₺250.000** (verify current — son zam 2024)
- 1/4'ü kuruluşta bloke (₺62.500) — geri kalanı 24 ay içinde tamamlanır
- Healthtech için en az ₺250-500K aralığı önerilir; Acıbadem'lere "biz ciddi bir şirketiz" sinyali

### 2.2 Kurucu dağılımı — iki senaryo

**A) Eşit (33.3 / 33.3 / 33.3)**
- En basit; üç kurucu da eşit imtiyazlı
- Risk: tie-breaker yok. Sözleşmede deadlock çözümü yazılmazsa yönetim kilitlenir

**B) Vesting modelli**
- Her kurucu 33.3% hak ediş ile başlar; 4 yıl üzerine vest, 1 yıl cliff
- Pre-incorporation iş yükü dengesizse ufak ayrışma (örn. 35/33/32) düşünülebilir
- Cliff öncesi ayrılırsa hisse şirkete geri döner — gelecek yatırımcı için kritik
- **Tercih: B.** Series A öncesi cleanup'ı şimdiden yap

### 2.3 Ek baştan ayrılması gereken havuzlar
- **ESOP havuzu:** kuruluşta %10–15 (önerilen: %12 başlangıçta, Series A öncesi top-up)
  - Vesting: 4 yıl, 1 yıl cliff (TR startup standardı)
  - AŞ pay sınıfı olarak teknik olarak "tahsisli" pay — pay defterine vakfedilir, dağıtım Yönetim Kurulu kararıyla yapılır
- **Klinik danışman ayrımı:** %0.25–0.75 (bkz. `ADVISOR_OUTREACH.md`)

> **Lawyer flag:** Vesting + reverse vesting clause **anasözleşmeye değil, ortaklar sözleşmesine (SHA)** girer. Anasözleşmede bunu zorlamayın — Sicil reddeder.

---

## 3. Kuruluş adımları (sıralı)

| # | Adım | Süre | Kim yapar | Lawyer? |
|---|---|---|---|---|
| 1 | Anasözleşme draft | 1-2 hafta | Avukat | **Zorunlu** |
| 2 | Noter tasdiki (anasözleşme + imza beyanları) | 1-2 gün | Noter | Hayır |
| 3 | Ticaret Sicil Müdürlüğü tescili | 5-10 iş günü | Sicil | Hayır (avukat dosyalar) |
| 4 | Vergi Dairesi açılış | 1 hafta | Mali müşavir | Hayır |
| 5 | SGK işyeri sicili + Bağ-Kur (4/b kurucular için) | 1 hafta | Mali müşavir | Hayır |
| 6 | Banka hesabı açılışı + sermaye blokajı serbestleştirme | 3-5 iş günü | Banka | Hayır |
| 7 | KEP adresi alınması | 1 gün | KEP sağlayıcısı | Hayır |
| 8 | e-Tebligat aktivasyonu (zorunlu) | 1 hafta | GİB | Hayır |
| 9 | e-Fatura / e-Arşiv başvurusu | 1-2 hafta | GİB / özel entegratör | Hayır |
| 10 | **VERBİS kaydı** (KVKK Veri Sorumluları Sicili) | 1 gün | Kurucu | Önerilir |

**Toplam paralel-akış süresi: 4–6 hafta** (1, 2, 3 sıralı; 4–10 paralel).

### 3.1 Anasözleşme (Adım 1) — neye dikkat

- Faaliyet konusu: "Yapay zekâ tabanlı sağlık yazılımı geliştirme, teknik servis, danışmanlık" — geniş bırak ama **"tıbbi tanı"** ifadesinden kaçın (reklasifikasyon riski; bkz. §6).
- Yönetim kurulu: 3 kurucu (single-class) veya 1 kurucu CEO + 2 üye. Series A'da yatırımcı 1-2 koltuk talep edecek; başlangıçta esnek bırak.
- Genel kurul nisapları: yatırım turlarında değişecek — varsayılan TTK hükümleriyle başla.

### 3.2 Noter & Sicil (Adım 2-3)

- İmza beyanı (imza sirküleri), anasözleşme tasdiki, taahhütname.
- Sicil'e MERSİS üzerinden online — ama eklerin imzalı/taranmış halleri elden teslim edilir.

### 3.3 Banka hesabı (Adım 6)

Önerilen bankalar (founder-network deneyimi, son 18 ay):
- **Garanti BBVA** — startup-friendly, online açılış, dolar/euro alt-hesap kolay
- **DenizBank** — startup desteği iyi, USD-denominated SaaS giderleri için Visa/Mastercard çıkış kart kolay
- **TEB / İş Bankası** — daha klasik; kurumsal SLA iyi ama hız yavaş

İlk hesap açılışında sermaye blokajını **adım 3'ten önce** yapamazsınız (Sicil tescili gerekir). Akış: Sicil → blokajı tut → blokajı kaldır → hesap açık.

### 3.4 KEP + e-Tebligat (Adım 7-8)

AŞ için KEP adresi **zorunlu**. PTT KEP veya özel sağlayıcılar (TürkKEP, eKep). Yıllık ~₺200–500.

### 3.5 VERBİS — healthtech için kritik (Adım 10)

KVKK m.6 kapsamında **özel nitelikli kişisel veri** (sağlık verisi) işleyen tüm veri sorumluları VERBİS'e kayıt olmak zorundadır. Eşik istisnaları (yıllık 100+ çalışan / 100M TL bilanço) sağlık verisinde **uygulanmaz** — küçük olsanız bile kayıt zorunlu.

- Süre: kuruluştan / faaliyete başlamadan **30 gün içinde** kayıt
- Kayıt: KVKK web portalı üzerinden online
- Veri envanteri (Veri İşleme Envanteri) hazır olmalı — TriAIge için: PII (isim, telefon, e-posta, lokasyon) + sağlık verisi (semptom, ICD-10 kodları, triaj çıktıları)
- Mevcut repo dokümanı: `docs/PRIVACY_AND_SECURITY.md` (KVKK hazır olduğu burada belgeleniyor; VERBİS kaydı bu dokümanın yerine geçmez)

> **Cezalar:** VERBİS'siz özel-nitelikli veri işleme, idari para cezası ₺1M+ aralığında (verify current upper bound). Bu, tek başına Series A'yı yavaşlatabilecek bir bulgu.

---

## 4. Tahmini maliyet

| Kalem | TL aralığı (verify current) |
|---|---|
| Avukat (anasözleşme + danışmanlık) | 30.000 – 80.000 |
| Noter (tasdik + imza beyanları) | 5.000 – 15.000 |
| Ticaret Sicil + MERSİS harçları | 5.000 – 12.000 |
| Mali müşavir kuruluş ücreti | 10.000 – 25.000 |
| Mali müşavir aylık | 5.000 – 15.000 / ay |
| KEP yıllık | 200 – 500 |
| Banka açılış | ücretsiz veya ₺500 |
| **Tek seferlik toplam (sermaye hariç)** | **~₺50.000 – ₺130.000** |
| **Sermaye blokajı (1/4)** | ₺62.500 (geri serbest kalır) |

Founder-network ballpark: **toplam tek-seferlik ₺75–100K all-in** sık görülen aralık. Yüksek tarafa hazır olun; pazarlık yeri var.

---

## 5. Healthtech'e özel gotcha'lar

### 5.1 VERBİS — non-optional (yukarıda anlatıldı)
Tek cümle: kuruluştan 30 gün içinde kayıt, gecikme = ceza.

### 5.2 Sağlık Bakanlığı / Tıbbi Cihaz sınıflandırması

**Şu an TriAIge'in legal pozisyonu (önemli, doğru kavrayın):**

TriAIge **pre-triage** sağlar — yani:
- Aciliyet seviyesini sınıflandırır (Yeşil / Sarı / Kırmızı)
- Öneri verir ("acile gidin", "GP'ye gidin", "bekleyebilirsiniz")
- **Tanı koymaz**
- **Tedavi reçetelendirmez**

Bu pozisyon kasten seçildi çünkü Tıbbi Cihaz Yönetmeliği (TCY, AB MDR'ın TR transpozisyonu) Madde 2 + Annex VIII tıbbi cihaz tanımı **"tanı, önleme, izleme, tedavi"** için kullanılan yazılımı kapsar. "Triaj öncesi karar destek aracı" şu an bu kapsama girmez ve **TİTCK (Türkiye İlaç ve Tıbbi Cihaz Kurumu) onayı gerektirmez**.

**Dokümante et:** kuruluştan itibaren `PRIVACY_AND_SECURITY.md` ve pazarlama dokümanlarında TriAIge'in **pre-triage** olarak konumlandırıldığı, **"diagnosis" / "tanı koyar" / "tedavi önerir"** ifadelerinin **asla** kullanılmadığı bir tutarlılık testinin geçtiği. Bu, TİTCK'nın muhtemel bir reklasifikasyon talebine karşı en güçlü savunmanız.

**Future-watch:** Eğer TriAIge bir gün açıkça tanı çıktısı verirse → MDR Class IIa veya IIb tıbbi cihaz olarak sınıflandırılır → CE marking + TİTCK kaydı + klinik validasyon + ISO 13485 + IEC 62304 yazılım yaşam döngüsü uyumu gerekir. Bu 12+ ay ve 6 haneli € maliyet.

### 5.3 Sağlık Verisi yurt dışına çıkarımı
KVKK m.9: özel nitelikli verinin yurt dışına aktarımı **açık rıza + Kurul izni** veya **yeterli ülke** statüsü ister. ABD ve büyük LLM sağlayıcıları "yeterli ülke" değil. Yapı: PHI'yi backend'e kaydetmeden önce maskeleme + LLM'ye anonim payload gönderme. Bu konu zaten `PRIVACY_AND_SECURITY.md` ve PII redaction katmanında ele alınmış olmalı — VERBİS bildirimi ile uyumlu olduğunu doğrulayın.

---

## 6. ESOP yapısı (önerilen)

| Boyut | Değer |
|---|---|
| Pre-Series-A havuz büyüklüğü | %10–15 (öneri: %12) |
| Vesting | 4 yıl, 1 yıl cliff |
| Strike fiyatı | Mevcut adil değer (FMV) — kuruluşta nominal, sonradan Series A son post-money'e göre revize |
| İlk grant'lar | Klinik danışman (%0.25–0.75), key engineering hire (%0.5–1.5), ilk sales hire (%0.5–1.0) |
| Form | TR'de en yaygın yapı: phantom share / sanal pay ile başla, AŞ Yönetim Kurulu kararıyla gerçek pay grant'a dönüş — vergisel basitlik |

> **Lawyer flag:** TR'de ESOP'un "stock option" olarak vergilendirilmesi 2018 sonrası daha berraklaştı ama hâlâ uygulamada bazı avukatlar phantom-share + cash-settled yapıyı tavsiye ediyor. Vergi danışmanı + avukatla netleştirin.

Referans: **Türkiye startup ESOP playbook**'ları için Startup Türkiye, Galata Business Angels, KWORKS publications gibi kaynakları taramayı önerin (founder kendisi).

---

## 7. İlk-ay operasyonel checklist

### Hafta 1 (kuruluş hemen sonrası)
- [ ] Banka hesabı operasyonel; sermaye serbest
- [ ] Mali müşavir kontratı imzalı; aylık paket (KDV beyannamesi, muhtasar, gider belgeleri) net
- [ ] **Muhasebe yazılımı seçimi:**
  - **Paraşüt** — early-stage favori; abonelik bazlı, e-fatura entegre, mobil
  - **Logo Lojist / Logo İşbaşı** — geleneksel, derin
  - **Mikro Fly** — küçük-orta ölçek
  - Öneri: **Paraşüt** (3 kurucu, mobil-first, çok kullanıcı-yetki)
- [ ] e-Fatura entegratörü seçildi (Logo, Uyumsoft, Foriba, Paraşüt entegre)
- [ ] KEP adresi paylaşıldı

### Hafta 2-4
- [ ] **VERBİS kaydı tamamlandı** (en geç 30. günde)
- [ ] KVKK Aydınlatma Metni + Açık Rıza Metinleri publish edildi (mobil app + web)
- [ ] Hukuk danışmanı retainer'ı (saatlik ya da paketle) sözleşmeli
- [ ] Defter tasdikleri (yevmiye + envanter + pay defteri + yönetim kurulu karar defteri) noterli
- [ ] SGK işyeri açılış bildirim formu verildi
- [ ] Bağ-Kur (4/b) kayıtları kurucular için aktif

### İlk-ay-sonu kontrolü
- [ ] İlk yönetim kurulu kararı (banka imza yetkilileri, e-imza yetkililer) deftere işlenmiş
- [ ] Kurucu IP devir sözleşmeleri imzalanmış (bkz. `IP_TRANSFER_PLAN.md`)
- [ ] GitHub org devri tamamlanmış (bkz. `IP_TRANSFER_PLAN.md`)
- [ ] Domain kayıt sahipliği şirket adına geçirilmiş

---

## 8. Faydalı TR resmi kaynaklar

- **KGK (Kamu Gözetimi Kurumu)** — finansal raporlama standartları
- **Hazine ve Maliye Bakanlığı** — vergi mevzuatı
- **GİB (Gelir İdaresi Başkanlığı)** — e-Fatura, e-Tebligat, vergi dairesi
- **KVKK (Kişisel Verileri Koruma Kurumu)** — VERBİS, sağlık verisi rehberleri
- **TPMK (Türk Patent ve Marka Kurumu)** — marka tescili
- **TİTCK (Türkiye İlaç ve Tıbbi Cihaz Kurumu)** — tıbbi cihaz sınıflandırması (future-watch)
- **T.C. Cumhurbaşkanlığı Yatırım Ofisi** — yabancı yatırımcı için rehber, Series A'da yararlı
- **Türkiye İhracatçılar Meclisi (TİM) / Turquality** — uluslararasılaşma teşvikleri (TriAIge int'l plan'a girince)
- **Sanayi ve Teknoloji Bakanlığı** — Ar-Ge merkezi statüsü (gelecekte düşünülebilir; %100 SGK işveren payı + Ar-Ge gider indirimi)
- **TÜBİTAK / KOSGEB** — early-stage hibe ve destek programları

---

## 9. Açık konular — founder kararı bekliyor

- [ ] Sermaye nominal tutar: ₺250K mı, ₺500K mı?
- [ ] Eşit dağılım mı (33.3 × 3) yoksa hafif ayrışma + vesting mi?
- [ ] ESOP havuzu kuruluşta %10 mu %15 mi?
- [ ] Avukat seçimi: butik startup avukatı mı, full-service firma mı? (öneri: butik; healthtech tecrübesi olan; KVKK + IP'ye hâkim)
- [ ] Mali müşavir seçimi (founder-network referansı toplayın)
- [ ] Şirket merkezi: gerçek ofis mi, sanal ofis (virtual address) mi? Sanal ofis Sicil için kabul ediliyor ama bazı bankalar zorluk çıkarıyor
- [ ] Yabancı yatırımcı bekliyor musunuz? Eğer evet → kuruluşta "döviz cinsinden sermaye" seçeneği değerlendirin

---

**Son kontrol.** Bu doküman bir avukat sözleşmesinin yerine geçmez. İlk taslak imzalanmadan önce bir Türkiye-qualified avukat anasözleşmeyi, ortaklar sözleşmesini ve kurucu IP devir sözleşmesini birlikte gözden geçirmelidir.
