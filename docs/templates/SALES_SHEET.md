# TriAIge — Pre-Triage Agentic AI for Hospitals

**It does not diagnose. It determines where to go, and how fast.**

## Elevator

TriAIge is a policy-driven, explainable, safety-first symptom pre-triage layer that sits upstream of your clinical staff and routes the right patient to the right place, at the right speed — without ever attempting to diagnose them.

## The problem you face

- Avoidable emergency-department visits drive operational cost the hospital cannot recover, while genuinely urgent cases sometimes arrive late because the patient hesitated or self-routed wrong.
- Nurse-line and front-desk triage time spent on phone-tree symptom intake is unrecoverable headcount; every minute a clinician spends on "where should I go?" is a minute not spent on care.
- Patient routing today depends on the patient's own search engine — an unaccountable, unauditable, multilingual variable in your operational pipeline.

## What TriAIge does

- **Deterministic emergency hard-stop.** High-acuity scenarios (chest-pain class, etc.) short-circuit the flow before any model runs. The trace names the rule that fired — auditable by your safety committee, not "the model said so".
- **Budgeted agentic question loop.** Non-emergency flows ask a bounded number of clarifying questions with deterministic scoring. Predictable cost, predictable latency, predictable behaviour on review — never an open-ended chatbot monologue.
- **Explainability trace on every result.** Each `RESULT` envelope ships extracted canonicals, the top specialty's rationale, why questioning stopped, and the risk reasons. There is nothing to defend in a clinical review except the rule trace itself.
- **Five locales as a CI contract.** Turkish, English, German, Russian, Arabic (with RTL). A contract test fails the build if any locale drifts from the primary key set. Same gate exists for the dashboard — material for any catchment with a multilingual patient base.
- **Per-session audit timeline.** Every envelope, decision, and rule firing is replayable from the admin dashboard. Safety reviewers reproduce user-reported issues without redeploying anything; ops sees exactly what the system decided and why.

## Why this is different

- **Hard-stop emergency rules, not LLM inference.** Implemented in `backend/app/emergency_router.py`; gated before downstream modules. There is no override path.
- **Guardrails plus automatic rollback.** Tuning patches go through a guardrail workflow and revert on failure rather than ship — feedback never silently degrades the system.
- **KVKK / GDPR awareness built in, not bolted on.** Privacy-aware logs, hashed device IDs, PII masking, KVKK-safe Sentry Replay, and a `DELETE /v1/me/sessions/{session_id}` endpoint as a concrete erasure mechanism.

## Pilot offer

Run TriAIge for `[3 ay]` on `[1 klinik birim, 100 hasta]` at no cost (or low cost — by mutual agreement). Pick `[2+]` measurable success metrics from a menu that includes emergency-flag catch rate, NPS, time-to-routing reduction, and inappropriate-ER-visit reduction. Targets are agreed in writing in the LOI before pilot start. At month 3 we meet, look at the numbers, and the Hospital decides: convert, extend, or exit. No hidden conversion clause, no auto-renew.

## Compliance posture

KVKK-aware throughout (see `docs/PRIVACY_AND_SECURITY.md`); GDPR-compatible architecture with the same data-minimisation contract. TLS in transit; managed Postgres encryption at rest. Hashed device IDs, never raw fingerprints. No PII in logs — enforced by a backend PII masker and a mobile `beforeSend` Sentry scrubber sharing the same key list. Per-session audit trail in the admin dashboard. KVKK-safe Sentry Session Replay (`docs/SENTRY_REPLAY_POLICY.md`) with all text and inputs masked, free-text patient input replaced with `[SCRUBBED]` server-side, and a quarterly PII audit on the operational rotation.

## Operational signals

15+ GitHub Actions workflows on the live repo, including a backend regression chain, dashboard quality + Lighthouse budgets, mobile EAS build pipeline, Maestro e2e, capability-drift detection, accessibility audit blocking on serious / critical WCAG 2.1 AA violations across light + dark themes, weekly Sentry DSN smoke, periodic `/health` probe, and secret scanning on every PR. Prometheus `/metrics` plus Grafana Cloud dashboard with alerts plumbed in. Sentry crash + KVKK-safe replay. Structured JSON logs with `request_id` on every response. Multi-instance Redis-backed rate limiting on the public buckets. Per-bucket alert rules and per-session admin replay are on by default — not enterprise add-ons.

## Contact

`[Founder name]` — `[founder email]`
GitHub: `https://github.com/SuleymanEmirGergin/TriAIge`

Pilot conversation, KVKK DPA template, and LOI template available on request.

---

**It does not diagnose. It determines where to go, and how fast.**
