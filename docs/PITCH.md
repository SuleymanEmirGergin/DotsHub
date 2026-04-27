# Pre-Triage Agentic AI — TriAIge

## Tagline

It does not diagnose. It determines where to go, and how fast.

## What is this

Pre-Triage Agentic AI is a policy-driven, explainable, safety-first symptom
pre-triage system. A user describes symptoms in free text and receives a
specialty recommendation, an urgency envelope, a risk level, and a full
deterministic explanation trace. It is an orchestration layer with rules,
audit logs, and rollback — not a generic chatbot.

Patients who don't know where to go are an addressable cost driver in every
healthcare system: unnecessary emergency visits on one side, delayed care on
the other. A safe pre-triage step sits upstream of the clinician and
compresses both failure modes.

See [README — What Is This?](../README.md#what-is-this) for the longer
framing.

## The problem

Healthcare systems lose time and capacity because patients often do not know
where to go first. Some panic and visit emergency unnecessarily; others delay
despite warning signs. A triage step that is fast, multilingual, and
explainable — but never diagnostic — closes that gap before a clinician is
ever involved.

## The solution

- A unified turn-based API (`POST /v1/triage/turn`) that returns one of four
  envelope types: `EMERGENCY`, `SAME_DAY`, `QUESTION`, `RESULT`.
- A deterministic emergency rules engine that runs **before** any other
  module and hard-stops the flow with no override path.
- A budgeted agentic question loop — bounded turn count, deterministic
  scoring, no open-ended LLM monologue.
- Full per-session event timeline plus an explainability trace on every
  `RESULT` (top specialty rationale, why questioning stopped, risk reasons).
- A continuous improvement loop: user feedback → tuning task → config patch
  → guardrail check → deploy or rollback.

## Why this is different

- **Hard-stop emergency rules, not LLM inference.** Implemented in
  [`backend/app/emergency_router.py`](../backend/app/emergency_router.py)
  and gated before downstream modules. See README's
  [Clinical Safety Layers](../README.md#clinical-safety-layers).
- **Deterministic scoring + explanation trace.** Every `RESULT` envelope
  carries the canonicals it extracted, why the top specialty scored
  highest, why questioning stopped, and the risk reasons.
  See README's [Explainability section](../README.md#explainability).
- **Full audit trail.** Per-session and per-event logging into Supabase
  with hashed IP and session IDs; admin surfaces include a full event
  timeline and risk-aware session list.
- **Guardrails + automatic rollback.** Tuning patches go through a
  guardrail workflow (`.github/workflows/guardrail.yml`) and revert on
  failure rather than ship.
- **Multi-language i18n contract.** Five locales (TR/EN/DE/RU/AR with
  Arabic RTL) under `mobile/i18n/`, gated by a contract test
  (`npm run test:i18n-contract`) that fails CI if any locale drifts from
  the primary. Same gate exists for the dashboard.
- **KVKK / GDPR awareness.** Privacy-aware logs, PII masking, hashed IDs,
  and a documented privacy posture in
  [`docs/PRIVACY_AND_SECURITY.md`](PRIVACY_AND_SECURITY.md). A
  `DELETE /v1/me/sessions/{session_id}` endpoint exists for user-initiated
  deletion (CHANGELOG 4.6.0).

## Architecture at a glance

The full mermaid lives in
[README — System Architecture](../README.md#system-architecture). In four
lines:

1. Mobile or dashboard hits `POST /v1/triage/turn`.
2. Canonical extraction → policy orchestrator → emergency rules first; if
   triggered, the flow hard-stops with an `EMERGENCY` envelope.
3. Otherwise: same-day rules → bounded question loop → deterministic
   scoring → `RESULT` envelope with risk and explanation trace.
4. Events stream to Supabase; the admin dashboard renders timeline,
   trends, and `/health` status.

For component-level detail see
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md).

## What pilot stakeholders should evaluate

The questions clinical, safety, and investment reviewers tend to ask, and
where each one is answered in the system itself.

- **Emergency hard-stop is rule-driven, not LLM-driven.** Chest-pain and
  similar high-acuity scenarios short-circuit the flow before any model
  sees them, and the trace names the rule that fired. This is the bar a
  safety committee will set; it's already where we built.
- **Bounded agentic loop, not an open chatbot.** Non-emergency flows run
  a budgeted question loop with deterministic scoring and a stop reason
  in the trace. Predictable cost per session, predictable latency,
  predictable behavior on review.
- **Explainability per result.** Every `RESULT` ships extracted
  canonicals, the top specialty's rationale, why questioning stopped,
  and the risk reasons. There is no "the model said so" output to defend
  in a clinical review or an audit.
- **Locale coverage as a contract.** Five locales (TR/EN/DE/RU/AR with
  Arabic RTL), gated by a CI contract test that fails the build if any
  key drifts. Same gate exists for the dashboard. Material for any
  buyer with a multilingual catchment.
- **Auditability at the session level.** The admin event timeline
  replays every envelope and decision in order. Safety reviewers
  reproduce user-reported issues without redeploying anything; ops
  reviewers see exactly what the system decided and why.
- **Real health check.** `GET /health` is a live Supabase reachability
  probe, not a stubbed `200 OK`. The admin panel surfaces
  `INFO`/`OK`/`WARN`/`CRIT`. CI runs a periodic probe and pages on
  regression — covered under operational maturity below.

## Tech stack

- Backend: FastAPI, deterministic rules and orchestration, Supabase
  (Postgres), optional Redis for multi-instance rate limiting.
- Mobile: Expo (React Native), 5-locale i18n with Arabic RTL, NetInfo
  offline banner, send-summary / export-summary from result screen.
- Dashboard: Next.js, locale switcher, Tailwind + shadcn-aligned theme
  tokens, axe-core a11y matrix (light + dark).
- Observability: Prometheus `/metrics` + Grafana Cloud dashboard, Sentry
  with KVKK-safe Session Replay, structured JSON logs with `request_id`.
- Ops: GitHub Actions for guardrails, kaggle ingest, capability drift,
  health alerts, secret scan, supabase smoke, sentry smoke.

## What this is NOT

Pulled directly from
[README — What This Is Not](../README.md#what-this-is-not):

- Not a diagnosis engine.
- Not a doctor ranking platform.
- Not a black-box LLM chatbot.
- Not a treatment decision maker.

## Operational maturity

CI workflows currently in `.github/workflows/`:

- `backend-regression.yml` — full backend regression chain (parity with
  `backend/scripts/run_backend_regression.py`).
- `dashboard-quality.yml` + `dashboard-tests.yml` — TypeScript no-emit,
  ESLint, route checks, i18n contract.
- `dashboard-lighthouse.yml` — Lighthouse CI with budget assertions
  (4 public URLs × 3 runs).
- `mobile-tests.yml` + `mobile-eas-build.yml` — Jest, smoke contract,
  i18n contract, EAS build pipeline.
- `mobile-e2e.yml` — Maestro flows (continue-on-error if no device).
- `guardrail.yml` — guardrail check before tuning patches deploy;
  triggers rollback on failure.
- `kaggle-ingest.yml` — automation with diff report and
  golden-flow gate (skips on no-op).
- `capability-drift.yml` — catches drift between API contract and
  implementation.
- `health-alert.yml` — periodic `/health` probe.
- `sentry-smoke.yml` — weekly DSN smoke test.
- `supabase-db-smoke.yml` — DB reachability smoke.
- `secret-scan.yml` — secret scanning on every PR/push.
- `observability-sync.yml` — alerts-as-code sync.
- `fly-deploy.yml` — deploy gate with `/health` HTTP smoke.

Observability and safety nets:

- Prometheus `/metrics` with native Supabase counter and histogram
  (session 15).
- Grafana Cloud dashboard with 4 alerts plumbed in (session 11).
- Sentry breadcrumbs on mobile + KVKK-safe Session Replay
  policy ([`docs/SENTRY_REPLAY_POLICY.md`](SENTRY_REPLAY_POLICY.md)).
- Quarterly PII audit with a local scanner (session 14).
- `axe-core` accessibility audit blocks on serious / critical WCAG 2.1
  AA violations across light + dark themes (session 16).
- 23 e2e Playwright specs across `dashboard/e2e/localhost/` and
  `dashboard/e2e/staging/` (admin, sessions, status, public pages,
  auth, accessibility — count it: ten files, multiple specs each).
- Pytest-benchmark baseline for hot-path modules.
- Real-corpus regression climbed from 60.8% → 79.1% across sessions
  (CHANGELOG 4.6.0 + session 8).

See also [`docs/RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) for the
release-time gate sequence.

## Repo / contact

- Repo: _(link to be filled in by author for the public landing)_
- Author: Emir (`emirgergin21@gmail.com`)
- Status: production-oriented MVP, pilot-ready, safety-review
  friendly. See [README — Status](../README.md#status).
