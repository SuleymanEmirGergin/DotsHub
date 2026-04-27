# Public Website Scaffold — `triaige.com`

> **What this is.** A design and structural specification for the public TriAIge website. Not the website itself. A founder hands this document to a designer plus a developer (or to themselves on a free afternoon) and gets a buildable plan.

> **What this is not.** This is not a brand book — that lives elsewhere. This is not the dashboard or the mobile app — those are separate surfaces. This is not the embedded widget — see [`EMBEDDED_WIDGET_SPEC.md`](EMBEDDED_WIDGET_SPEC.md). This document covers only the public marketing + information site at `triaige.com`.

> **Domain status.** `triaige.com` is treated as the placeholder domain throughout. Acquisition is tracked in [`docs/EXTERNAL_RENAME_CHECKLIST.md`](../EXTERNAL_RENAME_CHECKLIST.md).

---

## 1. Why this site exists

The site serves three distinct audiences. Each one needs different content, structure, and proof. Building one page for "everybody" is the failure mode.

### Audience A — Hospital decision-makers (after a sales conversation)

A clinical director, COO, CIO, or innovation lead has had a sales call. They want to:

- Confirm what the product actually does, in clinical-safety language
- Get architecture + compliance answers their security team will ask
- See the pricing shape and the pilot offer
- Hand a URL to a colleague without re-pitching it

**Pages they read:** `/`, `/product`, `/safety`, `/integrations`, `/security`, `/pricing`, `/contact`.

**What they need to feel:** "This is operationally serious. KVKK is handled. The deterministic safety story is real, not marketing. There is a low-risk way to start."

### Audience B — Investors (technical due diligence)

A pre-seed or seed investor, or a strategic-investor associate doing diligence. They want to:

- Validate the founder's narrative against public artifacts
- Find the technical depth (architecture, compliance posture, engineering hygiene)
- See traction signals — partners in conversation, pilot status, repo activity

**Pages they read:** `/`, `/product`, `/safety`, `/security`, `/about`, `/blog` (for cadence + thought leadership).

**What they need to feel:** "This founder ships. The compliance story is not bolted on. The product is not vapor."

### Audience C — Future hires + advisors

An engineer, a clinician, or a domain advisor who has heard about TriAIge through a network mention. They want to:

- See who is on the team
- See what the engineering culture looks like
- See the mission and the why

**Pages they read:** `/`, `/about`, `/blog`, `/contact`.

**What they need to feel:** "This is a team I want to email."

A single navigation must serve all three. The home page is the only page where all three audiences land first; every other page is conditional on a specific journey.

---

## 2. Tech stack recommendation

### Stack

- **Framework:** Next.js (App Router). The dashboard is already Next.js; the founders are familiar; Next static export deploys cleanly.
- **Hosting:** Vercel free tier. Domain on Vercel DNS (or external DNS pointing to Vercel). Bandwidth + build limits on the free tier are well above what a marketing site of this size will hit.
- **Content authoring:** MDX files in the repo for `v1`. Blog posts as `*.mdx` under `content/blog/`. No CMS overhead. Migrate to Sanity or Contentful only if blog volume goes above ~1 post per fortnight and a non-engineer needs to author.
- **Styling:** Tailwind, matching the dashboard's token convention. Reuses tokens defined in [`docs/DASHBOARD_THEME.md`](../DASHBOARD_THEME.md) and `dashboard/app/globals.css`. See §8 below.
- **i18n:** `next-intl` or `next-i18next`, mirroring the approach in `dashboard/messages/`. TR + EN at launch.
- **Analytics:** Plausible (see §7).
- **Forms:** Formspree, Tally, or Netlify Forms for the `/contact` form. No backend.

### Cost target

| Item | Monthly cost |
| ---- | ------------ |
| Vercel hosting (free tier) | $0 |
| Domain (`triaige.com`) | ~$1.50 (annualized) |
| Plausible Analytics | $9 (cloud, EU-hosted) — or self-host for $0 |
| Formspree / Tally | $0 free tier |
| **Total target** | **$0–30 / month** |

The whole stack should fit in one developer's head and survive a 12-month period of zero maintenance attention without breaking. That is the constraint.

---

## 3. Page hierarchy (sitemap)

