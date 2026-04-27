# TriAIge — Pitch Deck Outline

12-slide founder pitch outline. Markdown only; convert to Keynote / Figma /
PowerPoint downstream. Anchored to repo facts where possible — placeholders
in `[BRACKET STYLE]` are author-fill before any external presentation.

Tone reference: [`docs/PITCH.md`](../PITCH.md) — factual, confident, not
breathless. Tagline: _It does not diagnose. It determines where to go,
and how fast._

---

## Slide 1 — Hook

**Subtitle:** Patients who don't know where to go are an addressable cost in every healthcare system.

**Key bullets:**
- Some panic and visit emergency unnecessarily; others delay despite warning signs.
- Today the routing decision lives in a search engine, not in an audited system.
- TriAIge sits upstream of the clinician and compresses both failure modes.

**Visual hint:** Single full-bleed image — split screen: a packed ER waiting room on the left, a patient delaying care on the right. No chart, no logo. The image carries the slide.

**Speaker note:** Open with the asymmetry. Both failure modes — over-routing and under-routing — cost the system, and both happen because the patient is alone with their browser at the moment the decision matters. We exist for that moment.

---

## Slide 2 — The problem

**Subtitle:** The intake gap is operational, not clinical.

**Key bullets:**
- Avoidable ER visits drive cost the hospital cannot recover; nurse-line phone triage time is unrecoverable headcount (per `docs/templates/SALES_SHEET.md`).
- Genuinely urgent cases sometimes arrive late because the patient hesitated or self-routed wrong.
- Multilingual catchments (medical tourism, expats, refugees) compound the problem — the patient's first interaction is often in a language the front desk does not handle.

**Visual hint:** Three-column comparison: "Patient self-route via search" vs. "Phone-tree nurse triage" vs. "TriAIge". Columns scored on auditability, multilingual, latency, cost-per-session. No fabricated numbers — qualitative checkmarks only.

**Speaker note:** This is not a clinical-decision problem; clinicians are excellent at clinical decisions. It's an upstream routing problem that ends up consuming clinical capacity. We frame as such on every call.

---

## Slide 3 — The solution

**Subtitle:** A policy-driven, explainable, safety-first pre-triage layer.

