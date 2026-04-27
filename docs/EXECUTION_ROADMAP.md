# Execution Roadmap — Faz 3 open items

`PLAN_FAZ_3_STARTUP.md` dosyasındaki açık item'ları somut eylemlere
böler. Her bölüm: **kim / ne / ne kadar süre / nasıl / blocker / "done"
kriteri**.

Bu doc bir reference; check-off pattern aynı `PLAN_FAZ_3` gibi: item
kapandığında ✅ + closing-commit hash'i ekle, aynı commit'te.

---

## TL;DR — Week-1 critical path

Bu hafta başlanacak 5 high-leverage iş, hangisi kim:

| # | Item | Kim | Süre | Blocked? |
|---|---|---|---|---|
| 1 | TR-licensed lawyer ile ilk görüşme (2-3 quote) | Cofounder lead | 2-3 saat | Hayır |
| 2 | `triaige.com` (+ defensive `.co`, `.app`) registrar acquire | Solo founder, 1 saat | 1 saat | Hayır |
| 3 | Klinik advisor outreach — LinkedIn'de 10 candidate identify + 5 mesaj | Cofounder | 4-5 saat | Hayır |
| 4 | C.7.A — PII Fix #1 (notifier.py reason_tr redaction) | Engineer cofounder | 0.5 day | Hayır |
| 5 | Supabase region check + EU-Central pin decision | Engineer cofounder | 1 saat | Hayır |

Toplam Week-1: ~12-15 founder-saat, paralel — 3 cofounder arasında
dağıtılırsa bir hafta sonu işi. Geri kalan items 30-90 gün vadeli.

---

## Who-does-what map

3 cofounder + Claude (yardımcı) varsayılarak:

- **Engineer cofounder:** C.7 hepsi, C.9.C (widget impl), C.9.D (Supabase region)
- **Cofounder lead (sales/ops):** C.8.A (lawyer ilişkisi), C.8.C (advisor outreach), C.9.A (domain), C.9.B (designer hand-off briefing)
- **Tüm cofounder'lar:** C.8.A (anasözleşme imza süreci), C.8.B (VERBİS), risk decisions
- **External:** TR lawyer, designer, marka avukatı, klinik advisor (when found)
- **Claude (delegated):** C.7 implementation chip'leri, C.9 widget impl chip'leri (eğer engineer cofounder zamanı yoksa)

---

## C.7 — Engineering (PII + Multi-tenant)

Toplam ~6-8 eng-day. Bir engineer cofounder solo bir hafta + biraz veya
iki engineer 3-4 gün paralel.

### C.7.A — PII fixes (5 items, ~5 eng-days)

Her bir fix kendi mini-PR'si olabilir. Sıra paralelizable, ama
notifier.py + feedback.comment ilk öncelik (DPA imzasından önce
zorunlu).

#### C.7.A.1 — notifier.py reason_tr redaction (~0.5 day)

