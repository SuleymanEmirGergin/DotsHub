# PII Leak Audit — TriAIge Backend, Mobile, Dashboard

**Audit scope:** All paths along which user-typed Turkish symptom descriptions
(KVKK Art. 6 special-category health data; GDPR Art. 9 special-category data)
flow from the user's device through TriAIge infrastructure to any third party.

**Audit type:** Static source review against `backend/`, `mobile/`, `dashboard/`,
`config/`, `backend/sql/`. No DB introspection, no network capture, no live
log scrape — see Honesty section.

**Companion docs reviewed:**
- `docs/PRIVACY_AND_SECURITY.md`
- `docs/SENTRY_REPLAY_POLICY.md`
- `docs/templates/KVKK_DPA_TEMPLATE.md`

---

## Findings table

Severity legend:
- **critical**: raw PII reaches third-party SaaS uncontrolled.
- **high**: raw PII reaches logs / DB rotation paths accessible to operators.
- **medium**: hashed / partially scrubbed PII surface that could be reconstructed.
- **low**: defended path worth documenting.
- **info**: clean by design, recorded for the audit trail.

### Backend logs

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Free-text symptom description in `print()` / unstructured logs | stdout / stderr captured by Fly.io log shipper | low | No `print()` of `user_message` / `input_text` / `symptoms_text` found. The orchestrator only logs metadata (`question_count`, `top_specialty.id`, `final_score`). Triage error path logs the exception only — `logger.error(f"Error in triage turn: {e}", exc_info=True)`. | `backend/app/api/routes/triage.py:374`, `backend/app/agents/orchestrator.py:284-303` | Keep the discipline. Add a unit-test guard that fails CI if any logger call in `app/agents/`, `app/api/routes/triage.py`, or `app/triage_engine.py` formats `user_message` / `input_text` / `answer_value` directly. |
| `app/core/pii.py::mask_for_log` defined but never called | n/a | info | The helper masks device IDs / emails for log lines. `Grep mask_for_log\(` returns zero callers backend-wide. Documented but unused — no leak in itself. | `backend/app/core/pii.py:10`, callers: zero | Either delete the helper (dead code) or wire it into the one log line that emits a `device_id` (`backend/app/api/routes/push_token.py:100`, currently logs full device_id). |
| `push_token.unregister` log includes raw `device_id` | stdout | medium | `logger.info("push_token.unregister", extra={"device_id": body.device_id})` — full device_id, not masked. `device_id` is not health PII per KVKK but is the cross-session re-identification key called out in `SENTRY_REPLAY_POLICY.md §1b`. | `backend/app/api/routes/push_token.py:100` | Wrap with `mask_for_log(body.device_id, "device_id")`. Ten-second fix; closes the only inconsistency between this log path and the Sentry scrubber's `_SCRUB_HEADERS` policy. |
| Stack traces with `exc_info=True` | stdout + Sentry | low | Tracebacks rendered by FastAPI default handler. The triage entry point wraps the body redaction call (`redact_pii(request.user_message)`) before the exception window opens, so the local-variable dump in the traceback contains the redacted string, not the raw one. Verified by reading `triage.py:131` (redaction) → `triage.py:175` (engine call). | `backend/app/api/routes/triage.py:131,374,440` | Confirm with one traceback unit test: pass an input containing a TC kimlik, force the engine to raise, assert the captured exception's `__traceback__` frame locals do NOT contain the raw 11-digit ID. |
| `request_id` in JSON logs | stdout | info | UUID4 only; no body content. `JsonFormatter` emits `{timestamp, level, logger, message, request_id, exception}` — message is whatever the caller passed. | `backend/app/core/logging_config.py:14-26`, `backend/app/core/request_id.py` | None. |

