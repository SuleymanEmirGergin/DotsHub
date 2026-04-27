# First-customer hypothesis — Acıbadem & Eczacıbaşı eVital

Two active conversations, two distinct buyer profiles, two different
business models. This brief is internal — to be read before the next
meeting with each account, then iterated as we learn more from the
actual conversation.

Tone reference: [`docs/PITCH.md`](../PITCH.md) — factual, hedged where
honest, specific where defensible. Every claim about either account is
hypothesised unless we have it from the buyer's mouth; this document
does not pretend to know what we have not yet been told.

---

## Acıbadem — private chain (subscription motion)

### Their pain (hypothesised)

Acıbadem operates a multi-branch private chain with significant
international medical-tourism inflow. The likely operational pains —
testable in a discovery conversation, not assumed:

- **Avoidable ER load.** Patients self-route to ER on symptoms that
  are not emergencies, occupying ER capacity that drives unrecoverable
  cost. Hypothesis: a non-trivial fraction of ER visits could be
  shifted to same-day clinic visits without clinical risk if intake
  routed them differently.
- **Nurse-line / phone-tree triage time.** Inbound phone triage by
  nurses is unrecoverable headcount on every minute spent on "where
  should I go?" intake. The same labor in the chain handles the
  international-patient flow, which is more time-consuming per call
  because of language switching.
- **Mis-routed appointments.** Patients self-book to the wrong
  specialty (cardiology vs. internal medicine; orthopaedics vs.
  rheumatology), generating reschedules, no-shows, and delayed care.
- **Multilingual catchment friction.** Acıbadem International is a
  branded inbound channel for medical tourism — Russian, Arabic,
  German, English speakers entering the funnel via international
  channels need first-touch in their language, and front-desk
  capacity in 5 languages is structurally hard to staff.

These are framed as testable hypotheses. The first 30 minutes of the
next meeting should be discovery, not pitch — confirm or refute each
of these from their mouth.

### Wedge — the smallest valuable thing

**Acıbadem International, single-branch pilot, medical-tourism
inbound.** This is the smallest valuable thing because:

