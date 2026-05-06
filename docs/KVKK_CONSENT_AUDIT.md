# KVKK Per-Clause Consent Audit

This doc explains how TriAIge records the user's consent intent for KVKK
purposes — what we collect, where it lives, how long, and how an auditor
can demonstrate that a given user accepted a given clause at a given
point in time.

## Why three clauses, not one

The KVKK Article 6 ("Özel nitelikli kişisel verilerin işlenmesi") rule
for health data requires *açık rıza* — explicit, specific consent for
the processing activity. A blanket "I accept" at app launch does not
satisfy this. The mobile onboarding screen now surfaces three
independent acknowledgments:

| `clause_id` | Mobile copy (TR) | Legal basis |
|---|---|---|
| `terms` | "Kullanım koşullarını okudum ve kabul ediyorum." | Contract / general terms acceptance |
| `kvkk`  | "Anonim sağlık verilerimin işlenmesine açık rıza veriyorum." | KVKK Art. 6 / 5(2)(c) explicit consent for special-category data |
| `age`   | "13 yaşından büyüğüm." | KVKK + COPPA-equivalent age gate |

The Başla CTA stays disabled until all three are checked.

## What gets recorded

Every checkbox toggle (tick OR un-tick) on the IntroScreen fires
`POST /v1/consent/event` with:

```json
{
  "clause_id": "kvkk",
  "accepted": true,
  "notice_version": "2026-05-01",
  "consent_version": "1.0"
}
```

with header `X-Device-Id: <anonymous-uuid>`.

The server writes one row per call to `public.consent_events`:

| column | source | notes |
|---|---|---|
| `id` | bigserial | row id, used in logs |
| `device_id` | `X-Device-Id` header | anonymous, provisioned by mobile/utils/deviceId.ts |
| `clause_id` | request body | CHECK-constrained to `terms`/`kvkk`/`age` |
| `accepted` | request body | true on tick, false on un-tick |
| `notice_version` | request body | snapshot of `EXPO_PUBLIC_NOTICE_VERSION` |
| `consent_version` | request body | snapshot of `EXPO_PUBLIC_CONSENT_VERSION` |
| `user_agent` | NULL by default | optional; flip a privacy-team feature flag to populate |
| `ip_hash` | NULL by default | optional; same gate |
| `created_at` | server-side `now()` | UTC |

Indexes are tuned for the auditor's two main read patterns:

- **Latest state per device per clause** — the
  `(device_id, clause_id, created_at desc)` covering index lets `LIMIT 1`
  resolve the question "did device X currently have clause Y accepted?"
  without a sort.
- **All events for a single device** — the `device_id` index supports the
  right-to-be-forgotten tombstoning path (see `data_rights.py`).

## Why we record un-ticks

A user who ticks KVKK, considers it for two minutes, un-ticks it, then
re-ticks before pressing Başla has a meaningful audit trail: they
considered the clause and made a deliberate decision. Batching only the
final state at "Başla" would lose that signal — and KVKK auditors
explicitly value the *deliberation*, not just the outcome.

The latest row per `(device_id, clause_id)` is always the *effective*
state. The full sequence is the *audit trail*.

## Right-to-be-forgotten

`DELETE /v1/me/sessions/{session_id}` (legacy endpoint, see
`backend/app/api/routes/data_rights.py`) tombstones triage-related data
but does NOT currently touch `consent_events`.

That is intentional: the audit trail is what proves we *had* permission
to process the data we're now deleting, so erasing the audit record on
the same call would defeat the purpose. The retention policy for
`consent_events` is therefore decoupled from session retention:

- **Sessions** (`triage_sessions`) — auto-tombstoned at 90 days; full
  delete on user request.
- **Consent events** (`consent_events`) — retained for **5 years**
  to align with KVKK's typical legal-claim retention window. After 5
  years a separate periodic job will tombstone rows.

The 5-year retention window is configurable via env (see Privacy team
runbook); 5 years is the conservative default.

## Endpoint at a glance

```
POST /v1/consent/event
Headers:
  X-Device-Id: <required, anonymous device uuid>
Body:
  {
    "clause_id":       "terms" | "kvkk" | "age",   // server-validated
    "accepted":        true | false,
    "notice_version":  "<NOTICE_VERSION>",          // ≤64 chars
    "consent_version": "<CONSENT_VERSION>"          // ≤32 chars
  }
Responses:
  201 { "ok": true, "id": <bigserial> }       // recorded
  400 missing_device_id                       // header absent
  422 (Pydantic)                              // unknown clause_id
  503 audit_log_unavailable                   // Supabase outage
```

The route is write-only. Auditors query the table directly via
service-role Supabase access; we do not expose a read endpoint here
because reading consent records belongs to a different (auditor) role,
not the running mobile client.

## Mobile follow-up

- `mobile/src/screens/IntroScreen.tsx` currently records the three-state
  consent only in the in-memory Zustand store. The follow-up commit
  adds a fire-and-forget `POST /v1/consent/event` call inside the
  checkbox tap handler.
- An offline buffer (`AsyncStorage`-backed queue, drained on
  reconnection) keeps the per-toggle promise even when the user is
  air-gapped during onboarding. That's a separate mobile commit.

## Operator action items

1. Apply migration `backend/sql/20260506_consent_events.sql` to the
   Supabase project before this service version ships.
2. Confirm the `consent_events` table is excluded from any
   nightly-export pipelines that already redact PII for analytics —
   the audit trail is not analytics data.
3. Document the 5-year retention window in the public privacy notice
   alongside the existing 90-day session retention.
4. Wire a Sentry/Slack alert when `audit_log_unavailable` is returned
   more than N times in a window — silent KVKK-audit gaps are a
   compliance incident.