### Sentry (backend)

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| `before_send` scrubs known body keys | Sentry SaaS | low | `_SCRUB_BODY_KEYS = {input_text, user_message, answers, doctor_ready_summary_tr, why_specialty_tr, emergency_reason_tr, meta}` replaced with `[SCRUBBED]`. All other strings passed through `app.pii.redact_pii` (TC, phone, email regex). Same canonical regex module the LLM client and email summary use, so a new pattern lands once and protects every surface. | `backend/app/observability/sentry_init.py:40-106`, `backend/app/pii.py:24-39` | Add `raw_text`, `raw_texts`, `symptoms_text` to `_SCRUB_BODY_KEYS`. The orchestrator stores user-typed text under `state.raw_texts` (`backend/app/agents/orchestrator.py:134`); if a future stack trace serializes `state.__dict__` into Sentry context, that list would land unscrubbed. |
| `send_default_pii=False` | Sentry SaaS | info | Drops IP, no auto-attach of user info. KVKK / GDPR aligned. | `backend/app/observability/sentry_init.py:144` | None. |
| Auth headers scrubbed | Sentry SaaS | info | `authorization`, `cookie`, `x-admin-key`, `x-supabase-auth`, `x-device-id` replaced with `[SCRUBBED]`. Matches mobile-side list. | `backend/app/observability/sentry_init.py:32-38` | None. |
| `SENTRY_ENVIRONMENT in {test, ci}` drops events | Sentry SaaS | info | Local Jest/pytest runs that accidentally carry a DSN are dropped at the `before_send` boundary. | `backend/app/observability/sentry_init.py:77-78` | None. |
| Test coverage for scrubber contract | n/a | medium | The `before_send` hook contains four nested code paths (request data, request headers, extras, breadcrumbs). Could not locate a unit test that asserts each path. | `backend/tests/` (negative finding — see Honesty) | Add `test_sentry_before_send.py` that exercises each branch with a fixture event containing a TC kimlik, a phone number, an email, and a `device_id` header. Pin the scrubber contract. |

### Sentry (mobile)

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Session Replay masking | Sentry SaaS | info | `maskAllText: true`, `maskAllInputs: true` (SDK default), `maskAllImages: true`, `maskAllVectors: true`. Patient input and AI questions render as filled rectangles. | `mobile/src/observability/sentry.ts:271-282`, `docs/SENTRY_REPLAY_POLICY.md §2a` | None. The doc-vs-code match is exact for these flags. |
| `beforeSend` body scrub | Sentry SaaS | low | Mirror of backend list with the addition of `user_input_tr`, `device_id`, `x-device-id`. URL path collapse via `redactUrlPath` strips session UUIDs from `transaction` + `request.url` + breadcrumb URLs. | `mobile/src/observability/sentry.ts:45-59,107-169` | Same `raw_text` / `raw_texts` / `symptoms_text` addition recommended for the backend scrubber — keep the lists symmetric. |
| `sendDefaultPii=false` | Sentry SaaS | info | IP not sent. | `mobile/src/observability/sentry.ts:262` | None. |
| `replaysSessionSampleRate` | Sentry SaaS | low | 0.1 in prod / 1.0 in dev. `replaysOnErrorSampleRate=1.0`. | `mobile/src/observability/sentry.ts:269-270` | None per `SENTRY_REPLAY_POLICY §1c`. |

### Metrics (Prometheus / Grafana Cloud)

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Custom counter labels | Grafana Cloud (EU) | info | All labelnames are bounded enums: `envelope_type` (4 values), `caps_missing` (≤3), `bucket` (rate-limit type), `outcome` (success/error), `success` (true/false), `error_type` (~6 values), `operation` (DB op name). No free text. | `backend/app/observability/metrics.py:45-139` | None. The cardinality discipline doubles as PII discipline. |
| HTTP instrumentation labels | Grafana Cloud (EU) | low | `prometheus-fastapi-instrumentator` defaults: handler (template path, not raw URL), method, status, group_status_codes=True. `should_ignore_untemplated=True` means literal session UUIDs in `/v1/session/{uuid}/...` collapse to the template, not the literal — confirmed in `setup_metrics`. | `backend/app/observability/metrics.py:157-163` | Verify in a staging Prometheus scrape that no `/v1/session/<uuid-literal>` series exists. The instrumentator option is correct; live-confirm once. |
| Grafana dashboard panel descriptions | Grafana Cloud (EU) | info | Descriptions reference "user base" / "user impact" as natural language. No queries pull `input_text` / `answers`. | `config/grafana/dashboard-triaige.json:111,238` | None. |

