# TriAIge — Buyer FAQ

20 questions a clinical buyer (CMO, CIO, COO of a private chain) or a
telemedicine partner asks in early conversations. Tight answers anchored
to repo where possible. Where the honest answer is "we don't have this
yet", we say so.

Tone reference: [`docs/PITCH.md`](../PITCH.md) — factual, hedged where
honest, specific where defensible.

---

## First 5 minutes

#### 1. What is TriAIge in one sentence?

A policy-driven, explainable, safety-first symptom pre-triage layer that
sits upstream of your clinical staff and routes the right patient to the
right specialty at the right speed — without ever attempting to diagnose
them. Tagline from [`docs/PITCH.md`](../PITCH.md): _It does not diagnose.
It determines where to go, and how fast._

#### 2. Who is it for?

Two buyer profiles. (1) Private hospital chains (Acıbadem-tier,
Memorial-tier) that want to compress the patient self-routing gap and
cut avoidable ER load — subscription model. (2) Telemedicine partners
(eVital-tier) that want a structured pre-call summary handed to the
doctor — revenue-share model. See
[`docs/sales/FIRST_CUSTOMER_HYPOTHESIS.md`](FIRST_CUSTOMER_HYPOTHESIS.md)
for the wedge analysis on both.

#### 3. Why now?

Three converging curves: KVKK enforcement maturing in TR (compliance is
now a procurement gate, not a back-office concern), durable
post-COVID telemedicine volume needing structured pre-call intake, and
AI safety regulation (EU AI Act, TR following pattern) pushing buyers
away from black-box LLM chatbots toward auditable rule-driven systems.
TriAIge is built for that intersection by design, not by retrofit.

#### 4. Who is behind it?

Three co-founders shipping a production-oriented MVP. Active deal
pipeline includes Acıbadem and Eczacıbaşı eVital. Known gap: no
clinical advisor or co-founder yet — that is the first priority hire
after seed (named explicitly on slide 11 of
[`docs/sales/PITCH_DECK_OUTLINE.md`](PITCH_DECK_OUTLINE.md), not
hidden). TR-licensed legal counsel for KVKK DPA review is also queued.

#### 5. Where's the demo?

A 90-second narrated walkthrough is documented in
[`docs/DEMO_SCRIPT.md`](../DEMO_SCRIPT.md), with a beat sheet, pre-flight
checklist, fallback plan, and pre-baked Q&A. Live demo runs on a real
device against a hot backend; recorded fallback exists for offline
meetings. Three claims demonstrated on screen: emergency hard-stop is
rule-driven, the explanation trace is real, the system is multilingual
and operationally observable.

---

## Safety & clinical

#### 6. What is your emergency-miss rate?

Honest answer: we do not publish a clinical sensitivity number, because
we are not a diagnostic device and do not have a cleared clinical study
behind the rules engine. What we do publish: a real-corpus regression
that climbed 60.8% → 79.1% across recent sessions (CHANGELOG 4.6.0 +
session 8 context), and the deterministic emergency rules engine in
[`backend/app/emergency_router.py`](../../backend/app/emergency_router.py)
that hard-stops the flow before any model runs. Emergency-miss
benchmarking against your own historical case load is the right
shape for a pilot success metric — see
[`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md).

#### 7. Who is liable if the system misroutes?

The system does not diagnose; the disclaimer is explicit on the result
screen and embedded in the API envelope. The clinician remains the
decision-maker, and TriAIge produces an audit-grade rationale per
session — extracted canonicals, top specialty rationale, why
questioning stopped, risk reasons — that gives a defensible
investigation artifact for any flagged case (per
[`docs/PITCH.md` § Why this is different](../PITCH.md)). Liability
allocation is contractual; we operate as a clinical-decision-support
layer, not a medical device. Final liability framing lives in the LOI
and DPA — TR-licensed counsel review is queued (`docs/PLAN_FAZ_3_STARTUP.md`
§ C.1).

#### 8. Can a doctor override what TriAIge says?

Yes — by design, TriAIge is advisory upstream of the clinician. The
result envelope is a recommendation with a rationale; the clinician's
chart is the system of record. There is no "override TriAIge" button
because TriAIge does not commit anything to the chart — it routes the
patient and presents the trace. The override path is the doctor's
existing workflow.

#### 9. What does the audit trail actually look like?

A per-session event timeline in the admin dashboard: every envelope,
every rule firing, every question turn, every scoring decision, and the
stop reason — replayable without redeploying anything. Safety
reviewers reproduce user-reported issues from the timeline directly.
Plus structured JSON logs with `request_id` on every backend response,
Prometheus `/metrics` for ops, and Sentry breadcrumbs with KVKK-safe
Session Replay (per
[`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md)) — all
captured by default, not enterprise add-ons.

