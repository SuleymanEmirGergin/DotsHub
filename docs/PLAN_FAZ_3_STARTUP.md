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

- [x] One-page sales sheet — `docs/templates/SALES_SHEET.md` (commit `88a533e`).
- [x] LOI template — `docs/templates/LOI_TEMPLATE.md` (commit `88a533e`).
- [x] FAQ — `docs/sales/FAQ.md` — 20 clinical-buyer Q&A grouped by lifecycle (this commit).
- [x] First-customer hypothesis brief — `docs/sales/FIRST_CUSTOMER_HYPOTHESIS.md` — Acıbadem + eVital account briefs (this commit).
- [x] Competitive landscape — `docs/sales/COMPETITIVE_LANDSCAPE.md` — Babylon (defunct), Ada, K Health, Mediktor, TR landscape (this commit).
- [x] HIS/EHR integration spec — `docs/sales/HIS_EHR_INTEGRATION.md` — 4-tier model; finding: TR not FHIR-mandated, Tier 1 (webhook) is the realistic v1 (this commit).
- [ ] Pilot programme deeper template — full operational playbook (kickoff, weekly review cadence, support SLAs, churn signals). LOI is the outline.
- [ ] Customer reference card — use cases, integration patterns.

### C.3 Investor-facing artifacts

- [x] Pitch deck outline — `docs/sales/PITCH_DECK_OUTLINE.md` — 12-slide markdown ready for Keynote/Figma conversion (this commit). **Designed PDF still pending.**
- [x] Wedge / GTM seed — `docs/sales/FIRST_CUSTOMER_HYPOTHESIS.md` covers Acıbadem (private chain) + eVital (telemedicine) wedge analysis (this commit). Broader GTM doc still candidate.
- [ ] Visual pitch deck (designed) — outline → Keynote/Figma → PDF.
- [ ] Financial model — unit economics at n=1, n=10, n=100 hastane ölçeklerinde.
- [ ] Market sizing memo — TAM/SAM/SOM, defensible.
- [ ] Founder narrative — bir-sayfalık founder + team story (investor DD için).

### C.4 Operational maturity

- [x] DR runbook — `docs/engineering/DR_RUNBOOK.md` — 8 disaster scenarios (Supabase, Fly, Sentry, LLM, DDoS, breach, DB restore, DNS) with detection/response/comms (this commit).
- [x] Incident severity matrix — folded into `DR_RUNBOOK.md` (P0-P3 with criteria) (this commit).
- [x] Adversarial test corpus — `docs/engineering/ADVERSARIAL_TEST_CORPUS.md` — 15 categories of natural Turkish edge cases + pytest harness spec (this commit).
- [x] Load test plan + scripts — `docs/engineering/LOAD_TEST_PLAN.md` + `tests/load/{01_smoke,02_steady,03_burst,04_sustained}.js` (this commit).
- [ ] On-call rotation policy — production destek SLA, escalation path (DR_RUNBOOK ön koşulluyor).
- [ ] Status page — public-facing uptime / incident history.
- [ ] QBR template — quarterly business review (pilot ve early customer'larla).
- [ ] Public roadmap — 6 ay / 12 ay, customer-facing version.

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

### C.7 Engineering audit follow-up (PILOT-BLOCKING)

Faz 3 audit sprint'i (this commit) iki material gap surfaced. **Acıbadem dedicated-infra pilot için OK; eVital eklendiğinde RED.**

#### PII findings — `docs/engineering/PII_LEAK_AUDIT.md`

5 high-severity surface, 0 critical. Pilot DPA imzasından önce hepsi kapanmalı.

- [ ] 🔴 `notifier.py` Slack/Discord webhook'larına Turkish `reason_tr` clinical detail gönderiyor (`backend/app/notifier.py:172-211`) — webhook payload'a redaction katmanı ekle veya alert'leri jenerik formata düşür.
- [ ] 🔴 `triage_feedback.comment` (≤2000 chars free-text) DB'ye redaction olmadan insert ediliyor (`backend/app/api/routes/feedback.py:25,56-62`) — `app/core/pii.py::scrub_for_storage` çağır.
- [ ] 🟡 `triage_sessions.input_text` retention purge cron yok rağmen `PRIVACY_AND_SECURITY.md` claim ediyor — automated purge job + verification metric.
- [ ] 🟡 `triage_events.payload` USER_MESSAGE / ENVELOPE_RESULT full payload + `_meta` debug saklıyor — debug payload'ı production'da off, dev/staging'de on.
- [ ] 🟡 LLM NLU egress (Wiro/Google/OpenAI/Anthropic) Turkish health text dış sınıra geçiriyor — pre-redaction yalnız TC/phone/email; full PII scrubber pipeline'a ekle.

Bonus dead-code finding: `app/core/pii.py::mask_for_log` zero callers — kullanan yer yok, ya kaldır ya wire et.

#### Multi-tenant — `docs/engineering/MULTI_TENANT_REVIEW.md`

VERDICT: **YELLOW for 1 tenant, RED for ≥2.** `triage_sessions` schema'sında `tenant_id` yok; `_RUNTIME` cache ilk yüklenen tenant'la lock'luyor.

- [ ] 🔴 `triage_sessions` + `triage_events` + `triage_feedback` + `push_tokens` tablolarına `tenant_id` column'u ekle, foreign key + index. Migration + backfill (default tenant'a assign).
- [ ] 🔴 `_RUNTIME` cache'i tenant-aware yap — `tenant_id` parametresi olarak al, tenant başına ayrı LRU.
- [ ] 🔴 `/admin/sessions` (dashboard) tenant filter parametresi — admin user'ı kendi tenant'ının session'ını görsün, global firehose default değil.
- [ ] 🟡 `requireAdmin()` fallback fail-closed yap — `NEXT_PUBLIC_SUPABASE_ANON_KEY` unset durumunda redirect to login, default-allow değil.
- [ ] 🟡 `push_token.unregister` full `device_id` log'luyor — hash veya mask.