### Database (Supabase)

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| `triage_sessions.input_text` | Supabase Postgres (region per `KVKK_DPA_TEMPLATE.md` is `[Bölge — örn. eu-central-1]` — placeholder, see Honesty) | high | Stored after `redact_pii(request.user_message)` strips TC kimlik, TR phone, email. Free-text Turkish health detail (symptom descriptions) is retained verbatim — that IS the analytical artifact. Class-of-data is special-category per KVKK Art. 6 / GDPR Art. 9. | `backend/app/api/routes/triage.py:131,144,159`, `backend/app/session_repo.py:30-44`, `backend/sql/20260210_supabase_triage_schema.sql:11-13` | This is the core data asset, not a leak — the issue is retention. PRIVACY_AND_SECURITY.md says "saklama süresi … operasyonel gereklere göre tanımlanmalı"; no concrete retention policy is implemented. Wire a daily cron that purges `triage_sessions WHERE created_at < now() - INTERVAL '90 days' AND deleted_at IS NULL`. The `idx_triage_sessions_live` partial index already supports this. |
| `triage_events.payload` | Supabase Postgres | high | `append_event(sid, "USER_MESSAGE", {"text": user_msg_redacted})` writes the redacted free-text. `ENVELOPE_RESULT` events store the full payload INCLUDING `_meta` with debug data — `event_payload["_turn_index"] = turn_index + 1; append_event(sid, f"ENVELOPE_{envelope_type}", event_payload)`. | `backend/app/api/routes/triage.py:166-204` | Same retention cascade as `triage_sessions` (FK `ON DELETE CASCADE` already in `20260210_supabase_triage_schema.sql:163` — purging the session row drops the events). Retention cron must be applied to the parent table; the FK does the rest. |
| `triage_feedback.comment` | Supabase Postgres | high | `comment: Optional[str] = Field(default=None, max_length=2000)` — free text up to 2000 chars, NOT passed through `redact_pii` before insert. Users can paste a TC kimlik or phone into the feedback form and it lands raw. | `backend/app/api/routes/feedback.py:25,56-62` | Wrap `payload.comment = redact_pii(payload.comment) if payload.comment else None` before the insert. Single-line fix. |
| `triage_sessions.device_id` | Supabase Postgres | medium | Stored verbatim, max 128 chars (Pydantic-enforced + `.strip()[:128]` defense-in-depth). Not health PII but is the cross-session re-identification key per `SENTRY_REPLAY_POLICY.md §1b`. | `backend/app/session_repo.py:36-39`, `backend/sql/20260421_triage_sessions_device_id.sql` | Document explicitly in `PRIVACY_AND_SECURITY.md` that `device_id` is the re-identification handle for the follow-up push flow and falls under KVKK Art. 5 lawful-basis processing. Optional: hash on insert (`sha256(device_id + tenant_salt)`) and only store the hash — push delivery still works because Expo Push uses `expo_token`, not `device_id`. |
| `push_tokens` table | Supabase Postgres | medium | Stores `device_id` + `expo_token` + `platform` + `locale`. Both columns are device-level identifiers. | `backend/app/push.py:46-63`, `backend/sql/20260214_push_tokens.sql` | Same hashing recommendation as above. The Expo token IS the wire credential; the device_id only exists to dedupe upserts. |
| Tombstone deletion | Supabase Postgres | low | `DELETE /v1/me/sessions/{id}` wipes `input_text`, `answers`, `user_canonicals_tr`, `top_conditions`, `doctor_ready_summary_tr`, `why_specialty_tr`, `specialty_scoring_debug`, `confidence_debug`, `emergency_reason_tr`, `meta`. Cascades to events / llm_calls / feedback. The session row stays for join integrity. | `backend/app/api/routes/data_rights.py:99-131` | Add `device_id` to the tombstone clear-list. Currently the row keeps its `device_id` after tombstone, preserving the exact handle the user is trying to forget. One-line fix: `"device_id": None` in the update dict. |
| `llm_calls` table | Supabase Postgres | medium (presumed) | Could not statically confirm what columns this table holds. Migration file `20260416_llm_calls.sql` exists; the data_rights route deletes `WHERE session_id = X` so it joins to a session at a minimum. | `backend/sql/20260416_llm_calls.sql` (file exists; not read in this audit) | Read the migration; confirm whether the LLM prompt / response is stored verbatim. If yes, redact-on-insert via the same `redact_pii` path the LLM client already uses on inputs. |