**Key bullets:**
- One unified API: `POST /v1/triage/turn` returns one of four envelopes — `EMERGENCY`, `SAME_DAY`, `QUESTION`, `RESULT` (per [`README.md`](../../README.md#envelope-model)).
- Deterministic emergency rules engine runs **before** any model — hard-stops the flow with no override path (`backend/app/emergency_router.py`).
- Budgeted agentic question loop, not an open-ended chatbot — bounded turns, deterministic scoring, named stop reason in every trace.
- Full per-session audit timeline plus an explainability trace on every `RESULT` (top specialty rationale, why questioning stopped, risk reasons).

**Visual hint:** Simplified architecture diagram — adapt the mermaid in [`README.md` § System Architecture](../../README.md#system-architecture). User → API → Canonical Extraction → Emergency Rules (red hard-stop branch) → bounded Question Loop → RESULT. Strip everything that isn't on the data path.

**Speaker note:** Three claims, in order: it does not diagnose; it does hard-stop emergencies before any LLM runs; it shows its work on every result. The rest of the deck is evidence for those three.

---

## Slide 4 — Why now

**Subtitle:** TR-first market timing converges on three independent curves.

**Key bullets:**
- **KVKK enforcement** has matured: TR private chains now treat data-processing posture as a procurement criterion, not a back-office concern. TriAIge ships KVKK-aware logging, hashed IDs, PII masking, and `DELETE /v1/me/sessions/{session_id}` (CHANGELOG 4.6.0) — built in, not bolted on.
- **Post-COVID telemedicine adoption** is durable in TR; eVital-class players have steady-state consultation volume that needs a structured pre-call summary, not just a video pipe.
- **AI safety regulation** (EU AI Act high-risk classification of medical-adjacent systems; TR following pattern) is forcing buyers away from black-box LLM chatbots toward auditable, rule-driven systems with explanation traces — exactly our shape.

**Visual hint:** Three-line chart, all going up-and-to-the-right, labelled: KVKK enforcement maturity, telemedicine session volume, AI safety regulatory gravity. Mark a circle at the intersection point: "TriAIge fits here." Numbers can be qualitative — this is a positioning slide, not a stats slide.

**Speaker note:** None of these are speculative. They're the three things our two active conversations (Acıbadem, eVital) explicitly raised in their first meeting — compliance, telemedicine throughput, and "is this a black box". We built into all three.

---

## Slide 5 — Product demo

**Subtitle:** 90 seconds, three claims proven on screen.

**Key bullets:**
- Emergency hard-stop, demonstrated on a chest-pressure scenario — `EMERGENCY` envelope returns before any model runs; the dashboard event timeline names the rule that fired.
- Same-day flow on an abdominal-pain scenario — bounded question loop, deterministic scoring, `RESULT` with the rationale on screen.
- Five-locale switch (TR/EN/DE/RU/AR with Arabic RTL) without any rebuild — same i18n contract that gates CI gates the demo.
- Full beat sheet: [`docs/DEMO_SCRIPT.md`](../DEMO_SCRIPT.md).

**Visual hint:** Two screenshot placeholders side-by-side: `[SCREENSHOT — mobile EMERGENCY envelope on Turkish chest scenario]` and `[SCREENSHOT — admin event timeline showing the rule firing]`. Add a small "demo video — 90s" QR or link footer.

**Speaker note:** I always run the live demo if the network is stable. If it isn't, the recorded fallback is on a USB stick. Either way, the goal is to show the trace, not the mobile UI — buyers' first question is "but what does the doctor see when this misroutes" and the answer is on the dashboard, not the phone.

---

## Slide 6 — Differentiators

**Subtitle:** Four things buyers ask in the first meeting; four things we built.

**Key bullets:**
- **Rule-driven safety, not LLM inference.** Emergency rules in [`backend/app/emergency_router.py`](../../backend/app/emergency_router.py) hard-stop the flow before any model sees the input. The trace names the rule. (`docs/PITCH.md` § Why this is different)
- **Deterministic by design, auditable by default.** Every `RESULT` ships extracted canonicals, top specialty rationale, why questioning stopped, and the risk reasons. There is no "the model said so" output to defend.
- **Multi-language as a CI contract.** Five locales gated by `npm run test:i18n-contract` — fails the build on drift. Same gate exists for the dashboard. Adopted across mobile in Session 12 (per CHANGELOG context).
- **Continuous improvement loop with rollback.** Tuning patches go through `.github/workflows/guardrail.yml` and revert on failure rather than ship.

**Visual hint:** 2×2 grid, each cell a differentiator with a one-line proof anchored to a file path. Use the same iconography style as [`PITCH.md`](../PITCH.md) — minimal, no decoration.

**Speaker note:** This is the slide that closes a clinical-buyer's first meeting. The CMO asks four questions in some order; this slide answers all four with file paths, not adjectives. Pull up the file in-meeting if challenged.

---

## Slide 7 — Market sizing

**Subtitle:** TR-first, defensible bottom-up.

**Key bullets:**
- **TAM (TR private healthcare):** `[FOUNDER FILL — # of private chain hospitals × annual outpatient + ER session volume × routing-relevant fraction]`. Defensible source: TÜİK private hospital statistics + an estimated routing-touchable fraction.
- **SAM (private chains adopting AI-augmented intake within 24 months):** `[FOUNDER FILL — Acıbadem-tier + Memorial-tier + Medical Park-tier × addressable session volume]`. Anchor: pipeline includes Acıbadem and eVital, both top-tier TR private healthcare players.
- **SOM (3-year):** `[FOUNDER FILL — n hospitals × annual subscription tier × telemedicine rev-share blended ARPU]`. Cross-reference to pricing in slide 8.
- Internationalization (EU, GCC) framed as upside, not gated on TR validation.

**Visual hint:** Concentric-circle TAM/SAM/SOM diagram with a single "we are here" arrow on SOM. Each ring labelled with a placeholder value — explicitly bracketed so the founder fills with sourced numbers, not us.

**Speaker note:** Honest hedge: this slide has placeholders, on purpose. We refuse to fabricate market numbers, and the right person to source TR private healthcare session volume is the founder with TÜİK + chain-level disclosed numbers. The reasoning hook is bottom-up — sessions per chain × addressable fraction × pricing tier — not top-down "AI in healthcare = $X billion."

---

## Slide 8 — Business model

**Subtitle:** Two motions: subscription for chains, rev-share for telemedicine.

**Key bullets:**
- **Pilot:** 3 months free / symbolic in exchange for engagement, data access, and reference rights. Pilot terms in [`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md).
- **Subscription, tiered by session volume:**
  - Starter — ≤1K sessions/mo — `₺12K/ay (~$400/ay)`
  - Growth — ≤10K sessions/mo — `₺50K/ay (~$1.7K/ay)`
  - Enterprise — unlimited + integration / support — `₺150K+/ay (~$5K+/ay)`
  - Per-session overage above tier: `₺3-5/session`
- **Telemedicine partner:** revenue share on triage→consultation conversion (5–15%). Hands the doctor a structured summary + suggested specialty before the call connects — see [`docs/sales/FIRST_CUSTOMER_HYPOTHESIS.md`](FIRST_CUSTOMER_HYPOTHESIS.md) for the eVital wedge.

**Visual hint:** Two-column layout — left: subscription tier table (Starter / Growth / Enterprise rows × price / session cap / overage columns); right: rev-share diagram (triage → handoff → consultation → % of consultation fee). Mark the wedge clearly: subscription = chain motion, rev-share = telemedicine motion.

**Speaker note:** We are not a single-pricing-model company; we are two motions sharing one engine. Acıbadem-tier wants predictable subscription with annualized procurement; eVital-tier wants rev-share aligned with their unit economics. The pricing in this slide is direction, revisable per pilot conversation.

---

## Slide 9 — Competition

**Subtitle:** We are the auditable middle path.

**Key bullets:**
- **Babylon (UK / global):** broad consumer health chatbot; not deterministic, not auditable per session in the way clinical safety committees expect; commercial volatility post-2023.
- **Ada Health (DE / global):** symptom-checker positioned consumer-direct; strong content, less infrastructure for chain-grade audit trail and multilingual CI gating.
- **K Health (US):** clinician-augmented chat with prescription pathway; US-regulatory-shaped product, weak fit for TR private chain workflow and TR-language depth.
- **TR landscape:** no dominant local incumbent in pre-triage as a B2B layer for chains; existing TR digital-health is appointment booking + telemedicine UI, not policy-controlled triage with audit trails. Detailed analysis lives in `[PLACEHOLDER — docs/sales/COMPETITIVE_LANDSCAPE.md, to be written]`.

**Visual hint:** 2×2 positioning grid. Axes: Auditability (low → high) × TR-specific fit (low → high). Babylon, Ada, K Health clustered low-auditability or low-TR-fit; TriAIge anchored top-right. One paragraph at the bottom: "competitive deep-dive in `docs/sales/COMPETITIVE_LANDSCAPE.md`".

**Speaker note:** None of these competitors are wrong; they're aimed at different buyers. We are not a consumer symptom-checker; we are an infrastructure layer for chains and telemedicine partners that need the audit trail. That framing also explains why we don't compete on UX richness — our UX richness target is the admin event timeline, not the patient screen.

---

## Slide 10 — Traction

**Subtitle:** Two active conversations with TR private healthcare leaders + a production-grade engineering bar.

**Key bullets:**
- **Active deal pipeline:** Acıbadem — active conversation; Eczacıbaşı eVital — active conversation. Both top-tier TR private healthcare. See [`docs/sales/FIRST_CUSTOMER_HYPOTHESIS.md`](FIRST_CUSTOMER_HYPOTHESIS.md) for wedge analysis.
- **Engineering maturity:** 15+ GitHub Actions workflows including backend regression chain, dashboard Lighthouse budgets, mobile EAS pipeline, Maestro e2e, capability-drift detection, weekly Sentry smoke, periodic `/health` probe, secret scanning per push (per [`docs/PITCH.md` § Operational maturity](../PITCH.md)).
- **Quality signals:** real-corpus regression climbed 60.8% → 79.1% across sessions (CHANGELOG 4.6.0 + session 8); axe-core a11y blocks on serious / critical WCAG 2.1 AA violations across light + dark themes; KVKK-safe Sentry Session Replay; Prometheus `/metrics` + Grafana Cloud dashboard with 4 alerts plumbed in.
- **i18n breadth:** 5 locales (TR/EN/DE/RU/AR with Arabic RTL) with a CI contract test gating drift — operational from day one for international medical tourism inbound.

**Visual hint:** Three boxes: "Pipeline" (Acıbadem, eVital logos as `[LOGO PLACEHOLDER]`), "CI maturity" (GitHub Actions workflow count + 4 named badges), "Quality" (regression % climb sparkline 60.8 → 79.1, plus a small axe-core / Lighthouse / Sentry strip).

**Speaker note:** We are pre-revenue but not pre-product. The traction story is two active deals and a CI surface that proves we will not embarrass a buyer's safety committee. Investors who care about engineering rigour read this slide; investors who only care about ARR will tell us so on this slide and we move on.

---

## Slide 11 — Team

**Subtitle:** 3 co-founders shipping a production-oriented MVP. Clinical advisor is hire-1 priority.

**Key bullets:**
- `[FOUNDER 1 — name + role: e.g. CEO / Product]` — `[1-line domain credibility]`
- `[FOUNDER 2 — name + role: e.g. CTO / Engineering]` — `[1-line credibility, anchor to repo if engineering]`
- `[FOUNDER 3 — name + role: e.g. COO / GTM]` — `[1-line credibility, anchor to TR healthcare network if applicable]`
- **Known gap, named publicly: clinical advisor.** First priority hire post-seed. We do not pretend we have one. A practising clinician on advisory or co-founder seat closes a gap that affects pilot conversion at chain-tier — Acıbadem's safety committee will ask, and the right answer is "we are recruiting now, here is the profile". Per `docs/PLAN_FAZ_3_STARTUP.md` § C.1, the regulatory path memo also depends on this hire.

**Visual hint:** Four boxes in a row. Three founder boxes with `[PHOTO PLACEHOLDER]` and 2-line bio. Fourth box visually distinct (dashed border, lighter background): "Clinical Advisor — hiring". This is the slide that signals self-awareness. Investors notice when teams hide gaps; they reward teams that name them.

**Speaker note:** I name the clinical-advisor gap on this slide, every time. It is not a weakness — it is the next hire, and the seed round funds it. Saying it out loud disarms the question before the investor asks, and credentials the team's judgment in front of safety-committee-aware buyers.

---

## Slide 12 — The ask

**Subtitle:** Seed to convert two active pilots and hire the clinical advisor.

**Key bullets:**
- **Round size:** `[SEED ROUND SIZE — e.g. $1.5M]`
- **Use of funds:**
  - `[X%]` — clinical advisor hire + 1 medical-content engineer (regulatory and rule-set authoring depth)
  - `[Y%]` — 2 pilot conversions (Acıbadem + eVital) including dedicated pilot-success engineer for 12 months
  - `[Z%]` — TR-licensed legal counsel for KVKK DPA review (per `docs/templates/KVKK_DPA_TEMPLATE.md` review note) + the pre-FDA / CE-mark regulatory-path memo
  - `[W%]` — runway: ~`[18-24 months]` to revenue inflection
- **Milestones we sign up to:** 2 paid pilot conversions in 9 months, clinical advisor on board in 4 months, regulatory-path memo published in 6 months.
- **What we are not asking for:** product validation — that lives in the demo and the repo. We are asking for runway to convert active conversations.

**Visual hint:** Single-slide pie chart for use of funds, with the four buckets labelled. Bottom strip: 3 milestones with checkbox icons + dates. Right side: contact card with founder name + email + repo link + GitHub.

**Speaker note:** Close confidently. Two active conversations is rare at this stage; an investor either resonates with TR-private-healthcare-as-a-thesis or they don't, and on this slide we find out. End on the same line as `docs/PITCH.md`: "It does not diagnose. It determines where to go, and how fast."

---

## Conversion notes (for the founder)

- Convert this markdown to Keynote / Figma / PowerPoint with the same numbering. Do not collapse slides; the 12-slide structure is load-bearing for the narrative arc.
- Replace every `[BRACKET]` with a sourced value before any external presentation. Placeholders that survive into a deck are a credibility tax.
- Slide 5 needs two real screenshots — recommend pulling them during the next clean local demo run (per [`docs/DEMO_SCRIPT.md`](../DEMO_SCRIPT.md) pre-flight).
- Slide 7 (market sizing) is the single highest-risk slide for fabrication. Source every number from TÜİK, hospital annual reports, or OECD TR healthcare statistics. If a number is estimated, mark it estimated.
- Slide 9 references a competitive landscape doc that does not yet exist — `docs/sales/COMPETITIVE_LANDSCAPE.md` is the natural follow-up file.