#### 10. What is your training data and how do you avoid bias?

The rules engine is **not** trained — it is authored, deterministic,
and version-controlled in `config/emergency_rules.json` and
`backend/app/data/rules.json`. The agentic question loop and specialty
scorer use a deterministic scorer over canonical extractions, not a
free-form LLM (per [`docs/PITCH.md` § Why this is different](../PITCH.md)).
LLM-adjacent steps (e.g. canonical extraction) have deterministic
fallbacks. Bias surface area is therefore the rule set itself,
which is human-readable, version-controlled, and reviewable by your
safety committee — not a black-box embedding. The continuous improvement
loop (feedback → tuning patch → guardrail check → deploy or rollback,
per [`README.md`](../../README.md#continuous-improvement-loop)) is the
mechanism for correcting bias when it surfaces.

---

## Integration & operations

#### 11. How does it integrate with our HIS / EHR (Epic, Cerner, Avicenna, NIA)?

Today the integration surface is the API: `POST /v1/triage/turn`
returns the `RESULT` envelope (specialty, urgency, risk, full trace),
shaped to drop into a referral or routing record. EHR / HIS-specific
adapters (FHIR, proprietary) are bespoke per pilot — that is part of the
Enterprise tier. We do not pretend we have a generic Epic plugin; we
pretend we have a clean API that integrates well per the partner's
schema. HIS/EHR integration spec per chain is on the Faz 3 backlog
(`docs/PLAN_FAZ_3_STARTUP.md` § C.2).

#### 12. What's the deployment model — cloud, on-premise, or hybrid?

Cloud-native today: backend on Fly.io (per CHANGELOG 4.6.0 deploy
scaffold + always-on tuning), Postgres on Supabase, optional Redis for
multi-instance rate limiting. Dashboard on Vercel; mobile via EAS Build.
On-premise / private cloud is feasible — the backend is a containerized
FastAPI service with no managed-cloud lock-in beyond Postgres — but
will be a pilot-specific scope conversation, not a published SKU.

#### 13. Where does the data live? Is it KVKK-compliant?

Data residency: Supabase region selectable per deployment; for TR
private-chain pilots, EU region with KVKK-compatible processor terms is
the default. KVKK posture is built in, not bolted on: privacy-aware
logs, hashed device IDs (never raw fingerprints), PII masking
enforced by a backend masker and a mobile `beforeSend` Sentry scrubber
sharing the same key list, KVKK-safe Sentry Session Replay (per
[`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md)), and a
`DELETE /v1/me/sessions/{session_id}` endpoint as a concrete erasure
mechanism (CHANGELOG 4.6.0). The KVKK DPA template is at
[`docs/templates/KVKK_DPA_TEMPLATE.md`](../templates/KVKK_DPA_TEMPLATE.md).
TR-licensed counsel review of the DPA is required before signing — per
`docs/PLAN_FAZ_3_STARTUP.md` § C.1. Honest hedge: SOC 2 / ISO 27001 /
HITRUST are not in place today; SOC 2 readiness is on the same Faz 3
backlog.

#### 14. What's your support SLA and on-call posture?

Honest hedge: a formal published SLA (P0/P1/P2 response times,
escalation matrix, status page) is on the Faz 3 backlog
(`docs/PLAN_FAZ_3_STARTUP.md` § C.4). Operationally, what exists
today: weekly Sentry DSN smoke, periodic `/health` probe alerting, a
runbook (`docs/RUNBOOK.md` per CHANGELOG 4.6.0), and an incidents
directory + template. Pilot SLA terms are negotiated per LOI. Enterprise
tier includes a dedicated pilot-success engineer for 12 months
(per use-of-funds, `docs/sales/PITCH_DECK_OUTLINE.md` slide 12).

#### 15. What's your downtime / incident history?

We do not yet have a public status page or year-of-uptime number to
quote. What exists today: Prometheus `/metrics` + Grafana Cloud
dashboard with 4 alerts plumbed in (CHANGELOG 4.6.0); periodic `/health`
probe via `health-alert.yml`; Sentry crash + KVKK-safe replay; an
`incidents/` directory with template (CHANGELOG 4.6.0). For pilot
buyers: we share the Grafana dashboard read-only access, share-in
incidents directly, and commit to a transparent post-mortem on any
production incident. A public status page is queued
(`docs/PLAN_FAZ_3_STARTUP.md` § C.4).

---

## Commercial

#### 16. What's your pricing model?

Two motions sharing one engine. **Subscription, tiered by session
volume:** Starter (≤1K sessions/mo) `₺12K/ay (~$400/ay)`; Growth
(≤10K sessions/mo) `₺50K/ay (~$1.7K/ay)`; Enterprise (unlimited +
integration / support) `₺150K+/ay (~$5K+/ay)`. Per-session overage above
tier `₺3-5/session`. **Telemedicine partner:** revenue share on
triage→consultation conversion, 5–15%. Pricing is direction, revisable
per pilot conversation; published rate card is post-pilot. See
[`docs/sales/PITCH_DECK_OUTLINE.md`](PITCH_DECK_OUTLINE.md) slide 8.

#### 17. What does a pilot look like? Free or paid?

Pilot: 3 months free / symbolic in exchange for engagement, data
access, and reference rights. Scoped pilot is one specialty path or one
demographic in one locale, run alongside existing intake — shadow mode
first, then advisory. Success metrics are agreed in writing before
pilot start; a menu of options is in
[`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md). At
month 3 we meet, look at the numbers, and the buyer decides: convert,
extend, or exit. No hidden conversion clause, no auto-renew (per
[`docs/templates/SALES_SHEET.md`](../templates/SALES_SHEET.md)).

#### 18. Contract length and termination?

Pilot: 3 months, no auto-renew, exit clause is "do nothing" at month 3.
Post-pilot subscription: 12-month default term per Enterprise SKU,
6-month for Growth, 3-month for Starter. Mid-term termination on
material breach with a 30-day cure window is the default; specific
exit clauses (data return, deletion confirmation, transition support)
are in the LOI / MSA template. We are not stitching customers into
multi-year lock-ins from a pre-revenue position — the math doesn't
work for either side.

#### 19. What are reasonable pilot success metrics?

A menu, picked from at LOI signing — typically 2–4 metrics per pilot.
Concrete options grounded in what we can measure today from the event
timeline: emergency-rule precision (rate of true-positive emergency
flags vs. clinician concurrence on those same sessions);
agreement-rate against clinician routing on the same session
(post-hoc, on a sampled review); time-to-routing reduction vs.
existing intake; session-volume coverage (how many of your incoming
patients were eligible for TriAIge); NPS or patient-perceived clarity
on the result screen. Per
[`docs/DEMO_SCRIPT.md` § Q&A primer](../DEMO_SCRIPT.md), we will commit
to a target on agreement rate and emergency-rule precision in the pilot
agreement. Throughput targets depend on volume.

#### 20. What's the exit clause if we don't see value?

At month 3 of the pilot, the buyer decides: convert to subscription,
extend the pilot, or exit. Exit means: no fee, no auto-renew, full data
return in machine-readable format (CSV / JSONL of the session timeline
the buyer's data was used to generate), deletion confirmation per the
KVKK DPA, and a 30-day transition support window for any operational
hand-back. We do not believe in trapping buyers in
post-pilot — the conversion must be earned by the metrics, every
pilot.