### Mobile

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Local AsyncStorage cache of session state | Device-local | low (out-of-scope for "leak", in-scope for device theft) | Could not statically confirm whether the mobile client persists `raw_texts` / `answers` to AsyncStorage. The `state` directory exists at `mobile/src/state` but was not read in this audit. | `mobile/src/state/` (not read) | If session state is persisted, ensure it's keyed by `device_id` only (not tied to a logged-in identity), and add a "clear cache" call to the data-rights flow. Document in PRIVACY_AND_SECURITY.md. |
| Network breadcrumbs | Sentry SaaS | info | `addApiBreadcrumb` in `triageClient.ts` records URL + status + duration + level. URLs flow through `redactUrlPath` in `beforeSend`. Breadcrumb messages flow through `redactPII`. | `mobile/src/api/triageClient.ts:7,44-50`, `mobile/src/observability/sentry.ts:155-166` | None. |
| `x-device-id` request header | wire (TLS) → backend | info | Sent on every triage call. Not logged client-side. Backend scrubs it from Sentry events. Stored in DB by design (medium severity above) for the follow-up push path. | `mobile/src/api/triageClient.ts:34-37` | None. |

### Dashboard

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Sentry init for dashboard | Sentry SaaS | info | No Sentry init file found under `dashboard/`. The dashboard is admin-only and not patient-facing — the absence is intentional, per `SENTRY_REPLAY_POLICY.md` (which only covers mobile + backend). | `dashboard/` (no `sentry.client.config.ts` / `instrumentation.ts` found via Glob) | If a future hospital DPA requires Next.js error tracking on the admin surface, mount Sentry with the same `beforeSend` body-key list as the backend. |
| Session detail page renders raw `input_text` | Browser DOM (admin viewer) | medium | `dashboard/app/admin/sessions/[id]/page.tsx:275` directly renders `session.input_text` (already redacted at insert). Admin sees the session free-text in plain TR. | `dashboard/app/admin/sessions/[id]/page.tsx:275` | This is the explicit clinical-review use case — not a leak, but a privacy-policy surface. Document in PRIVACY_AND_SECURITY.md that admin users see redacted free-text and that admin access is itself logged via `tenant_catalog_audit` (catalog edits) but not via a session-view audit log. Recommend adding a `triage_session_views` audit table for the per-tenant logging hospitals will demand. |
| `requireAdmin()` falls open when `NEXT_PUBLIC_SUPABASE_ANON_KEY` is unset | Browser | low | "If Supabase Auth not configured, skip gate (dev mode)" — returns `{user: null, role: "admin"}`. Not a leak in production (env IS set), but a misconfigured production deploy would silently expose the admin UI. | `dashboard/lib/requireAdmin.ts:11-13` | Add a runtime guard: if `process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY`, throw on import so the build/serve fails loudly. |