```
/                       Home — tagline + 3 differentiators + pilot CTA
/product                What it does (deep-dive content from PITCH.md)
/safety                 Deterministic emergency layer + audit trail story
/integrations           HIS / EHR fit (4 integration tiers)
/pricing                Tier table + telemedicine partner model + pilot offer
/security               KVKK, encryption, Sentry posture, audit trail
/about                  Team + origin story + mission
/blog                   Blog index (initially empty, structure ready)
/blog/<slug>            Individual posts
/contact                Sales + support emails + form
/privacy-policy         Legal — placeholder for lawyer review
/terms                  Legal — placeholder for lawyer review
/kvkk-aydinlatma        KVKK Aydınlatma Metni (mandatory in TR)
/tr/...                 Turkish locale mirror of all of the above
/en/...                 English locale mirror
```

Routing convention: locale prefix in the URL (`/tr/product`, `/en/product`). Default redirect from `/` follows `Accept-Language`, falling back to `tr`.

---

## 4. Content blocks per page

For each page, the sections it contains, the source of the content from this repo, and notes on what is genuinely new vs. restructured.

### `/` Home

- **Hero:** the tagline ("It does not diagnose. It determines where to go, and how fast.") plus a one-sentence subhead. Source: [`docs/PITCH.md`](../PITCH.md) opening.
- **Three-up differentiators:** deterministic emergency hard-stop, bounded agentic loop, KVKK-native. Source: [`docs/PITCH.md`](../PITCH.md) "Why this is different".
- **Audience-split CTAs:** "Run a pilot at our hospital" → `/pricing`. "Read the architecture" → `/product`. "Talk to the team" → `/contact`.
- **Trust strip:** Acıbadem + eVital logos once permission is in writing (not before). Until then: a single neutral line of social proof.
- **Footer:** standard — links to legal pages, GitHub repo, contact.

### `/product`

- **What it does — flow narrative.** The four envelope types and how they chain. Source: [`docs/PITCH.md`](../PITCH.md) "The solution".
- **What pilot stakeholders evaluate.** Source: [`docs/PITCH.md`](../PITCH.md) "What pilot stakeholders should evaluate".
- **Architecture at a glance.** Mermaid diagram from [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md). Linked deeper to [`docs/brand/REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) for the diligence-grade version.
- **What this is NOT.** Source: [`docs/PITCH.md`](../PITCH.md) "What this is NOT" — keep this verbatim, it is one of the strongest differentiators.

### `/safety`

- **The deterministic emergency layer.** Plain-language version of how `backend/app/emergency_router.py` runs before any LLM and hard-stops the flow.
- **The audit trail.** What gets logged per turn; the per-session event timeline; how a safety reviewer reproduces a session.
- **Honest framing.** "Not FDA-cleared, not CE-marked as a medical device. This is a routing layer that sits upstream of clinical decision-making." Do not soft-pedal this. Hospital safety committees notice.
- **Quarterly PII audit.** Source: [`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md) §6.

### `/integrations`

- **The four integration tiers** (standalone widget → SDK embed → REST API → FHIR-native). Source: `docs/HIS_EHR_INTEGRATION.md` (being created in parallel).
- **The widget option.** One-line summary linking to [`EMBEDDED_WIDGET_SPEC.md`](EMBEDDED_WIDGET_SPEC.md) for the technical reader.
- **Compatibility matrix.** Which Turkish HIS systems we have validated against (placeholder until confirmed: Probel, Akgün, Doruk, Logo HIS, etc. — `[VERIFY with each vendor]`).

### `/pricing`

