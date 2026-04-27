# Sub-Processors / Veri İşleyiciler

Compliance lineage: [`COMPLIANCE_CHECK_2026_04.md:Y-2`](COMPLIANCE_CHECK_2026_04.md). Bağlı dokümanlar: [`PRIVACY_NOTICE.md`](PRIVACY_NOTICE.md), [`RETENTION_POLICY.md`](RETENTION_POLICY.md), [`DEPLOY_AND_ENV.md`](DEPLOY_AND_ENV.md).

> ⚠️ **DRAFT — hukuk + DPO onayı bekliyor.** DPA imza tarihleri ve sertifika referansları doldurulması gerekir; yer tutucu olarak `[YYYY-MM-DD]` ve `[ref]` kullanıldı. KVKK Madde 9 (yurt dışına aktarım) ve GDPR Art.28 + Art.46 (controller-processor + uluslararası transfer) gereği bu envanter güncel ve denetlenebilir tutulmalı.

KVKK + GDPR çerçevesinde "veri işleyen" (sub-processor) olarak hareket eden tüm üçüncü taraf hizmet sağlayıcıların envanteridir. Aydınlatma metni ([`PRIVACY_NOTICE.md`](PRIVACY_NOTICE.md)) bu listeye işaret eder; kullanıcı talep ettiğinde paylaşılır.

---

## Aktif sub-processor'lar