**Sorun:** `backend/app/notifier.py:172-211` — emergency alert webhook'una
Turkish `reason_tr` clinical detail (örn. "göğüs ağrısı sol kola
vuruyor") Slack/Discord US/EU cloud'una düşüyor. Hospital DPA bu
data'yı US-cloud egress olarak değerlendirir.

**Adımlar:**
1. `backend/app/notifier.py` aç, `reason_tr` field'ının webhook payload'a
   nereden eklendiğini gör.
2. İki seçenek:
   - **A (önerilen):** Webhook payload'da `reason_tr` yerine generic
     "EMERGENCY envelope fired — see admin dashboard for detail" yaz.
     Detay clinical detail dashboard'da kalsın (audit trail), webhook
     sadece notification ipucu.
   - **B:** `reason_tr` yerine sadece envelope type ve session_id (ilk
     8 char hash'lenmiş) gönder.
3. `backend/tests/test_notifier_pii.py` (yeni): unit test ekle, mock
   webhook → assert `reason_tr` plaintext yok.
4. PR + regression chain.

**Done:** webhook output'unda Turkish clinical detail yok; `notifier.py`
ayrıca audit table'a (Supabase) full detail yazıyor.

#### C.7.A.2 — feedback.comment redaction (~0.5 day)

**Sorun:** `backend/app/api/routes/feedback.py:25,56-62` — kullanıcı
feedback comment'i (≤2000 char free-text, "doktor şöyle dedi", "annem
panik atak", potential PHI/PII) DB'ye redaction olmadan insert.

**Adımlar:**
1. `backend/app/core/pii.py` içinde `scrub_for_storage(text: str) -> str`
   fonksiyonu var mı kontrol et. Yoksa yaz: TC kimlik no, telefon,
   email, ad-soyad pattern'larını redact et.
2. `feedback.py:56` insert öncesi `comment = scrub_for_storage(comment)`
   ekle.
3. Test: `tests/test_feedback_pii.py` — TC no içeren comment scrub
   sonrası `[REDACTED-TC]` placeholder olsun.
4. Migration: var olan `triage_feedback.comment` kayıtlarını re-scrub
   etmek için bir script (`backend/scripts/backfill_scrub_feedback.py`).
5. PR + run backfill ONCE on staging, then production.

**Done:** new + existing comment'lerde plaintext PII yok.

#### C.7.A.3 — Retention purge cron (~1 day)

**Sorun:** `docs/PRIVACY_AND_SECURITY.md` "X gün sonra silinir" claim
ediyor ama automated job yok. KVKK denetiminde bu material gap.

**Adımlar:**
1. `backend/app/scheduled/retention_purge.py` (yeni): daily cron.
2. Logic: `triage_sessions.input_text` ve `triage_events.payload` için
   30 gün retention (configurable via `RETENTION_DAYS_INPUT_TEXT` env
   var). Cron her 24 saatte:
   - `DELETE FROM triage_sessions WHERE created_at < NOW() - INTERVAL '30 days' AND input_text IS NOT NULL` → set `input_text = NULL` (soft purge: row stays for analytics, PII gone).
   - `DELETE FROM triage_events WHERE created_at < NOW() - INTERVAL '30 days'` (full delete, audit trail short).
3. Fly.io scheduled task: `fly.toml`'a `[processes.scheduler]` ekle veya
   external cron (GitHub Actions schedule, Supabase scheduled function).
4. Prometheus counter: `retention_purge_runs_total`,
   `retention_purge_rows_deleted_total`.
5. Test: integration test — insert old row, run purge, assert row's
   `input_text` is NULL.
6. PR + verify on staging.

**Done:** cron çalışıyor, metric Grafana'da görünüyor, retention claim
artık enforced.

#### C.7.A.4 — Debug payload gating (~0.5 day)

**Sorun:** `triage_events.payload` USER_MESSAGE / ENVELOPE_RESULT
event'larında full input + `_meta` debug detail (orchestrator state,
intermediate scores) saklıyor. Production'da gereksiz attack surface.

**Adımlar:**
1. Env var `INCLUDE_DEBUG_PAYLOAD=false` (default in production,
   `true` in dev/staging).
2. `triage_events` insert path'inde: `_meta` field'ı sadece env var
   true ise dahil et.
3. Existing `_meta`'lı eski row'lar olduğu gibi kalır (geçmiş audit
   trail).
4. Test: env var false → `_meta` yok; true → `_meta` var.
5. Fly.io secret olarak `INCLUDE_DEBUG_PAYLOAD=false` set et prod'da.

**Done:** prod payload size küçüldü, debug context dev/staging'de
hâlâ var.

#### C.7.A.5 — LLM NLU egress full PII scrub (~1 day)

**Sorun:** Wiro / Google / OpenAI / Anthropic API'lara Turkish health
text gidiyor. Şu an sadece TC/phone/email pre-redact ediliyor; isim,
adres, kurum adı, hastane ismi gibi diğer PII geçiyor.

**Adımlar:**
1. `backend/app/agents/symptom_interpreter.py` (veya LLM çağrısının
   yapıldığı dosyada): pre-call hook'a `scrub_for_external_egress(text)`
   çağır.
2. `scrub_for_external_egress` extended scrubber:
   - TC, phone, email (already done)
   - Personel ad-soyad regex (Türkçe ad pattern'ları — kompleks,
     %100 catch zor)
   - Adres anahtar kelimeler (mahalle, sokak, cadde, no:, daire)
   - Kurum/hastane isimleri (top-100 list — Acıbadem, Memorial, vb.
     placeholder'la replace)
3. Trade-off: aggressive scrub LLM context kalitesini düşürür. Test
   et — golden corpus'ta accuracy regression %2'den fazlaysa scrubber
   daraltılmalı.
4. Audit log: her egress request için (text length, scrubbed item
   count) metric.

**Done:** LLM provider'a giden payload'da plaintext PII (isim, adres,
kurum) %95+ redacted.

---

### C.7.B — Multi-tenant tenant_id wiring (~5 eng-days)

**Verdict:** YELLOW for 1 tenant (Acıbadem dedicated infra OK), RED
for ≥2. eVital pilot'u Acıbadem ile aynı stack'e koymak isterseniz bu
WIP'siz NO-GO.

**Adımlar (sıralı):**

#### C.7.B.1 — Schema migration (~1 day)

1. Migration script: `backend/migrations/0XX_add_tenant_id.sql`:
   ```sql
   ALTER TABLE triage_sessions ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default';
   ALTER TABLE triage_events ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default';
   ALTER TABLE triage_feedback ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default';
   ALTER TABLE push_tokens ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default';
   CREATE INDEX idx_triage_sessions_tenant ON triage_sessions(tenant_id);
   CREATE INDEX idx_triage_events_tenant ON triage_events(tenant_id);
   ```
2. Backfill: existing rows → `tenant_id = 'default'`.
3. Foreign key (eğer `tenants` tablosu varsa): `ALTER TABLE
   triage_sessions ADD CONSTRAINT fk_tenant FOREIGN KEY (tenant_id)
   REFERENCES tenants(id)`.

#### C.7.B.2 — Tenant resolution at API edge (~0.5 day)

1. `backend/app/api/routes/triage.py`: request body'sinde `tenant_id`
   yoksa header'dan (`X-Tenant-Id`) al, yoksa `'default'`.
2. Embedded widget URL'inden gelen `tenant=acibadem` query parametresi
   bu header'a map'lensin.
3. Pydantic model'lere `tenant_id: str` ekle.

#### C.7.B.3 — Orchestrator + cache tenant-aware (~1.5 day)

1. `backend/app/agents/orchestrator.py`: her function call'a
   `tenant_id` propagate.
2. `_RUNTIME` cache key: `(tenant_id, ...)` tuple olsun. LRU per
   tenant.
3. `curated_conditions.json` resolution: `curated_conditions.<tenant>.json`
   varsa onu, yoksa `curated_conditions.json` default'unu yükle.
4. Test: tenant A'nın curated catalog'u, tenant B'nin request'inde
   görünmemeli.

#### C.7.B.4 — Admin dashboard tenant scoping (~1 day)

1. `dashboard/app/admin/sessions/page.tsx`: query string'e
   `?tenant=...` ekle, default'unda admin user'ın kendi tenant'ı.
2. `dashboard/lib/requireAdmin.ts`: admin user'ın `tenant_id` field'ı
   olsun, list query'ler bunla filtrelensin.
3. Super-admin ("internal" tenant) tüm tenant'ları görebilsin
   (founder use için).
4. UI: header'da current tenant göster, dropdown ile değiştirme.

#### C.7.B.5 — Tests + verification (~1 day)

1. Integration test: 2 tenant create, her birinden session, isolation
   assert.
2. Load test: tenant A traffic, tenant B'nin metric'lerini kirletmiyor.
3. Manual: 2 tenant arası `/admin/sessions` cross-leak yok.
4. Migration rollback plan: migration `DOWN` script'i — column'lar
   drop edilir, default tenant data preserved.

**Done:** 2 tenant aynı stack'te isolated. Acıbadem + eVital paralel
çalışır.

---

## C.8 — Org / legal

### C.8.A — TR AŞ kuruluş (4-6 weeks elapsed, ~10 founder-saat)

**Adımlar:**

#### C.8.A.1 — Lawyer seçimi (Week 1, ~2-3 saat)

1. **Network referans:** Cofounder'lar tanıdık startup founder'larından
   "hangi avukatla çalıştın?" sor. TR startup community'sinde 5-10
   isim sürekli dönüyor.
2. **Yedek:** TÜGİAD, TBV, Endeavor Türkiye, KOBİVEN, BAU Inkube,
   ITU Çekirdek, KWORKS gibi inkübatörlerin tavsiye ettiği listeler.
3. **Quote alma:** 2-3 lawyer'la kısa görüşme. Şu konuları sor:
   - AŞ kuruluş tecrübesi (özellikle healthtech / data-heavy)
   - SaaS müşteri sözleşmesi review tecrübesi
   - DPA / KVKK uzmanlığı
   - Hourly rate vs flat fee for incorporation
   - Timeline tahmini
4. **Karar:** flat fee tercih et (₺25-50K all-in incorporation
   typical), retainer için hourly (₺2-5K/saat).
5. **Sözleşme:** anasözleşme + DPA review + LOI review için scope
   define et.

**Done:** seçilmiş lawyer + signed engagement letter.

#### C.8.A.2 — Anasözleşme drafting (Week 2-3, lawyer-driven)

1. Lawyer şirket adı doğrula (TPMK marka search ile çakışma yok).
2. **Founder share split:** 3 cofounder × %33.3 default. Reverse
   vesting clause ekle (4 yr, 1 yr cliff, founders'ın hisse %100'ü
   şirkete geri dönmek üzere).
3. **Capital:** AŞ minimum capital ~₺250K (verify current Türk
   Ticaret Kanunu). Cofounder'lar bu sermayeyi koymak zorunda
   (cash veya ayni katkı).
4. **Yetki:** Yönetim kurulu yapısı (cofounder'lar arasında).
5. **ESOP pool:** %10-15 reserve et (pre-Series-A standard). Pool
   anasözleşmede yer almasa da SHA'da reflect.

**Done:** lawyer'dan anasözleşme draft. Hepsini imzalamadan önce
mutlaka kendi cofounder'larla detaylı oku.

#### C.8.A.3 — Notary + Ticaret Sicil (Week 3-4, ~2-3 founder-saat)

1. Notary'de imza atma seansı (3 cofounder fiziki olarak orada).
2. Ticaret Sicil'e başvuru (lawyer halleder).
3. Tescil ilanı Ticaret Sicil Gazetesi'nde (~7-10 gün).
4. **Verify:** [Ticaret Sicil Gazetesi](https://www.ticaretsicil.gov.tr/)
   üzerinden tescil ilanını gör.

**Done:** AŞ resmi olarak kayıtlı.

#### C.8.A.4 — Vergi + SGK + Bağ-Kur (Week 4, ~2 founder-saat)

1. Vergi Dairesi'nde mükellefiyet tesisi (lawyer veya muhasebeci).
2. KEP adresi al ([Posta KEP](https://www.kep.gov.tr/)) — AŞ için
   zorunlu.
3. e-Tebligat aktivasyonu.
4. SGK işyeri açılış bildirgesi (eğer ilk çalışan kayıt edilecekse).
5. Bağ-Kur (cofounder'lar yönetim kurulu üyesi sıfatıyla
   sigortalanır).
6. e-Fatura mükellefiyeti (gelir oluştuğunda zorunlu, baştan
   açılması iyi).

**Done:** vergi + SGK + KEP set up.

#### C.8.A.5 — Bank account opening (Week 4-5, ~1-2 founder-saat)

1. Önerilen: **Garanti BBVA** (startup-friendly), **DenizBank**
   (E-Money çözümü için), veya **Ziraat** (kamu işleri için).
2. Required: Ticaret Sicil belgesi, Vergi levhası, anasözleşme,
   imza sirküleri, cofounder kimlik fotokopileri.
3. **TL hesabı + USD hesabı + EUR hesabı** aç (yurt dışı SaaS için
   USD/EUR şart).
4. Internet banking + sanal POS (Stripe / iyzico karşılaştır).

**Done:** company bank account active.

### C.8.B — VERBİS kayıt (within 30 days post-incorp, ~3-4 saat)

**Önemli:** AŞ kuruluş tarihinden itibaren 30 gün içinde sağlık verisi
işleyen şirket olarak VERBİS'e kayıt zorunlu. Kaçırılırsa idari para
cezası — healthtech için cezalar 2024'te ₺1.2M–₺7.6M aralığında.

**Adımlar:**

1. https://verbis.kvkk.gov.tr/ → Veri Sorumlusu kaydı.
2. Kayıt için gerekli:
   - Ticari unvan + Mersis no + KEP
   - Veri Sorumlusu Temsilcisi (Türkiye'de oturan gerçek kişi —
     cofounder)
   - İşlenen kişisel veri kategorileri (özel nitelikli veri:
     sağlık verisi olduğunu işaretle — bu otomatik olarak yıllık
     eşik altına düşmeyi engeller, kayıt zorunlu)
   - İşleme amaçları (ön-triyaj, sağlık yönlendirmesi)
   - Aktarım yapılan ülkeler (US — Sentry / OpenAI / Anthropic
     için; EU — Supabase / Grafana için)
   - Saklama süreleri (`PRIVACY_AND_SECURITY.md` ile uyumlu)
3. Lawyer ile birlikte yap — yanlış doldurulan VERBİS kaydı sonra
   denetim gelince problem yaratır.

**Done:** VERBİS başvuru tamamlandı, sicil no'su alındı.

### C.8.C — Klinik advisor outreach (parallel, ~3-4 weeks to first signed)

**Stratejik öncelik:** Acıbadem CMO'sundan "klinik ekibinizde kim var?"
sorusu IK gelirse cevap ver. İlk advisor signed olmadan önce DPA
imzalamayın — pitch tarafında material credibility.

**Adımlar:**

#### C.8.C.1 — Candidate identification (Week 1, ~3-4 saat)

LinkedIn search filtreleri:
- Location: Türkiye
- Title contains: "Doctor", "MD", "Dr.", "Tabip", "Hekim"
- Experience: 10+ years
- Specialty hint: family medicine, emergency, public health,
  digital health

Hedef profil:
- 10+ yıl klinisyen
- Healthtech / digital health adjacency
- Kurumsal network (private chain ilişkisi)

**10-15 candidate identify.** İsim + LinkedIn URL + 1 satır relevant
detail bir spreadsheet'e yaz.

#### C.8.C.2 — Outreach (Week 1-2, ~2-3 saat)

Bilingual outreach email template `docs/org/ADVISOR_OUTREACH.md`'de.

Sequencing:
- 5 mesaj at, response oranı %20-30
- 2-3 cevap → 2-3 sohbet
- 1-2 ciddi konuşma → 1 advisor signed

Eğer response oranı düşükse:
- LinkedIn InMail kullan (ücretli)
- Network referans iste (cofounder'ların kendi networks'ünden)
- Acıbadem CMO veya bilişim direktörünü direct sor (post-pilot
  conversation'da iyi olabilir)

#### C.8.C.3 — Sözleşme + sign (Week 3-4)

Advisor agreement outline `docs/org/ADVISOR_OUTREACH.md`'de.

Equity grant:
- 0.25-0.5% common shares (4 yr vesting, 1 yr cliff)
- Top-tier candidate için 0.75% acceptable
- ESOP pool'dan al, founder dilution etmesin

Time commitment: ~5 hrs/month (tek-tek mtg + on-call sorular).

**Done:** signed advisor agreement + first call scheduled.

### C.8.D — TPMK marka başvurusu (~6-12 ay, ~₺3-8K)

**Önemli ama acil değil.** İlk pilot'tan ÖNCE başvur ki
6-12 ay sonra registered marka olsun. Aksi halde başka biri "TriAIge"
yi kapatabilir.

**Adımlar:**

1. **Preliminary search:** [TPMK marka veri tabanı](https://www.turkpatent.gov.tr/arama)
   üzerinden "TriAIge" ve benzer string'ler için search. Çakışma
   yoksa devam.
2. **Sınıf seçimi:** Madrid Nice classification:
   - Class 9: software
   - Class 42: SaaS, computer programming
   - Class 44: medical services (TriAIge medical service vermiyor
     ama markayı medical alanda kullanacağı için defensive olarak
     ekle)
3. **Başvuru:** TPMK üzerinden online (kendin de yapabilirsin) veya
   marka avukatı (önerilen: marka avukatları AŞ avukatlarından
   farklı uzmanlık).
4. **Cost:** ~₺3-8K (sınıf sayısı + avukat ücreti).
5. **Timeline:** başvuru → 6-12 ay → registered (itiraz olmazsa).

**Done:** başvuru no'su (önemli değil registered olsun, başvuru
tarihi öncelik verir).

### C.8.E — TR-licensed counsel relationship (already covered C.8.A.1)

C.8.A.1'de seçilen lawyer bu rolü zaten oynuyor. Sadece scope'u
genişlet: incorporation + DPA review + LOI review + ongoing
contract review.

---

## C.9 — Brand / public surface

### C.9.A — Domain acquisition (1 saat, ~$50-100/yıl)

**Adımlar:**

1. **Registrar seç:**
   - **Cloudflare Registrar** (önerilen, en ucuz, no markup) — ama
     Cloudflare account gerek
   - **Namecheap** — ucuz, basit
   - **GoDaddy** — yaygın ama markup yüksek
2. **Acquire:**
   - `triaige.com` — primary, MUST acquire
   - `triaige.co` — defensive, ~$30/yıl
   - `triaige.app` — defensive, ~$15/yıl
   - `triaige.com.tr` — TR market için ek defansif (.com.tr için
     ticaret sicil belgesi gerek, AŞ kurulduktan sonra al)
3. **DNS yapılandır:** Cloudflare DNS (free) önerilir — sonradan
   widget.triaige.com, dashboard.triaige.com, status.triaige.com
   gibi subdomain'ler için.
4. **Email forwarding:** `info@triaige.com`, `security@triaige.com`,
   `legal@triaige.com` placeholder'ları gerçek mailbox'a forward et
   (cofounder'lara split).

**Done:** `triaige.com` aktif, DNS Cloudflare'de.

### C.9.B — Designer hand-off (~3 weeks elapsed, ~₺50-200K)

**Adımlar:**

#### C.9.B.1 — Designer seç (Week 1, ~3-4 saat)

Seçenek:
- **Freelance:** Dribbble + LinkedIn search "TR + UI/UX designer +
  SaaS". Portfolio + 2 hospital/healthcare reference iste.
- **Agency:** TR'de küçük design studio'lar (TQM, Boom Studios,
  Userspots, Userhub).
- **Cost:** freelance ₺50-100K, agency ₺150-300K (11-page site +
  brand identity hint).

#### C.9.B.2 — Brief + hand-off (Week 1)

Designer'a teslim:
- `docs/brand/WEBSITE_SCAFFOLD.md` (sitemap, content blocks)
- `docs/brand/REFERENCE_ARCHITECTURE.md` (visual'a inspiration)
- `docs/PITCH.md` (tone)
- `docs/templates/SALES_SHEET.md` (one-pager content)
- Design tokens: `docs/DASHBOARD_THEME.md`'den primary/accent/text
  renkleri (consistency için)

#### C.9.B.3 — Iteration + delivery (Week 2-3)

- Wireframe review (Week 2 başı)
- Visual design (Week 2 sonu)
- Hand-off to dev (Week 3) — Figma file + asset export

**Done:** designed Figma file + dev-ready asset paketi.

### C.9.C — Widget v1 implementation (~2-3 weeks engineering)

`docs/brand/EMBEDDED_WIDGET_SPEC.md` detaylı spec. Kısa özet:

#### Adımlar:

1. **iframe rotası:** Next.js dashboard'a yeni page route
   `dashboard/app/embed/page.tsx`. Query params: `tenant`, `locale`,
   `theme`, `entry`.
2. **Tenant resolution:** `?tenant=acibadem` → backend'e
   `X-Tenant-Id: acibadem` header'ı geçir.
3. **Theme support:** `?theme=hospital-custom` → tenant-specific
   theme JSON yükle.
4. **postMessage protocol:** widget mount → `triaige:ready`,
   emergency detect → `triaige:emergency_detected`, result →
   `triaige:result_shown`, exit → `triaige:exit`.
5. **CSP config:** `dashboard/next.config.ts` üzerinden per-tenant
   `frame-ancestors` allowlist. Tenant settings'inde hospital origin
   register edilmeden iframe render etmesin.
6. **Subdomain:** `widget.triaige.com` Vercel project'e custom
   domain bağla, dashboard'dan ayrı route.
7. **Demo embedding page:** `dashboard/app/embed/demo/page.tsx` — bir
   hospital'ın site'ında nasıl embed edileceğini gösteren demo
   landing.

**Done:** Acıbadem International landing page'inde iframe ile drop-in
deployable widget.

### C.9.D — Supabase region pin (~1 day operations)

**Sorun:** TR-resident hospital data ideally TR-local olmalı. Supabase
TR region'ı yok; en yakın EU-Central. Mevcut region check + EU-Central
pin.

**Adımlar:**

1. https://app.supabase.com/ → project dashboard → Settings → General
   → Region.
2. Eğer EU-Central değilse:
   - **Önerilen:** new project oluştur EU-Central'da, eski'ye dump,
     yeni'ye restore, env var'ları güncelle, eski project'i pause
     veya delete. Migration window: ~1-2 saat downtime.
   - **Alternatif:** mevcut region'ı tut, KVKK Aydınlatma Metni'nde
     açıkça beyan et + hospital DPA'larında region disclose et.
3. **Pin documentation:** `docs/PRIVACY_AND_SECURITY.md`'a region
   bilgisini açıkça yaz (currently `[VERIFY]` markı var
   `REFERENCE_ARCHITECTURE.md`'de — onu da güncelle).
4. **Backup region:** Supabase backup'larının da aynı region'da
   olduğunu verify et (cross-region backup KVKK perspective'inden
   tartışmalı).

**Done:** Supabase region documented + pinned + DPA-ready.

---

## External — 5 spawned chips

User-clicked, ayrı worktree'de çalışan independent task'lar.

| Chip | Scope | Branch suffix | Blocked-by |
|---|---|---|---|
| Reconcile README rate-limit doc drift | docs | (auto-generated) | - |
| Resolve duplicate top header on landing `/` | dashboard/app/{page,layout}.tsx | (auto-generated) | - |
| Add useFocusOnPageChange hook for App Router | dashboard/app/FocusOnRouteChange.tsx | (auto-generated) | landing header chip ile layout.tsx çakışıyor |
| Fix Turkish chest-pain emergency rule blind spot | backend/app/safety_guard.py + tests | (auto-generated) | - |
| Fix Turkish word-boundary regex in canonical_extract | backend/app/canonical_extract.py + tests | (auto-generated) | - |

**Sıralama önerisi (ilk yorumumdan):**
- **Şimdi paralel başlat:** safety chip'leri (chest-pain + canonical-
  extract) + rate-limit doc + landing header
- **Sonra başlat:** focus hook (landing header land etmeden başlatma —
  layout.tsx merge çakışır)

Her chip kendi PR'ini açacak. Main'e merge etmeden önce backend
regression chain (`backend && python scripts/run_backend_regression.py`)
zorunlu.

---

## 30-day sprint calendar

Tüm açık items'ı 30 günlük takvime göre dağıtırsak:

### Week 1
- C.7.A.1 + C.7.A.2 (PII fixes for DPA — engineer cofounder)
- C.8.A.1 (lawyer seç — sales/ops cofounder)
- C.8.C.1 (advisor candidate identification — sales/ops cofounder)
- C.9.A (domain acquire — solo, 1 saat)
- C.9.D (Supabase region check — engineer cofounder, 1 saat)
- 5 chip click → spawned, paralel running

### Week 2
- C.7.A.3 + C.7.A.4 + C.7.A.5 (geri kalan PII fixes)
- C.7.B.1 + C.7.B.2 (multi-tenant migration + edge resolution)
- C.8.A.2 (anasözleşme drafting — lawyer-driven)
- C.8.C.2 (advisor outreach 5 mesaj)
- C.9.B.1 (designer seç)
- 5 chip merge'leri review

### Week 3
- C.7.B.3 + C.7.B.4 (multi-tenant orchestrator + admin)
- C.8.A.3 (notary + sicil)
- C.8.C.2 follow-up (advisor mtg'leri)
- C.9.B.2 (designer brief)
- C.9.C başlangıcı (widget v1 implementation kick-off)

### Week 4
- C.7.B.5 (multi-tenant tests + validation)
- C.8.A.4 + C.8.A.5 (vergi/SGK/KEP/bank)
- C.8.B (VERBİS kayıt — AŞ tescilden 30 gün içinde)
- C.8.C.3 (advisor sign)
- C.8.D (TPMK marka başvuru)
- C.9.B.3 + C.9.C devam

**End of month 1:** AŞ kayıtlı, VERBİS submitted, advisor signed,
domain owned, multi-tenant + PII fixes shipped, 5 chip merged,
designer iterating.

**Month 2-3:** Designer site delivered, widget v1 production-ready,
Acıbadem pilot kick-off.

---

## Cost summary (rough)

| Item | Cost (₺) | Cost (USD) | Frequency |
|---|---|---|---|
| AŞ kuruluş (lawyer + harçlar) | ₺25-50K | $700-1500 | One-time |
| AŞ minimum capital | ₺250K | $7000 | Locked in equity |
| Domain (.com + .co + .app) | ₺3K | $80 | Annual |
| TPMK marka başvuru | ₺5-8K | $150-250 | One-time + 10-yıl renewal |
| Designer (freelance) | ₺50-100K | $1500-3000 | One-time |
| Widget v1 engineering | (eng-day cost) | - | One-time |
| TR lawyer retainer | ₺5-10K/ay | $150-300/ay | Ongoing |
| Klinik advisor (equity) | 0% cash | - | 4-yr vesting |
| Hosting (Vercel free + Fly hobby) | ₺0-300/ay | $0-10/ay | Monthly |
| Supabase Pro | ₺750/ay | $25/ay | Monthly (post-free-tier) |

**Month-1 cash out:** ~₺85-160K (₺250K AŞ capital hariç) =
~$2500-5000 + $7K capital lock.

---

## Decision points (founder calls)

Bu yol haritasında karar gerektiren noktalar:

1. **AŞ vs LtdŞti** — `TR_ENTITY_SETUP.md`'de AŞ argümanı, ama
   lawyer'la doğrula.
2. **Pilot pricing** — şu an placeholder ₺12K/50K/150K — Acıbadem ile
   ilk konuşmadan sonra revize.
3. **Designer freelance vs agency** — bütçe + ekip vibe.
4. **Supabase migration window** — pilot başlamadan ÖNCE migrate et,
   sonra zorlaşır.
5. **Advisor equity tier** — 0.25/0.5/0.75 — kandidatın deneyimi +
   network gücü.
6. **Multi-tenant timing** — Acıbadem pilot dedicated infra ile
   başlat, eVital eklenmeden ÖNCE C.7.B land. Veya iki pilot'u
   sequence et.

---

## Maintenance — bu doc'u güncel tut

- Her item kapandığında `PLAN_FAZ_3_STARTUP.md`'de ✅ + bu doc'ta
  notlandır.
- Yeni item ortaya çıkarsa `PLAN_FAZ_3_STARTUP.md`'a ⚪ candidate olarak
  ekle, sonra promote et.
- Bu doc'un 30-day calendar'ı her hafta refresh edilebilir
  (rolling 30).