- **Tier table.** Pilot / Starter / Growth / Enterprise. Source: [`docs/templates/SALES_SHEET.md`](../templates/SALES_SHEET.md) plus the LOI template's pilot terms.
- **Telemedicine partner model.** The eVital-shaped partnership: revenue-share or seat-priced for a partner that resells to its own hospital network.
- **Pilot offer.** Verbatim from [`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md) §3 — 3 months, 1 clinical unit, 100 patients, 2+ measurable success metrics agreed in writing, no auto-renew.
- **What's not on the page.** Specific dollar amounts. Hospital procurement is custom; the page should drive a conversation, not pre-anchor a number.

### `/security`

- **KVKK posture.** Source: [`docs/PRIVACY_AND_SECURITY.md`](../PRIVACY_AND_SECURITY.md) plus the Sentry replay policy.
- **Encryption + transit.** TLS in transit; managed Postgres encryption at rest. Hashed device IDs.
- **Audit trail.** Per-session event timeline.
- **Data subject rights.** `DELETE /v1/me/sessions/{session_id}` endpoint — concrete erasure mechanism (CHANGELOG 4.6.0). This is rarely shown by competitors and worth highlighting.
- **Sub-processors list.** Supabase, Sentry, Grafana Cloud, LLM provider, Vercel, Plausible. Region for each. Cross-references [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md).

### `/about`

- **Team:** 3 co-founders. Photo + 1-paragraph bio + LinkedIn each. Clinical advisor placeholder ("we are looking for our first clinical advisor") — honest framing, not staged.
- **Origin story.** Why a Turkish pre-triage layer, why deterministic-first, why now. Two paragraphs.
- **Mission.** One sentence. Aligns with the tagline.

### `/blog`

- Index page listing posts in reverse chronological order.
- Initially empty (or one launch post). Structure ready so `content/blog/<slug>.mdx` posts land cleanly.
- RSS feed at `/blog/rss.xml` for technical readers.

### `/contact`

- Sales email: `sales@triaige.com` (or founder direct).
- Support email: `support@triaige.com`.
- Form: name, organization, role, message. Honeypot for spam, no captcha.
- KVKK Aydınlatma link in form footer.

### `/privacy-policy`, `/terms`, `/kvkk-aydinlatma`

- Placeholder text marked clearly as placeholder. Do not ship the site to production with these as lorem ipsum — even private-link launches will be screenshotted.
- Source for `/kvkk-aydinlatma`: should mirror what the mobile app and dashboard already show. This is a legal-review item.

---

## 5. Localization

**Launch scope: TR + EN.**

This mirrors the deliberate scope choice on the mobile app and the dashboard. The mobile app supports five locales (TR/EN/DE/RU/AR) because the patient-facing surface needs to meet the patient where they are — including international patients in TR clinical catchments. The marketing website does not have that constraint. A German-speaking investor reads English; a Russian-speaking hospital CIO reads English; an Arabic-speaking partner reads English or has TR-fluent staff. RU, DE, AR for the website is over-build.

**Defer the question to international expansion.** When a non-TR market becomes a real conversation (not before), revisit this in a one-pager. The mobile + dashboard locale CI gate will tell you if the website needs to follow.

---

## 6. SEO posture

The instinct is to chase volume. The right move is to chase intent.

**Target queries (TR-first):**

- `hastane ön triyaj` (hospital pre-triage)
- `pre-triage AI Türkiye`
- `KVKK uyumlu sağlık AI` (KVKK-compliant healthcare AI)
- `hastane chatbot KVKK`
- `triaige` (brand defense)
- `Acıbadem dijital triyaj` (partnership-adjacent — only after Acıbadem signs)
- `sağlık Bakanlığı KVKK AI` (regulatory-adjacent)

**Target queries (EN):**

- `Turkish hospital pre-triage AI`
- `KVKK-compliant medical AI`
- `deterministic clinical triage`

**Don't target:**

- Generic "AI healthcare" / "medical chatbot" — too broad, occupied by global SaaS, low intent.
- Patient-facing self-diagnosis terms — wrong audience and unsafe positioning.

**Practical SEO hygiene:**

- Meaningful `<title>` and `<meta description>` per page, in TR and EN.
- Open Graph + Twitter Card metadata (founder tweets the link, partners share internally).
- `sitemap.xml` auto-generated by Next.
- `robots.txt` allowing all reputable crawlers.
- Don't pay for tools; don't hire an SEO agency. The five queries above are the ones that matter.

**What to skip:** schema.org rich-result markup beyond the basics; aggressive backlink building; programmatic SEO. Hospital decision-makers do not arrive via long-tail SEO. They arrive via personal introduction, then verify by searching the brand.

---

## 7. Analytics + privacy-by-design

**Choice: Plausible.**

| Property | Plausible | Google Analytics |
| -------- | --------- | ---------------- |
| KVKK / GDPR cookie banner needed? | No (no cookies, no PII) | Yes |
| Hosted in EU | Yes | Mixed |
| Brand consistency with our privacy posture | Strong | Weak |
| Pricing | $9/month or self-host | "Free" with privacy cost |
| Data export | Open API | Open API |

The website's privacy posture must match the product's privacy posture. Shipping the marketing site with a Google Analytics cookie banner while the mobile app's Sentry config is policy-document grade is a credibility crack a thoughtful CIO will notice.

**Self-host alternative:** Plausible Community Edition runs on a single $5 droplet. Defensible if the founder wants $0 marginal cost.

---

## 8. Design tokens

Match the dashboard. Brand consistency across surfaces is one of the cheapest credibility signals available; the founders already paid the cost of choosing tokens once in [`docs/DASHBOARD_THEME.md`](../DASHBOARD_THEME.md) and `dashboard/app/globals.css`.

The six critical tokens to lift verbatim:

| Token | Source | Usage on website |
| ----- | ------ | ---------------- |
| `--primary` | `oklch(0.6231 0.1880 259.8145)` (cobalt blue) | Hero CTA, primary buttons, link color |
| `--accent` | `oklch(0.9514 0.0250 236.8242)` (pale blue) | Section background tint, card hover |
| `--foreground` (text) | `--dash-text` | Body copy |
| `--background` (bg) | `--dash-bg` | Page background |
| `--destructive` (error / emergency call-out) | dashboard semantic red | `/safety` page emergency hard-stop call-out |
| `--success` | dashboard semantic green | Pilot success metrics, partner logos area |

Typography: Inter (body), Source Serif 4 (headings, optional), JetBrains Mono (code samples in `/security` and `/integrations` snippets). Already loaded in the dashboard.

The website should pass a side-by-side screenshot test with the dashboard: a viewer should immediately recognize them as the same product.

---

## 9. Build-out plan (week by week, first 4 weeks)

### Week 1 — Skeleton

- Repo bootstrap: `triaige-com/` Next App Router project, Tailwind, MDX, locale routing.
- All pages exist with placeholder content.
- Navigation works; locale switcher works.
- Vercel preview deploy live behind a private link.

### Week 2 — Content fill

- `/`, `/product`, `/safety`, `/integrations`, `/pricing`, `/security` filled with real content sourced from this repo per §4.
- `/about` filled (team bios, origin, mission).
- TR content full; EN content stub-quality but present.
- One launch blog post drafted.

### Week 3 — Polish

- EN content brought to parity with TR.
- All hero images, OG images, favicons designed.
- Plausible Analytics live.
- Contact form live, end-to-end tested.
- Lighthouse score ≥ 95 on every page (matches the dashboard's bar in `dashboard/lighthouserc.json`).
- Accessibility pass — same axe-core matrix the dashboard uses.

### Week 4 — Soft launch

- Private link review with 3–5 friendly readers from each audience (a hospital sponsor, an investor, an engineer).
- Iterate on the one or two pieces of feedback that come back from each audience.
- Public DNS cutover.
- Announcement post on LinkedIn, repo README, partner newsletter (if available).

---

## 10. Effort estimate

Three viable paths, ranked by founder time cost:

| Path | Time to launch | Founder time | External cost |
| ---- | -------------- | ------------ | ------------- |
| 1 designer + 1 developer, part-time | 2 weeks | ~10 hrs total (review + content) | Designer + dev rate × 2 weeks part-time |
| 1 full-stack contractor solo | 3 weeks | ~15 hrs total | Single contract |
| Founder-built | 4 weeks | ~80 hrs concentrated | $0 |

The founder-built path is genuinely viable given the dashboard already exists in Next + Tailwind — most of the wiring is mechanical. The trade-off is the four weeks of founder time vs. three weeks of fundraising / sales motion. A founder who is not currently in active fundraising should build it; a founder mid-cycle should outsource it.

---

## 11. Out of scope for this document

- The actual website code — that is a separate repo.
- The brand book (typography rules, logo usage, voice and tone) — should exist as `docs/brand/BRAND_BOOK.md` but is outside this scaffold's remit.
- Ad campaigns, paid acquisition, growth marketing — none of these belong on the v1 website.
- A customer portal or login. The website is brochure-ware. The dashboard is the customer portal.

---

## Related documents

- [`docs/PITCH.md`](../PITCH.md) — primary content source for `/`, `/product`, `/safety`.
- [`docs/PRIVACY_AND_SECURITY.md`](../PRIVACY_AND_SECURITY.md) — primary source for `/security`.
- [`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md) — referenced in `/security`.
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) — base for the simplified `/product` diagram.
- [`docs/DASHBOARD_THEME.md`](../DASHBOARD_THEME.md) — brand-token source.
- [`docs/sales/COMPETITIVE_LANDSCAPE.md`](../sales/COMPETITIVE_LANDSCAPE.md) — positioning material referenced in `/product`.
- [`docs/templates/SALES_SHEET.md`](../templates/SALES_SHEET.md) — base for `/pricing`.
- [`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md) — base for `/pricing` pilot section.
- [`docs/EXTERNAL_RENAME_CHECKLIST.md`](../EXTERNAL_RENAME_CHECKLIST.md) — domain acquisition status.
- [`docs/brand/EMBEDDED_WIDGET_SPEC.md`](EMBEDDED_WIDGET_SPEC.md) — sibling, referenced from `/integrations`.
- [`docs/brand/REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) — sibling, referenced from `/security` and `/product`.
- `docs/HIS_EHR_INTEGRATION.md` — sibling, being created in parallel; referenced from `/integrations`.