| # | Sub-processor | Hizmet kategorisi | Erişilen veri | Lokasyon | DPA durumu | SCC | Sertifikalar | Yıllık review |
|---|---|---|---|---|---|---|---|---|
| 1 | **Supabase** (Supabase Inc.) | Postgres veritabanı barındırma + Auth | Triaj oturumu içeriği, push tokens, consent records, LLM çağrı logları, audit log | EU (Frankfurt veya İrlanda; proje config'inde set) | **[DPA imza durumu doldurulacak]** — Supabase standart DPA web'de yayında, kabul tarihi `[YYYY-MM-DD]` | EU SCC 2021 (Modül 2: C2P) | SOC 2 Type II, ISO 27001 | [tarih] |
| 2 | **Fly.io** (Fly.io, Inc.) | Container barındırma (backend FastAPI) | İstek payload'ları (geçici, log'a yazılmaz; supabase'e proxy'lenir) | EU bölgesi (`fly.toml`'da `primary_region` set) | **[doldurulacak]** | EU SCC 2021 (Modül 2) | SOC 2 Type II | [tarih] |
| 3 | **Vercel** (Vercel Inc.) | Next.js dashboard barındırma + edge CDN | Dashboard kullanıcı (admin) istekleri; statik privacy/terms sayfalarının cache'i | EU edge | **[doldurulacak]** | EU SCC 2021 (Modül 2) | SOC 2 Type II, ISO 27001 | [tarih] |
| 4 | **Sentry** (Functional Software, Inc. dba Sentry) | Hata izleme + Session Replay | Stack trace, breadcrumb, masked event meta. **PII maskeleme aktif** — bkz. [`SENTRY_REPLAY_POLICY.md`](SENTRY_REPLAY_POLICY.md). | EU (`sentry.io/eu`) veya US, hesap konfigürasyonuna bağlı — **EU bölgesi tercih edilmelidir** | **[doldurulacak]** — varsayılan retention 90 gün | EU SCC 2021 (Modül 2) — US bölgesi seçildiyse zorunlu | SOC 2 Type II, ISO 27001 | [tarih] |
| 5 | **Resend** (Resend, Inc.) | İşlemsel e-posta gönderimi (sadece send-summary tetiklendiğinde) | E-posta adresi (gönderim anında), oturum özet metni (içerik) | US (varsayılan) | **[doldurulacak]** | EU SCC 2021 (Modül 2) — US transfer için zorunlu | SOC 2 Type II | [tarih] |
| 6 | **Expo (Expo Application Services / EAS)** | Push notification altyapısı + mobile build/dağıtım | Anonim cihaz push token'ı (içerik gönderilmez), build artifact metadata | US (Cloudflare edge) | **[doldurulacak]** | EU SCC 2021 (Modül 2) | SOC 2 Type II | [tarih] |
| 7 | **Wiro.ai** | LLM (NLU) inference — `google/gemini-2-5-flash` proxy | **`LLM_NLU_ENABLED=true` iken** anonimleştirilmiş semptom metni (kimlik/oturum eşlemesi yok) | TR / global | **[Critical — doldurulacak]** Compliance KR-4 blocker. DPA + zero-retention API politikası imzalanmadan production'da `LLM_NLU_ENABLED` `true` yapılmamalı. Şu an varsayılan `false` (deterministic-only mode aktif). | EU SCC 2021 (Modül 2) — TR-AB transfer hâlâ değerlendirme istiyor | (sertifika listesi sağlayıcıdan teyit) | quarterly (yüksek hassasiyetli; özel kategori veri akışı) |
| 8 | **GitHub** (GitHub, Inc., Microsoft subsidiary) | Kaynak kod, CI/CD (Actions), issue tracking | Geliştirici taahhütleri; **müşteri/kullanıcı verisi yok** — yalnızca repo + workflow logları | US | **[doldurulacak]** — GitHub Customer DPA varsayılan | EU SCC 2021 (Modül 2) | SOC 2 Type II, ISO 27001, FedRAMP | yıllık |

---

## Pasif / kaldırılan sub-processor'lar

| Sub-processor | Çıkış tarihi | Sebep | Veri imhası teyidi |
|---|---|---|---|
| _(yok)_ | — | — | — |

Bir sağlayıcı çıkarıldığında bu tabloya satır ekleyin: çıkış tarihi + müşteri verisinin nasıl imha edildiği (örn. "Resend dashboard üzerinden veri silme talebi onaylandı, [tarih]").

---

## Sözleşme + denetim takvimi

| İş | Sıklık | Sahibi |
|---|---|---|
| Yeni sub-processor eklemeden önce DPA imzalı mı doğrula | Her ekleme öncesi | DPO + Hukuk |
| Mevcut sub-processor sertifikaları (SOC 2, ISO 27001) güncel mi | Yıllık | DPO |
| Wiro.ai özel: API politikası değişikliği (zero-retention koruyor mu?) | Quarterly | Eng + DPO |
| Bu listenin aydınlatma metni ile uyumu | Her aydınlatma metni güncellemesinde | Hukuk |
| Liste güncel mi (kullanılmayan provider çıkarıldı mı) | Quarterly | Eng |

---

## Yeni sub-processor eklerken kontrol listesi

- [ ] Provider için yazılı DPA imzalandı (öncelikle EU SCC 2021 versiyon).
- [ ] Provider'ın işleme amacı + erişim seviyesi minimal (data minimisation — KVKK Md.4, GDPR Art.5(1)(c)).
- [ ] Provider lokasyonu belirlendi; AB/TR dışı ise SCC + Transfer Impact Assessment.
- [ ] Provider'ın kendi sub-processor zinciri kabul edilebilir.
- [ ] [`docs/PRIVACY_NOTICE.md`](PRIVACY_NOTICE.md) sharingList + dataTransfer'a eklendi (TR + EN).
- [ ] [`docs/COMPLIANCE_CHECK_2026_04.md`](COMPLIANCE_CHECK_2026_04.md) Y-2 referansı güncel.
- [ ] Bu doküman (yukarıdaki tablo) güncellendi.
- [ ] CHANGELOG'a `[Privacy]` etiketli not.
- [ ] Mevcut kullanıcılara material değişikse in-app banner duyurusu.
- [ ] Aydınlatma metni `notice_version` bump'lanır → kullanıcı yeniden onay verir (intro).

## Sub-processor çıkarırken kontrol listesi

- [ ] Provider tarafında müşteri verisi silme talebi gönderildi + onaylandı.
- [ ] Backup arşivinde kalan veri için provider'dan yazılı imha taahhüdü.
- [ ] Bu doküman "Pasif" tablosuna satır eklendi.
- [ ] Aydınlatma metni güncellendi.
- [ ] Code'dan API key + endpoint config kaldırıldı.

---

Doküman tarihi: 2026-04-27. Sahibi: DPO + Engineering Lead. Sonraki review: 2026-07-27 (quarterly).
