# Risk Register — TriAIge

> **Disclaimer.** Bu risk kaydı bir iç çalışma belgesidir; sigorta poliçesi, hukuki uyumluluk attestation'ı veya tıbbi cihaz risk yönetimi (ISO 14971) yerine geçmez. Pilot başlamadan önce bir Türkiye-qualified avukat ve bir klinik danışman tarafından gözden geçirilmelidir.

Audience: kurucular, gelecek board, due-diligence reviewer.

Likelihood / Impact ölçeği: **L = Low (1), M = Medium (2), H = High (3)**. Skor = Likelihood × Impact (1–9). Yüksek skor = öncelik.

---

## 1. Risk tablosu

| ID | Kategori | Risk | L | I | Skor | Owner | Mitigation | Trigger / leading indicator |
|---|---|---|---|---|---|---|---|---|
| **R-01** | Klinik / güvenlik | **Acil-eşik vakası kaçırma — kırmızı bir vakayı yeşil/sarıya yanlış sınıflandırma** (örn. AKS göğüs ağrısı, inme şüphesi, anaflaksi). Hasta zararı + dava + medya. | M | H | **9** | CTO + (gelecek) Klinik advisor | (a) Acil tetikleyici sembol-listesi: göğüs ağrısı + nefes darlığı, FAST inme triadı, anaflaksi belirtileri — bunlar **hard-coded bypass** ile her zaman kırmızı; LLM hiyerarşinin altında. (b) Her sürüm öncesi `triage golden flows` 17–25 (`docs/TRIAJ_GOLDEN_FLOWS_17_25.md`) ile regression suite — emergency miss = block release. (c) Mobil app'in tüm triaj çıktılarına eklediği "112 numarayı arayın" disclaimer (`docs/I18N_TRIAJ.md`). | Shadow eval'de emergency-recall < %99 (`docs/SHADOW_EVAL_B1_REPORT.md` benchmark); ya da pilot süresince 1+ "kullanıcı acile gitti, biz yeşil dedik" raporu |
| **R-02** | Klinik / güvenlik | **Yanlış-pozitif acil — yeşili kırmızı'a yanlış sınıflandırma** çok sık olursa hastane acili gereksiz yere yüklenir, partner güveni düşer, ürün "the boy who cried wolf" olur. | M | M | **6** | CTO + Klinik advisor | (a) Specificity metric'i recall metric'i ile birlikte sürüm gate'inde (eşik: %85+). (b) Her acil yönlendirmenin "neden" gerekçesi mobile UI'da görünür → kullanıcı "bu mantıksız" feedback'i kolayca verir. (c) Pilot sırasında haftalık partner geri bildirim toplantıları. | Pilot hastanede haftada 5+ "yanlış yönlendirme" raporu; ya da specificity drift > %3 |
| **R-03** | Klinik / güvenlik | **Tıbbi sorumluluk davası** — bir hastanın TriAIge çıktısı sonucu zarar gördüğü iddiası ile dava. | L | H | **6** | CEO + Klinik advisor + avukat | (a) **Pre-triage** pozisyonu net (tanı koymuyoruz, tedavi reçetelendirmiyoruz; bkz. `docs/PRIVACY_AND_SECURITY.md` + `docs/PITCH.md`). (b) Her çıktıda "112'yi arayın / hekim görün" disclaimer. (c) Mesleki sorumluluk sigortası (E&O / cyber + medical tech rider) — pilot başlamadan poliçe alın. (d) ToS / KVKK aydınlatma metninde sorumluluk sınırlama maddeleri (avukat onaylı). | Hukuk ofisinden bir "claim notice" gelir; ya da hastane partner pozitif değil net negatif feedback formuna geçer |
| **R-04** | Düzenleyici | **KVKK denetim eylemi / VERBİS gecikmesi** — özel-nitelikli sağlık verisi işlerken VERBİS kaydı eksik veya gecikti, idari para cezası. | L | H | **6** | CEO + DPO (atanacak) | (a) Kuruluştan sonra 30 gün içinde VERBİS kaydı (bkz. `docs/org/TR_ENTITY_SETUP.md` §3.5). (b) `docs/PRIVACY_AND_SECURITY.md`'in KVKK aydınlatma metni + açık rıza akışı ile eşleşmesi. (c) PII redaction katmanının aktif ve test edilmiş olması (LLM payload'larında PHI sızıntısı yok). | KVKK'dan inceleme yazısı; ya da kullanıcı tarafından KVKK'ya şikayet (haftalık kullanıcı şikayet sayısı izlenir) |
| **R-05** | Düzenleyici | **TİTCK / Sağlık Bakanlığı reklasifikasyonu — TriAIge'in tıbbi cihaz olarak yeniden tanımlanması.** TCY (MDR transpozisyon) altında Class IIa/IIb sınıfına girerse CE + ISO 13485 + IEC 62304 + klinik validasyon gerekir; 12+ ay, 6 haneli € maliyet. | L | H | **6** | CEO + (gelecek) Düzenleyici danışman | (a) Pre-triage pozisyonunun ürün, marketing, pitch, ToS'ta tutarlı kullanımı — "tanı koyuyor" kelimesinin asla kullanılmaması. (b) `docs/PITCH.md` ve `docs/templates/SALES_SHEET.md` rebranding sonrası taranmalı (`docs/EXTERNAL_RENAME_CHECKLIST.md`). (c) Future-watch: TR'de AI-as-medical-device rehberlerinin (TİTCK / KVKK) çıkması durumunda 30 gün içinde uyumluluk değerlendirmesi yapılır. | TİTCK'dan kategoriye dair rehber yayını; ya da AB MDR güncellemesinde "diagnosis support software" tanım genişlemesi |
| **R-06** | Düzenleyici | **Uluslararası genişlemede FDA / AB MDR yolu belirsizliği** — 2027+ uluslararasılaşma planında bir hedef ülkede sınıflandırma TR'den daha sıkı. | M | M | **4** | CEO | Yol haritasında TR'yi konsolide et; uluslararası açılım için **adım-adım country-by-country** düzenleyici taraması — pilot tarafına paralel olarak 6 ay öncesinden başlat. | Uluslararası pilot konuşması başlar; herhangi bir EU/US hastane "FDA cleared mi?" sorar |
| **R-07** | Ticari | **Acıbadem pilot çöker** (ürün → operasyonel uyumsuzluk; veya iç stakeholder support kaybı). | M | H | **6** | CEO | (a) İlk pilot için "discovery only" küçük scope: 1 klinik + 50-100 hasta / 4 hafta. (b) `docs/templates/LOI_TEMPLATE.md` + `docs/templates/KVKK_DPA_TEMPLATE.md` ile başlangıç sürtüşmesini minimize et. (c) Acıbadem'in **kendisi** support sponsoru bulamazsa Memorial / Liv / Anadolu'ya paralel reach-out — pilot pipeline'da 2+ partner her zaman olmalı. | Acıbadem decision-maker'dan 2 hafta cevap gecikmesi; ya da pilot kickoff tarihi kayar |
| **R-08** | Ticari | **eVital pilot çöker** (telesağlık partner integration karmaşıklığı; veri paylaşım modelinde anlaşmazlık). | M | M | **4** | CEO + CTO | (a) eVital'in mevcut API entegrasyon yüzeyini erken haritala. (b) Veri paylaşım modeli — kim hangi PII'yi tutuyor — pilot LOI'sinde berraklaştır. (c) Alternatif telesağlık partneri pipeline'da (Memorial Online, vb.). | Teknik discovery 4 hafta üzeri sürer; ya da KVKK DPA müzakeresi tıkanır |
| **R-09** | Ticari | **Pipeline tıkanır — hem Acıbadem hem eVital aynı çeyrekte yavaşlar.** Cash burn devam eder; runway erir. | M | H | **6** | CEO | (a) Pipeline'a 3+ partner ekle; haftalık conversion funnel review. (b) Self-serve / B2C lite pilot opsiyonu çantada (mobil app açık erişim, ücretsiz, kullanıcı verisi toplama). (c) Hibe / tübitak başvurusu paralel — TÜBİTAK 1812 BiGG, KOSGEB Ar-Ge. | Pipeline 90 gün kapanış olmadan stagnate; ya da iki partner aynı anda "next quarter" der |
| **R-10** | Ticari | **Yanlış fiyatlandırma — partner ödeme isteğinin altında / üstünde fiyat.** | M | M | **4** | CEO | (a) İlk pilot fiyat: per-completed-triage modeli, partner için $0.50–2 USD aralığı düşünülüyor (TR fiyat + zaman kazancı çarpanı; verify with partner discovery). (b) İlk pilot kapanışında "ücretsiz pilot + paid expansion" yapısı — risk transferi. | Partner pricing konuşmasında "çok pahalı" / "çok ucuz, ciddi mi?" reaksiyonu; ya da değer paylaşımı oranı net değil |
| **R-11** | Yetenek | **Klinik advisor yokluğu** (mevcut açık eksik). | H | H | **9** | CEO | `docs/org/ADVISOR_OUTREACH.md` 6-8 hafta hedef; ilk pilot LOI'sinden önce 1+ signed advisor. | Acıbadem CMO'su "klinik tarafınızda kim var?" sorusuna cevap "kimse" — bu zaten gerçekleşti |
| **R-12** | Yetenek | **Senior backend / ML hire eksik** — ürün ölçeklendiğinde 3 kurucu + ad-hoc kapasite yetersiz. | M | M | **4** | CTO | (a) Şu an 3 kurucu engineering kapasitesi MVP için yeter. (b) Pilot başlamadan +1 senior backend hire planla — ESOP grant + Series A kapanışı ile aktif olabilir. (c) Mevcut kapasite üzeri herhangi bir scope için "pause and prioritize" disiplini. | Sprint velocity 4 sprint üst üste planın altında; ya da on-call rotation 2 kişi ile sürdürülemez hale gelir |
| **R-13** | Yetenek | **Kurucu uyuşmazlığı / kurucu ayrılığı** — 3 kurucu equity yapısında deadlock veya bir kurucu erken ayrılırsa equity geri çağrı sorunu. | L | H | **6** | Tüm kurucular | (a) Ortaklar sözleşmesi (SHA) — vesting + reverse vesting + drag-along + tag-along + good-leaver/bad-leaver tanımları (bkz. `docs/org/TR_ENTITY_SETUP.md` §2.2). (b) Kurucular arası karar mekanizması (hangi kararlar oybirliği, hangileri çoğunluk). (c) Yıllık 1-on-1 alignment check'leri. | Bir kurucu sprint review'da pasifleşir; ya da kararlar 2 hafta üzeri açıkta kalır |
| **R-14** | Teknoloji | **LLM sağlayıcı outage** — Anthropic / OpenAI API kesintisi triaj akışını çökertir. | M | M | **4** | CTO | `docs/runbooks/LLM_PROVIDER_DOWN.md` runbook + (gelecek) ikinci sağlayıcıya fallback. Mobil app degraded mode (kural-bazlı triage). Cache + retry tenacity (zaten requirements.txt'de). | Sağlayıcı status sayfası incident; ya da `/healthz` LLM dependency check fail rate > %1 |
| **R-15** | Teknoloji | **Supabase outage** — DB erişimi kaybı; auth + session storage başarısız. | M | M | **4** | CTO | `docs/runbooks/SUPABASE_DOWN.md` runbook. PostgREST cache'lenebilirlik. Offline-first mobil mimarisi (zustand + AsyncStorage local state — `mobile/package.json`). | Supabase status incident; ya da DB latency p95 > 2s |
| **R-16** | Teknoloji | **Bağımlılık deprecation / güvenlik açığı** — kullanılan kütüphanede yüksek-CVE açığı; örn. fpdf2 (LGPL), expo, fastapi. | M | M | **4** | CTO | (a) `docs/AUDIT_DEPENDENCIES.md` + `docs/DEPENDENCY_AUDIT.md` periyodik review. (b) Dependabot otomatik PR + CI security scan. (c) Aylık güvenlik tarama (npm audit, pip-audit). (d) `docs/runbooks/SECURITY_INCIDENT.md` runbook. | CVSS 7+ yeni CVE; ya da Dependabot 30+ gündür kapatılmamış PR |
| **R-17** | Rekabet | **İyi finanse edilmiş bir uluslararası rakip TR'ye girer** (örn. Babylon, K Health, Buoy). | L | H | **6** | CEO | (a) TR-yerlisi avantaj — Türkçe medikal jargon + TR sigorta sistemi anlayışı + Bakanlık ilişkisi. (b) Lokal data flywheel: pilot verisi her hafta modeli iyileştirir; rakip giriş anında onlardan yıllar geride. (c) Hızlı imza pipeline: ilk büyük zincir partner LOI'si rakibin pazara girişini zorlaştırır. | TR'de bir uluslararası health-AI brand awareness/PR campaign; ya da TR ofisi açılışı |
| **R-18** | Rekabet | **Hastane zinciri kendi içinde yapar** — Acıbadem teknoloji yatırımıyla in-house geliştirir, partnership yerine. | L | M | **3** | CEO | (a) Acıbadem'in mevcut iç yazılım kapasitesi haritalanır — "make vs buy" ekonomi sunumu (TriAIge 6 ay, in-house 18+ ay, opportunity cost). (b) Multi-tenant SaaS pozisyonu — tek bir zincir için inşa edilmemiş, network etkisi var. | Acıbadem CTO ofisinden "bunu kendi ekibimizle yapabiliriz" sinyali |
| **R-19** | Rekabet | **Big-tech entrant** (Google Health, Amazon Health, Microsoft Health) Türkiye'ye girer. | L | M | **3** | CEO | TR-spesifik avantaj (regülasyon, dil, klinik adaptasyon) + niş odaklanma + agility. Big-tech yıllar sürer; biz çeyreklerle hareket ederiz. | Bu sağlayıcılardan TR pazar girişi resmi açıklaması |
| **R-20** | Finansal | **Runway gap — traction'a ulaşmadan kasa kuruyor.** | M | H | **6** | CEO + CFO (atanacak) | (a) Aylık burn rate take + 12 ay forward runway target. (b) Hibe paralel akışı (TÜBİTAK 1812, KOSGEB Ar-Ge, Horizon Europe altında EIC Accelerator). (c) Bridge SAFE / convertible note opsiyonu pre-Series-A için. (d) Pilot revenue başlatma — küçük olsa bile cash-in işareti. | Runway < 6 ay düşer; ya da pipeline conversion oranı 2 çeyrek üst üste plan altında |
| **R-21** | Finansal | **FX maruziyeti — USD denominated SaaS gelirleri TL'ye çevrildiğinde ekstra volatility, ya da SaaS giderleri TL bütçesini aşar.** | M | M | **4** | CEO + mali müşavir | (a) USD-denominated tüm gider kalemlerini bir hesapta topla (Garanti / DenizBank dolar alt-hesabı). (b) USD-denominated potansiyel revenue (uluslararası genişleme) bu hesaba akar — natural hedge. (c) Aylık FX rate exposure raporu. | TL/USD çift haneli aylık değişim; ya da SaaS bills bütçenin %20+ üstünde |
| **R-22** | Operasyonel | **Veri ihlali — PHI / PII içeren breach.** | L | H | **6** | CTO + (atanacak) DPO | (a) PII redaction katmanı + LLM payload denetimi (zaten architecture'da). (b) `docs/PRIVACY_AND_SECURITY.md` security headers (`docs/SECURITY_HEADERS_INTEGRATION.md`), HTTPS-only, encryption at rest. (c) `docs/runbooks/SECURITY_INCIDENT.md` IR plan + KVKK 72 saatlik bildirim akışı. (d) Pilot öncesi pen-test (düşük maliyetli butik firma; ~₺50K). | Sentry'de "PHI in payload" alert; ya da bug-bounty / şüpheli bir trafik pattern |
| **R-23** | Operasyonel | **On-call kapsamı eksik — hafta sonu / gece outage'ında kimse cevap veremez.** | M | M | **4** | CTO | (a) `docs/OPS_ROTATION.md` 3 kurucu primary rotation. (b) PagerDuty / Opsgenie alert routing. (c) Pilot başlamadan en az 2 secondary on-call (senior hire tamamlandıktan sonra) — gerekirse sözleşmeli SRE. | Bir incident'te response time > 30 dk; ya da bir kurucu izin döneminde on-call boş |
| **R-24** | Operasyonel | **Backup / DR kaybı** — Supabase backup retention dışında veri kaybı, ya da region outage uzun sürer. | L | H | **6** | CTO | (a) Supabase otomatik backup + ek günlük off-site dump (ayrı bucket). (b) Aylık restore drill (`docs/RUNBOOK.md`'a eklenebilir). (c) Quarterly DR tabletop exercise. | Backup job 3 günden fazla başarısız; ya da Supabase region maintenance window 1 saat üzerinde |
| **R-25** | Operasyonel | **Hukuki maliyet sürprizi** — düzenleyici inceleme, dava, marka çekişmesi, ya da yatırım turunda DD legal cost'u beklenenin üstünde. | M | M | **4** | CEO | (a) Avukat retainer (sabit aylık) — saatlik karşı koruyucu. (b) Yıllık hukuk bütçesi (₺150-300K aralığı, verify) + %20 buffer. (c) Kritik kararlar için memo trail — sonradan re-litigation maliyetini düşürür. | Avukat fatura ay 3+ üst üste budget üstünde; ya da bir incelemenin "external counsel needed" sinyali |

---

## 2. Top 3 risks to watch — bu çeyrek

### Tier 1 — şimdi (next 30 days)

1. **R-11 — Klinik advisor yokluğu (skor 9)** — Acıbadem pitch'inde first-blocker. `docs/org/ADVISOR_OUTREACH.md` outreach 6-8 haftalık hedef; ilk pilot LOI'sinden önce 1+ signed advisor amaç. Sahibi: CEO.

2. **R-01 — Acil-eşik vakası kaçırma (skor 9)** — pilotun kabul kriteri olarak `triage golden flows` 17–25'e dayanan hard-coded emergency bypass + her sürüm öncesi shadow eval emergency-recall %99 gate. Sahibi: CTO + (gelecek) klinik advisor.

3. **R-09 — Pipeline tıkanması (skor 6, ama tetik yakın)** — Acıbadem ve eVital aynı çeyrekte yavaşlarsa runway riski. 3+ partner pipeline + paralel TÜBİTAK 1812 başvurusu. Sahibi: CEO.

### Tier 2 — paralel akış (next 90 days)
- **R-04 (KVKK / VERBİS)** — kuruluş + 30 gün
- **R-22 (Veri ihlali)** — pilot öncesi pen-test
- **R-20 (Runway)** — aylık burn rate görünürlüğü

### Tier 3 — quarterly review
- R-05 (TİTCK reklasifikasyonu), R-13 (kurucu uyuşmazlığı), R-17 (uluslararası rakip)

---

## 3. Risk review cadence

| Cadence | Audience | Çıktı |
|---|---|---|
| Aylık | 3 kurucu | Skor güncelleme; Tier 1 risklerin trigger durumu; yeni risk eklenmesi |
| Çeyreklik | Kurucular + (gelecek) board | Top 3 yeniden sıralama; mitigation maliyeti vs. risk skoru gözden geçirme |
| Pilot öncesi | Tüm tarafları + klinik advisor | Tier 1 + tier 2 deep dive; pilot scope'a uygunluk |
| Annual | Kurucular + board + dış reviewer (varsa) | Tüm risk register baştan sona, kategoriler arası tutarlılık check |
| Incident sonrası | İlgili sahip + CEO | Yaşanan incident bir mevcut risk'in tetiği mi? Yeni risk doğdu mu? |

---

## 4. Bu doküman ile ilişkili repo dosyaları

- `docs/PRIVACY_AND_SECURITY.md` — KVKK + güvenlik baseline
- `docs/SECURITY_HEADERS_INTEGRATION.md` — güvenlik başlıkları kontrol listesi
- `docs/runbooks/SUPABASE_DOWN.md` — DB outage runbook (R-15)
- `docs/runbooks/LLM_PROVIDER_DOWN.md` — LLM outage runbook (R-14)
- `docs/runbooks/SECURITY_INCIDENT.md` — güvenlik incident response (R-22, R-04)
- `docs/OPS_ROTATION.md` — on-call rotation (R-23)
- `docs/AUDIT_DEPENDENCIES.md` + `docs/DEPENDENCY_AUDIT.md` — bağımlılık denetimi (R-16)
- `docs/EXTERNAL_RENAME_CHECKLIST.md` — rebrand sonrası tutarlılık (R-05)
- `docs/TRIAJ_GOLDEN_FLOWS_17_25.md` — emergency triage regression (R-01)
- `docs/SHADOW_EVAL_B1_REPORT.md` — model recall benchmark (R-01)
- `docs/I18N_TRIAJ.md` — disclaimer + emergency number (R-01, R-03)
- `docs/templates/KVKK_DPA_TEMPLATE.md` — partner DPA (R-08, R-22)
- `docs/templates/LOI_TEMPLATE.md` — pilot LOI (R-07, R-08)
- `docs/PITCH.md` — pre-triage positioning (R-05)
- `docs/org/TR_ENTITY_SETUP.md` — VERBİS + ESOP + kurucu sözleşmesi (R-04, R-13)
- `docs/org/IP_TRANSFER_PLAN.md` — IP cleanup (DD readiness)
- `docs/org/ADVISOR_OUTREACH.md` — klinik advisor (R-11)

---

**Son not.** Bu register live bir belge olmalı. Her aylık review sonunda commit (kim ekledi, ne değişti, hangi trigger gerçekleşti). Pilot başlama tarihi yaklaştıkça Tier 1 listesi yeniden sıralanır — bugünkü öncelikler 90 gün sonra yerini tamamen başka risklere bırakabilir.
