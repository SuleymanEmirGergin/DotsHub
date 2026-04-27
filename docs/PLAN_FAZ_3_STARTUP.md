# Faz 3 — Startup-mode backlog

Faz 1 (`PLAN_KALAN_ADIMLAR.md`) ve Faz 2 (`PLAN_SONRAKI_FAZ.md`) kapatıldı —
o iki belge artık tarihçe kaydı. TriAIge'in startup fazına ait aktif
backlog burada tek source-of-truth olarak takip edilir.

Status legend:

- 🟢 in flight (spawned ya da aktif çalışılıyor)
- 🟡 queued (commit verildi ama başlamadı)
- ⚪ candidate (önerildi, henüz commit yok)
- ✅ done (kapanış commit'i ile mark'la, bu dokümana ekle)

---

## A. Spawned chips (waiting on user click)

Session 17 wrap-up'ında üç follow-up chip spawn edildi. Her biri ayrı
worktree'de bağımsız session olarak çalışacak.

| Status | Item | Scope | Notes |
|---|---|---|---|
| 🟢 | Reconcile README send-summary rate-limit doc drift | `README.md`, `CHANGELOG.md` | Source of truth: backend code. |
| 🟢 | Resolve duplicate top header on landing `/` | `dashboard/app/{page,layout}.tsx` | Path A default (drop landing's header). |
| 🟢 | Add `useFocusOnPageChange` hook for App Router | `dashboard/app/FocusOnRouteChange.tsx` (yeni) | Skip first mount; focus `<main>` on pathname change. |

---

## B. External rename remaining

GitHub repo rename ✅ (commit `f67fe3b` sonrası `git remote set-url`
edildi). Geri kalan 13 item için detay: [`EXTERNAL_RENAME_CHECKLIST.md`](EXTERNAL_RENAME_CHECKLIST.md).

| Priority | Item | Status |
|---|---|---|
| High | Fly.io app — verify `triaige-backend` slug live | 🟡 |
| High | Vercel project rename | 🟡 |
| High | Sentry backend project slug | 🟡 |
| High | Sentry mobile project slug | 🟡 |
| High | Slack workspace + channel rename (`#dotshub-ops` → `#triaige-ops`) | 🟡 |
| High | Discord webhook channel | 🟡 |
| High | App Store Connect listing (potentially new listing if bundle ID changed) | 🟡 |
| High | Google Play Console listing (same bundle ID concern) | 🟡 |
| High | EAS / Expo account slug | 🟡 |
| Medium | Grafana Cloud stack + dashboard titles + alert rule names | 🟡 |
| Medium | Prometheus metric labels (if any contain "dotshub") | 🟡 |
| Medium | Grafana provisioner name (cosmetic) | 🟡 |
| Low | GitHub Actions bot emails (`*-bot@dotshub.com` → `*-bot@triaige.com`) | 🟡 |
| Low | Env var keys containing `DOTSHUB_*` (none found in repo, but check live deploys) | ⚪ |
| Low | Placeholder domains in docs (`dotshub.example`, `dotshub.com` etc.) | 🟡 |

---

## C. Startup readiness — known gaps

Bu kategoriler henüz formalize edilmedi. Her satır ya kendi commit'ine,
ya da daha büyük bir initiative'e dönüşebilir. Hiçbiri "must-do
yarın"; hangileri kritik path olduğunu user belirler.

### C.1 Compliance & regulatory

- [x] KVKK DPA (Data Processing Agreement) template — `docs/templates/KVKK_DPA_TEMPLATE.md` (commit `88a533e`). TR-licensed counsel review still required before signing.
- [ ] GDPR DPA template — TR dışına açıldığında (KVKK template GDPR-compatible olarak yazıldı, refit gerekli)
- [ ] FDA-equivalent regulatory path memo — target market'larda cihaz sınıflandırması ve approval path
- [ ] SOC 2 (veya muadili sağlık) readiness self-audit
- [ ] BAA (Business Associate Agreement) template — HIPAA territory'ye girişte
- [ ] Veri saklama / silme akış dokümanı — kullanıcı silme talebi end-to-end (DELETE endpoint var, doküman yok)

### C.2 Sales / customer-facing artifacts

- [x] One-page sales sheet — `docs/templates/SALES_SHEET.md` (commit `88a533e`). Markdown only; designer'a verilince 1-page PDF oluşturulacak.
- [x] LOI template — `docs/templates/LOI_TEMPLATE.md` (commit `88a533e`). Pilot scope + 4 success-metric option + binding clauses.
- [ ] Pilot programme deeper template — full operational playbook (kickoff, weekly review cadence, support SLAs, churn signals). LOI bunun outline'ı.
- [ ] Customer reference card — use cases, integration patterns
- [ ] HIS/EHR integration spec — FHIR? proprietary? hangi sistemler? (Epic, Cerner, NIA, etc.)

### C.3 Investor-facing artifacts

- [ ] Visual pitch deck — `PITCH.md` → 10-12 slide PDF (PowerPoint/Keynote/Figma'dan birinde)
- [ ] Financial model — unit economics at n=1, n=10, n=100 hastane ölçeklerinde
- [ ] Market sizing memo — TAM/SAM/SOM kaynaklı, defensible
- [ ] Wedge / GTM doc — first customer profile, acquisition motion, neden TriAIge first
- [ ] Founder narrative — bir-sayfalık founder + team story (investor due diligence için)

### C.4 Operational maturity

- [ ] On-call rotation policy — production destek SLA, escalation path
- [ ] Incident severity matrix — P0-P3 tanımı + response SLA + comms playbook
- [ ] Status page — public-facing uptime / incident history
- [ ] QBR template — quarterly business review (pilot ve early customer'larla)
- [ ] Public roadmap — 6 ay / 12 ay, customer-facing version

### C.5 Demo & dry-run

- [x] Demo script static validation — pre-seeded scenarios swapped to proven `demo_chest_emergency.json` / `demo_abdominal.json` text; trace claim corrected; 8-step pre-flight checklist eklendi (commit `88a533e`).
- [ ] Live device walk-through — actual iOS/Android run on a real device, latency feel, visual rendering, /admin/sessions auth flow. Bunu sadece user yapabilir.
- [ ] Recorded fallback video — demo script'in 90-saniye kapsamlı kayıt
- [ ] Investor / customer demo cihaz seti — sim kart, network, hesap, charged device

### C.6 Critical safety patches (queued via spawn_task)

Demo prep validation sırasında **gerçek safety bug'ları** yakalandı.
İkisi de production code'da; demo'dan bağımsız problem.

- [ ] 🟢 **Turkish chest-pain emergency rule blind spot** — `safety_guard.py` + `rules.json` regex'leri vowel elision (`göğsümde` ≠ `göğüsümde`) ve possessive form (`koluma` ≠ `kola`) kapsamıyor. Doğal kullanıcı ifadesi her iki guard'ı atlatıp downstream'e düşüyor. Spawned chip 1 detaylı patch + regression test ile fix'ler.
- [ ] 🟢 **Turkish word-boundary gap in `canonical_extract.py`** — `\b` regex Turkish suffixed forms'ı (`karın bölgemde`, `karnım`, `karnımda`) kaçırıyor. Specialty scorer substring fallback ile route etmeye devam ediyor ama explainability trace'in "extracted canonicals" iddiası degraded. Spawned chip 2 fix'ler.

Her iki chip'in commit'i landed olduğunda C.6 ✅'a yakınsar; ana branch'e merge öncesi regression chain (`backend && python scripts/run_backend_regression.py`) confirmation gerekli.

---

## D. Process notes

- Bir item kapandığında bu dosyada **aynı commit'te** ✅ olarak mark'la,
  closing commit'in hash'ini ekle.
- Section'ı tamamen ✅'a girdiğinde alt'a "Done" subsection'a taşı —
  doc kısa kalsın.
- Yeni item ekle: ⚪ candidate olarak başla, user onayıyla 🟡 queued'a
  promote edilir. 🟢 in flight = aktif worktree veya spawn'lı agent var.
- Tarihçe kaydı: kapanmış faz dosyaları (`PLAN_KALAN_ADIMLAR.md`,
  `PLAN_SONRAKI_FAZ.md`) silinmedi — repo arkeolojisi için tutuluyor.