**Pre-pilot checklist** — load-bearing minimum: 6-8 eng-day. Acıbadem pilot dedicated infra ile bu minimum'u atlayabilir; eVital paralel başlamadan tüm 🔴'ları kapatma şart.

### C.8 Org / legal foundation (docs landed, action items pending)

`docs/org/` altında 4 doc — TR-licensed counsel review öncesi internal alignment için.

- [x] TR entity setup playbook — `docs/org/TR_ENTITY_SETUP.md` (AŞ rationale + 9-step + VERBİS 30-day) (this commit).
- [x] IP transfer plan — `docs/org/IP_TRANSFER_PLAN.md` (founder assignment + GH+SaaS transfer + TPMK marka) (this commit).
- [x] Advisor outreach — `docs/org/ADVISOR_OUTREACH.md` (clinical-advisor profile + bilingual template + agreement outline) (this commit).
- [x] Risk register — `docs/org/RISK_REGISTER.md` (24 risks; top 3: clinical advisor / emergency-recall / pipeline stall) (this commit).

**Outstanding actions (sende):**
- [ ] AŞ kuruluş — anasözleşme + lawyer + 4-6 hafta süreç.
- [ ] VERBİS kayıt — kuruluş sonrası 30 gün içinde (healthtech, kaçırılırsa idari ceza).
- [ ] Klinik advisor outreach — ilk 2-3 görüşme paralel Acıbadem/eVital pilot konuşmalarıyla.
- [ ] TPMK "TriAIge" marka başvurusu — domain acquisition'la birlikte (~6-12 ay).
- [ ] TR-licensed counsel relationship establish — anasözleşme + DPA + LOI review için.

### C.9 Brand / public surface (specs landed)

`docs/brand/` altında 3 spec — designer/dev'e hand-off için ready.

- [x] Website scaffold — `docs/brand/WEBSITE_SCAFFOLD.md` (Next.js + Vercel free; 11-page sitemap incl. KVKK Aydınlatma; Plausible analytics) (this commit).
- [x] Embedded widget spec — `docs/brand/EMBEDDED_WIDGET_SPEC.md` (iframe v1 + JS SDK v2; postMessage protocol; per-tenant CSP) (this commit).
- [x] Reference architecture — `docs/brand/REFERENCE_ARCHITECTURE.md` (security-flow + data-residency table; Fly.io ams confirmed; Supabase region pinning flagged) (this commit).

**Outstanding (sende veya tasarımcı):**
- [ ] `triaige.com` registrar acquisition — TPMK marka başvurusu paralel.
- [ ] Designer hand-off — site scaffold → tasarımlı static deploy (~3 hafta).
- [ ] Widget v1 implementation — iframe rotası + tenant-aware URL + postMessage protocol (~2-3 hafta eng).
- [ ] Supabase region pin — EU-Central'e taşı veya pin et, DPA gerektiriyor (`REFERENCE_ARCHITECTURE.md` flag).

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