- It is the part of Acıbadem most exposed to multilingual patient
  flow; our 5-locale CI contract (TR/EN/DE/RU/AR with Arabic RTL,
  per [`README.md`](../../README.md#tech-stack)) directly maps to
  their patient population in a way no domestic-only deployment does.
- A single branch limits deployment surface — no multi-branch
  rollout coordination, no chain-wide IT change-management blocker.
- International-patient flow is the segment where mis-routing has the
  highest cost (the patient travels for the appointment, so a
  reschedule is materially worse than a domestic reschedule), which
  amplifies the value of the wedge.

Alternative wedge if Acıbadem International is not the right entry
point: a single domestic branch's outpatient intake, scoped to one or
two specialties (e.g. cardiology + internal medicine, where
mis-routing between the two is common). This is the fallback wedge —
narrower clinical scope instead of narrower geographic scope.

### Lead conversation point

Open with the differentiator most aligned to their workflow: the
**deterministic emergency hard-stop as liability protection**, plus the
**audit trail as clinical-review artifact**. Both are repo-anchored:

- Emergency hard-stop in
  [`backend/app/emergency_router.py`](../../backend/app/emergency_router.py)
  runs before any LLM and is the answer their safety committee will
  ask for first. The trace names the rule that fired.
- Per-session admin event timeline replays every envelope and
  decision, replayable without redeploying — material for any clinical
  review of a flagged case.

Why these two: a chain-tier private-healthcare CMO's first concern is
not throughput uplift — it is "what happens when this misroutes". The
emergency hard-stop and the audit trail are the two answers, in that
order. Throughput / cost arguments come second, after the safety
posture is settled.

### Success criteria for the pilot

Three proposed metrics, picked from the menu in
[`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md):

1. **Emergency-rule precision ≥ `[X]`%.** Rate of true-positive
   emergency flags vs. clinician concurrence on the same sessions,
   sampled-review post-hoc. Number to be set in the LOI based on
   their historical data; we do not commit to a precision target
   ahead of seeing their case mix.
2. **Time-to-routing reduction ≥ `[Y]`% vs. existing nurse-line
   intake.** Measurable from the event timeline; baseline is their
   current phone-triage cycle time on a sampled set of intake
   sessions.
3. **Inappropriate-ER-visit reduction ≥ `[Z]`% on the eligible
   funnel.** Measured on the subset of patients TriAIge routed; we
   do not claim coverage of the whole ER funnel, only the part that
   went through the system.

NPS / patient-perceived clarity is a possible fourth metric, but
softer; we recommend Acıbadem-side decides whether to add it. Targets
on the % marks are agreed at LOI signing, not committed pre-discovery.

### Risks specific to this account

- **Safety-committee timeline.** A chain-tier private healthcare
  buyer's safety review can take 8–16 weeks before a pilot starts.
  This risk is not in the conversation; it is in the conversion path.
  Mitigation: provide the architecture doc (`docs/ARCHITECTURE.md`),
  the Sentry replay policy (`docs/SENTRY_REPLAY_POLICY.md`), the
  KVKK DPA template (`docs/templates/KVKK_DPA_TEMPLATE.md`), and the
  emergency rule list (`config/emergency_rules.json`,
  `backend/app/data/rules.json`) ahead of the safety committee
  meeting, not at it.
- **Clinical advisor gap.** Acıbadem's clinical leadership will ask
  who on our side authored the emergency rules and who reviewed them
  clinically. The honest answer is "we are recruiting a clinical
  advisor as priority hire post-seed". Naming the gap up-front
  (slide 11 of [`docs/sales/PITCH_DECK_OUTLINE.md`](PITCH_DECK_OUTLINE.md))
  is better than letting them discover it.
- **Procurement complexity at chain scale.** Acıbadem's procurement
  is not a single-decision-maker process; even after CMO buy-in,
  legal / IT / data-protection sign-offs add weeks. Mitigation:
  ship the KVKK DPA review-ready ahead of legal, ship the
  architecture-and-deployment doc ahead of IT, ship the Grafana
  dashboard read-only access for ops sign-off.
- **HIS/EHR integration scope creep.** Acıbadem operates on its own
  HIS layer; "drop into our system" is a bespoke conversation. Risk:
  the pilot's integration scope blows up before clinical scope is
  validated. Mitigation: shadow-mode first (TriAIge runs alongside
  intake without any HIS write), advisory next (TriAIge surfaces a
  recommendation to the nurse, who decides), HIS write-back is phase
  3 and out of pilot scope.
- **Reference-rights ambiguity.** The pilot terms include reference
  rights as part of the symbolic / free-pilot exchange. A chain-tier
  buyer may decline to confirm those rights pre-conversion;
  mitigation is to make the rights conditional on the chain's
  conversion to subscription, so they are not on the hook for a
  reference if they exit.

---

## Eczacıbaşı eVital — telemedicine partner (revenue-share motion)

### Their pain (hypothesised)

eVital operates a telemedicine platform with steady-state consultation
volume. The likely operational pains, framed as testable hypotheses:

- **Doctor-patient matching efficiency.** A meaningful fraction of
  telemedicine consultations are routed to the wrong specialty
  (cardiology question reaches a GP; orthopaedic question reaches
  internal medicine), leading to a second consultation, refund, or
  patient churn.
- **Doctor's first 30 seconds.** Without a structured pre-call
  summary, the doctor opens the call cold and spends the first
  minute on intake that could have been done before connection.
  Compounded across a high-volume schedule, this is meaningful
  capacity.
- **Mismatched complexity.** A telemedicine GP may see a high-acuity
  case that should have routed to ER; without a deterministic
  emergency screen ahead of the call, the platform absorbs the
  liability of having taken the consultation in the first place.
- **Patient handoff friction post-call.** The doctor recommends an
  in-person follow-up but the platform does not have a deterministic
  routing for "which specialty, which urgency". TriAIge's RESULT
  envelope is exactly that artifact.

### Wedge — the smallest valuable thing

**Pre-call triage that hands the doctor a structured summary +
suggested specialty before the call connects.** TriAIge's existing
`RESULT` envelope and the send-summary / export-summary flow
([`README.md` § API & Environment](../../README.md#api--environment))
are the wedge as-is — the doctor sees specialty, urgency, risk,
extracted canonicals, and rationale on the screen the moment the call
opens.

This is a smaller wedge than Acıbadem's because it does not require
HIS/EHR integration: eVital's telemedicine platform already passes
patient context through their session model, and TriAIge's API output
slots into that context without a chain-grade integration project.
Time-to-pilot is therefore meaningfully shorter than Acıbadem.

### Lead conversation point

Open with the **structured summary that makes their doctor's first 30
seconds productive**. This is the single concrete unit-of-value for an
eVital-tier buyer:

- Pre-call: TriAIge runs the budgeted question loop, produces a
  RESULT envelope with extracted canonicals and rationale.
- Call connects: doctor sees the summary on screen — specialty
  match, urgency, risk, top-line rationale — without scrolling.
- Post-call: if the doctor recommends in-person follow-up, the same
  envelope is the routing artifact for the chain referral.

Secondary lead point: the deterministic emergency hard-stop as a
**liability filter** for the platform — high-acuity cases that
should not be on telemedicine in the first place are deflected to
ER routing before consuming a doctor's time slot. This is platform
risk-management framing, distinct from the chain-tier liability
framing (which is patient-routing-misroute liability).

### Pricing model — rev-share, not subscription

This is the telemedicine variant. Revenue share on
triage→consultation conversion: 5–15% of the consultation fee for
sessions where TriAIge produced the pre-call summary that landed the
patient on the right specialty. Range:

- 5% — high-volume platforms, low-touch integration
- 10% — mid-tier with platform-side QBR cadence
- 15% — exclusive lane (platform-side commitment to pre-call TriAIge
  on all eligible sessions, no competing pre-triage layer)

The 15% tier raises the exclusivity question (see Risks below). We
should not lead with 15% by default; it is a negotiation lever for
exclusive access, not a pricing default.

### Lead conversation point (commercial)

Pricing framing on the commercial call: "We are aligned with your
unit economics — we earn when the patient lands on the right doctor.
A misrouted consultation costs both sides; rev-share aligns
incentives." This is the eVital-side commercial story, distinct from
the Acıbadem subscription pitch.

### Success criteria for the pilot

Telemedicine-shaped metrics, distinct from chain-tier:

1. **Suggested-specialty match rate ≥ `[X]`%.** Rate at which the
   specialty TriAIge suggested matches the specialty the doctor
   confirms post-call as appropriate. Measurable on a sampled review.
2. **Average call-prep time saved ≥ `[Y]` seconds.** Measurable on
   the platform-side telemetry, comparing call-open-to-clinical-talk
   latency on TriAIge-summarised sessions vs. control.
3. **Downstream consultation-conversion uplift ≥ `[Z]`%.** Of
   patients who entered the platform via TriAIge pre-call summary,
   what fraction completed consultation vs. patients without pre-call
   summary. This is the rev-share base — it is in our interest as
   well as theirs to lift it.

We propose 3 metrics, not 4 — telemedicine partners value tighter
metric scope than chain-tier buyers, who have more reviewers.

### Risks specific to this account

- **Exclusivity demand.** eVital may push for exclusive use of TriAIge
  in TR telemedicine — the 15% rev-share tier is the natural
  consideration in exchange. Risk: locking out other TR telemedicine
  partners in exchange for one platform's exclusivity is
  pre-revenue-stage strategically heavy. Mitigation: time-bounded
  exclusivity (e.g. 18 months) with a volume floor that triggers
  conversion to non-exclusive if not met. Negotiate, do not concede.
- **Doctor adoption resistance.** Telemedicine doctors on a fixed
  schedule may resent additional UI elements on their call screen.
  Risk: the structured summary becomes "another thing the platform
  asks me to read" and is ignored. Mitigation: pilot on opt-in
  doctors first; measure adoption rate as a leading indicator of the
  wedge before scaling.
- **Platform-side data ownership.** eVital may insist that all
  patient triage data remains within their platform, not in TriAIge's
  Supabase. Risk: this changes the deployment model toward
  on-platform processing or strict data-residency on their side.
  Mitigation: technically feasible (the backend is containerized);
  commercially this is a deployment-tier conversation, fine to
  accommodate but priced into Enterprise terms.
- **Clinical complexity ceiling.** A telemedicine partner may push
  TriAIge into complex multi-symptom presentations where the bounded
  question loop's turn budget is tight. Risk: degraded
  match-specialty rate on the long tail. Mitigation: scope the pilot
  to TriAIge's strong segments (single-system presentations, common
  outpatient complaints), expand later as the rule set matures.

---

## Cross-cutting — both accounts

### What both conversations need from us in week 1

A repeatable artifact bundle, sent ahead of the next meeting, not at
it:

1. **NDA, mutually signed.** Standard 2-way; do not let them write the
   first draft if avoidable — too long a delay loop.
2. **Technical architecture doc.** [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
   plus the system architecture mermaid from
   [`README.md` § System Architecture](../../README.md#system-architecture).
   Add a 1-page deployment diagram specific to their context (cloud
   region, integration points).
3. **Sample envelope + trace.** Real `RESULT` envelope JSON pulled
   from a demo session, scrubbed if needed, showing the full
   explanation trace as the buyer would see it. This is the artifact
   that wins or loses the safety / clinical conversation.
4. **Demo session.** Live (preferred) or recorded — 90-second beat
   sheet from [`docs/DEMO_SCRIPT.md`](../DEMO_SCRIPT.md). For
   chain-tier (Acıbadem), demo on a TR scenario; for telemedicine
   (eVital), demo on the structured-summary flow.
5. **KVKK DPA draft.** [`docs/templates/KVKK_DPA_TEMPLATE.md`](../templates/KVKK_DPA_TEMPLATE.md),
   marked as draft pending TR-licensed counsel review. Sets the
   data-protection conversation in motion before legal asks.
6. **LOI / Pilot terms.** [`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md)
   with the pilot scope and success-metrics menu. Customised per
   account on the wedge dimension.

### Concrete next steps — Acıbadem

- **Meeting cadence:** propose biweekly through pilot scoping; weekly
  during pilot if conversion happens.
- **Point of contact:** `[ACIBADEM POC NAME — title]`. Confirm
  decision-maker map: who signs off on (1) clinical safety, (2) IT /
  integration, (3) data protection, (4) procurement / commercial.
- **Decision-maker mapping (hypothesised, to be confirmed):**
  CMO / safety committee for clinical sign-off; CIO for IT
  deployment; DPO / legal for KVKK DPA; CFO / procurement for
  commercial terms. The pilot conversation lives with CMO + CIO; the
  conversion conversation pulls in legal + procurement.
- **Pre-meeting ask for the founder:** confirm Acıbadem International
  as the wedge target before the next meeting; if not the right entry
  point, swap to single-branch outpatient on cardiology + internal
  medicine specialties.

### Concrete next steps — eVital

- **Meeting cadence:** propose weekly through pilot scoping;
  telemedicine partners move faster than chain-tier on integration.
- **Point of contact:** `[EVITAL POC NAME — title]`. Confirm
  decision-maker map: who signs off on (1) platform integration, (2)
  doctor-side rollout, (3) commercial terms.
- **Decision-maker mapping (hypothesised, to be confirmed):**
  CTO / Head of Product for platform integration; clinical lead for
  doctor-side adoption; Head of Commercial for rev-share terms. The
  pilot conversation often lives with CTO + clinical lead; commercial
  pulls in late after pilot validation.
- **Pre-meeting ask for the founder:** confirm whether eVital wants
  the pre-call summary on opt-in doctors first or platform-wide; this
  determines whether the wedge is a doctor-cohort pilot or a
  platform-wide A/B.

---

## Things the founder should pre-research before the next meeting

1. **Acıbadem International's medical-tourism volume mix by source
   country.** Russian / Arabic / German / English breakdown shapes
   how strongly the 5-locale CI contract maps to the wedge. Public
   info likely available in Acıbadem's investor materials.
2. **eVital's doctor-side incentive structure.** Whether doctors
   are paid per-call or per-hour shapes whether call-prep time
   savings translate to commercial value for the platform or for the
   doctor. Affects the pricing conversation.
3. **Both accounts' incumbent pre-triage / intake software.** If
   either has an existing solution (rules-based phone-tree, a
   chatbot, a third-party intake form), the conversion path is
   "displacement" not "greenfield" — different objection set.
4. **TR private-healthcare AI procurement precedent.** Whether
   Acıbadem-tier or eVital-tier has previously bought an AI-augmented
   clinical product (any vertical) — sets the procurement-cycle
   length expectation realistically.