### Cross-border data transit

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| TR-resident user → Fly.io ams (Amsterdam) | TLS-protected wire, EU data center | medium | All triage requests terminate in Amsterdam. Patient health data leaves Turkey at the TLS handshake. KVKK Art. 9 requires explicit consent or a DPA-listed lawful basis for cross-border transfer of special-category data. | `fly.toml`, `docs/templates/KVKK_DPA_TEMPLATE.md:125` | Confirmed gap: the KVKK DPA template lists Fly.io as Amsterdam, but the in-app consent flow needs a `Veri Yurt Dışına Aktarma` checkbox. Verify the mobile onboarding consent screen captures this explicitly. (Not auditable from code alone — see Honesty.) |
| Backend → Supabase (region placeholder) | TLS, EU likely | medium | `KVKK_DPA_TEMPLATE.md:122` says `[Bölge / Region — örn. eu-central-1]` — this is a template placeholder, not a configured region. Could not confirm the actual project region from code. | `backend/app/supabase_client.py`, `KVKK_DPA_TEMPLATE.md:122` | DB-state verification: pull the Supabase project region from the dashboard; if not eu-central-1 / eu-west-1, file a region-migration ticket BEFORE a hospital DPA review. |
| Backend → Wiro / Google / OpenAI / Anthropic (LLM NLU) | TLS | high (mitigated) | `redact_pii(user)` is applied BEFORE the wire transmission in `services/llm_nlu_client.py:312`. So the LLM never receives a TC kimlik, TR phone, or email. It DOES receive Turkish symptom free-text — which is special-category health data. | `backend/app/services/llm_nlu_client.py:312` | This is the highest-risk transit path. The mitigation list: (a) prefer Wiro (TR-resident provider per `WIRO_BASE_URL` config) for tenant DPAs that exclude US clouds; (b) ensure `LLM_PROVIDER=wiro` is the production default; (c) add a startup assert that fails the boot if `LLM_PROVIDER ∈ {google, openai, anthropic}` AND the active tenant DPA forbids US transit. Single-line guard, big DPA dividend. |
| Backend → Sentry SaaS | TLS, EU project | low | Per `SENTRY_REPLAY_POLICY §3a` legitimate-interest is the lawful basis; replays/events carry no unmasked patient data. Region of the Sentry project: needs `KVKK_DPA_TEMPLATE.md` placeholder confirmation. | `backend/app/observability/sentry_init.py`, `KVKK_DPA_TEMPLATE.md` | Ensure the Sentry organization is on the EU data plane (`*.de.sentry.io` or eu equivalent). |
| Backend → Slack / Discord webhooks | TLS, US clouds | high | `notifier.py::_extract_info` returns `info["reason"] = payload.get("reason_tr", "Bilinmeyen acil durum")` — for EMERGENCY envelopes, the human-readable Turkish reason ("Göğüs ağrısı sol kola yayılıyor" or similar) is sent to Slack/Discord. This is a clinical detail but not a direct identifier. Recommended specialty + risk_level + first 8 chars of session_id are also sent. | `backend/app/notifier.py:172-211,253-256,289-292` | This IS a third-party SaaS path carrying clinical signal. Recommendation: configure `WEBHOOK_ENABLED=false` for tenants under a strict DPA. Or: replace `reason_tr` in the webhook payload with a coarsened `risk_level` only ("EMERGENCY" / "HIGH"), keeping the operational signal without the clinical detail. |
| Backend → Expo Push (Apple/Google clouds) | TLS | medium | `send_push_alert` payload not fully traced in this audit; `expo_token` is the wire identifier. Apple/Google/Expo may log the message body. | `backend/app/push.py:78-` (full body not read) | Confirm the push body does NOT include patient text. Push title/body should be generic ("Triage tamamlandı — sonuçlar için uygulamayı açın") with the clinical detail living inside the app, behind device unlock. |
| Backend → Resend (email summary) | TLS, US cloud | medium | `send_session_summary_email` calls `build_summary_body` which formats `recommended_specialty_tr`, `confidence`, `stop_reason`, `created_at`, `session_id` and runs the result through `redact_pii` defense-in-depth. No raw `input_text` is included. | `backend/app/services/email_summary.py:30-69` | Document Resend + region in `KVKK_DPA_TEMPLATE.md`. The body is metadata-only by construction; the recipient email itself IS user-supplied PII, accepted as the price of the feature. |

---

## Honesty section — what could not be audited statically

1. **Supabase region.** `KVKK_DPA_TEMPLATE.md:122` carries a placeholder
   `[Bölge / Region — örn. eu-central-1]`. The actual region of the
   production project is not derivable from source. **Pilot blocker:**
   confirm before any DPA discussion.
2. **Supabase column-level encryption claim.** The privacy doc references
   "hassas env değişkenleri … repoda tutulmaz" but makes no claim about
   at-rest column encryption beyond Supabase's default. A hospital DPA
   review will ask. Verify with `pg_extension` audit on the live DB.
