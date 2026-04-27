# Incident Reports

Her **30 dakika+** süren production incident'ı buraya yazılır. Kısa (<30dk) incident'lar için kanal: `#triaige-ops` Slack log yeterli; formal bir post-mortem gerek yok.

---

## Klasör yapısı

```
docs/incidents/
├── README.md                     # bu dosya
├── TEMPLATE.md                   # her yeni incident için start point
└── YYYY-MM-DD-kisa-aciklama.md   # gerçek incident'lar (her biri ayrı dosya)
```

Dosya adı formatı: `YYYY-MM-DD-kisa-aciklama.md`  
Örnekler:
- `2026-04-20-fly-backend-crash-loop.md`
- `2026-05-03-supabase-auth-outage.md`
- `2026-06-11-rate-limit-abuse-campaign.md`

`kisa-aciklama` kısmı 3-5 kelime, kebab-case. "Neydi?" sorusuna tek bakışta cevap versin.

---

## Ne zaman incident yaz?

- **30dk+ süren** bir prod issue — severity critical (5xx spike, full outage, data loss risk)
- **Recurring** (haftada 2+ aynı konu) — bir kere yazıp sonraki occurrence'larda referans ver
- **Learning moment** — "başlayan benzer bir şeyi nasıl engelleriz" çıkaracak tipte bir şey

Yazma: **olaydan sonraki 48 saat içinde**. Hafıza taze, kanıt (log, Grafana screenshot) hâlâ erişilebilir.

---

## Yazım felsefesi — blameless + aksiyon-odaklı

**Blameless**: "X hata yaptı" değil "süreç bunu yakalayamadı". Suçlu aramak değil, süreç + tooling iyileştirmek hedef.

- ❌ "Emir unutmuştu CORS_ORIGINS'i set etmeyi"
- ✅ "Secret-set prosedüründe yeni-deploy-sonrası checklist yoktu; PowerShell escape'i düşürme ihtimali belgelenmemişti"

**Aksiyon-odaklı**: her incident **en az 2-3 concrete follow-up** ile bitmeli. Action items:
- 🔧 Kod/config değişimi (örn. "validator ekle, `pydantic.ValidationError` → clear message")
- 📋 Süreç değişimi (örn. "deploy checklist'e `flyctl ssh + env check` adımı ekle")
- 📊 Monitoring (örn. "Grafana alert: CORS_ORIGINS parse error sentry'de → alert rule")
- 📖 Runbook (örn. "RUNBOOK.md Flow A'ya JSON parse crash case ekle")

---

## Template nasıl kullanılır

```bash
cp docs/incidents/TEMPLATE.md docs/incidents/2026-04-20-fly-backend-crash-loop.md
# Editör aç, doldur
```

Doldurulan dosyayı **aynı gün** repo'ya commit et:

```bash
git add docs/incidents/2026-04-20-fly-backend-crash-loop.md
git commit -m "docs(incidents): post-mortem — fly backend crash loop (CORS_ORIGINS parse)"
```

Commit mesajı formatı: `docs(incidents): post-mortem — <short-description>`.

---

## Güvenlik notu

**Asla commit etme:**
- Log'lardan kullanıcı IP'leri, session_id'leri, email'ler — hash'le veya replace et
- Gerçek secret değerleri — redact et (örn. `glc_eyJ...redacted...Q==`)
- Gerçek Supabase URL'si / Fly app adı genellikle OK (repo zaten biliyor), ama credential asla

Eğer tam bir log-dump gerekiyorsa: private Notion / password-protected drive'a yaz, buraya **özet + link** bırak.

---

## Periyodik review

**3 ayda bir** bu klasörü aç, açık action item'ları grepe:

```bash
grep -rn "Status: TODO\|Status: OPEN" docs/incidents/
```

Kapanmamış aksiyonları ilgili kişiye ata. Sprint planlamasında veya retro'da ele al.

**Yıllık olarak** en sık tekrarlayan incident kategorisini bul → o alana kalıcı investement (feature flag UI, otomatik recovery, dedicated dashboard, vs.).

---

## İlgili

- [`../RUNBOOK.md`](../RUNBOOK.md) — incident anında ne yapacağın (playbook + komutlar)
- [`../OPS_ROTATION.md`](../OPS_ROTATION.md) — quarterly credential rotation
- [`TEMPLATE.md`](TEMPLATE.md) — boş post-mortem iskeleti