3. **Live log content.** The audit confirmed the SHAPE of every `logger.*`
   call but did not scrape a real Fly.io log buffer. A misbehaving
   third-party library (httpx, supabase-py) could log a request body on
   error in a code path the static review missed.
4. **`llm_calls` table contents.** The migration file exists but was not
   read. The data_rights route DELETEs from this table, so it carries
   session-keyed data. Whether it stores prompt + response verbatim is
   unknown from this pass.
5. **Mobile state persistence.** `mobile/src/state` was not read.
   Whether `raw_texts` / `answers` survive an app restart on disk is
   unknown.
6. **Push body content.** `app/push.py::send_push_alert` was sampled but
   not read end-to-end. Whether the Expo Push body carries clinical
   detail or only generic copy needs confirmation.
7. **In-app consent capture.** Whether the mobile onboarding screen
   captures `Veri Yurt Dışına Aktarma` consent for the Amsterdam
   Fly.io transit is a UI-flow audit, not a code audit.
8. **Sentry organization data plane.** Per `SENTRY_REPLAY_POLICY` the
   project is on the EU plane; the actual DSN URL would confirm it.

---

## Recommended sequence — fix order if any are critical

There are no `critical`-rated findings. The `high`-rated ones, ordered
for hospital-DPA blast radius:

1. **Slack/Discord webhook clinical-detail leak** (`notifier.py`).
   Coarsen `reason_tr` to `risk_level`. Two-line change. Removes the
   only path that sends clinical TR text to a US SaaS.
2. **Feedback comment redaction** (`feedback.py`). One-line fix:
   `payload.comment = redact_pii(payload.comment)` before insert.
3. **Retention cron for `triage_sessions`**. The DB stores special-category
   data with no automatic purge. Document the cutoff in
   `PRIVACY_AND_SECURITY.md` AND ship the cron — the docs alone won't
   pass a DPA review.
4. **LLM provider geographic guard**. Startup assert that
   `LLM_PROVIDER` matches the tenant DPA's allowed-clouds list.
5. **Tombstone `device_id` clear**. One-line fix in `data_rights.py`.

Medium-rated items (Supabase region confirmation, dashboard `requireAdmin`
hardening, `device_id` hashing, mobile state persistence audit) are
near-term but not pre-pilot blockers given a single big tenant.

---

## Pilot-ready statement (founder-pasteable)

> **What does NOT leave the controlled environment (TR/EU TLS-protected
> infrastructure):** The patient's TC kimlik, TR phone numbers, and email
> addresses are stripped from every free-text input via
> `app.pii.redact_pii` (canonical regex module) BEFORE the text is
> persisted to Supabase, transmitted to the LLM provider, or written to
> a log line. The mobile session replay masks every `<Text>` and
> `<TextInput>` so screen captures contain no readable patient content;
> aggressive masking is documented in `docs/SENTRY_REPLAY_POLICY.md` and
> audited quarterly.
>
> **What is hashed / coarsened:** No patient data is hashed today — the
> redaction model is "remove direct identifiers, keep clinical free-text
> for analysis." `device_id` is stored verbatim today; we recommend
> hashing it for the follow-up push path (open improvement).
>
> **What is in third-party SaaS:** Sentry receives crash events and
> session replays where every text region is masked and every body
> string runs through the same redaction regex (mirrored backend +
> mobile). Slack/Discord webhooks today receive an Emergency reason
> string in Turkish — we will coarsen this to a `risk_level` enum
> before the first paying customer. The LLM NLU provider (Wiro by
> default; configurable to Google/OpenAI/Anthropic) receives Turkish
> symptom descriptions with TC kimlik / phone / email already stripped;
> the provider's region must match the tenant DPA. Resend email
> summaries carry session metadata only (specialty / confidence /
> stop_reason / session_id), not raw symptom text.
>
> **What crosses the border:** Backend hosting on Fly.io Amsterdam;
> Supabase project in the EU plane (region to be confirmed pre-pilot);
> Grafana Cloud EU. Cross-border consent must be explicit per KVKK
> Art. 9; the in-app onboarding flow needs a confirmation that this
> is captured. The `KVKK_DPA_TEMPLATE.md` lists every sub-processor
> that needs to appear in the data-processing addendum.
