# Multi-Tenant Review — TriAIge

**Audit scope:** Whether the existing `dashboard/app/admin/tenants/` UI,
`backend/app/admin_tenants_api.py`, and the per-tenant
`curated_conditions.<id>.json` flow constitute a pilot-ready multi-tenant
boundary for an Acıbadem-class hospital customer who will demand data
isolation from any other tenant.

**Audit type:** Static source review against `backend/`, `dashboard/`,
`backend/sql/`, `backend/app/data/`. Live RLS policies and Supabase
schema state were not introspected — see Honesty section.

---

## Current state diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TENANT SCOPE — what is and isn't isolated today                            │
└─────────────────────────────────────────────────────────────────────────────┘

CONFIG PLANE (curated_conditions catalog)        DATA PLANE (sessions/events/feedback)
─────────────────────────────────────────        ──────────────────────────────────────

   ┌──────────────────────┐                       ┌────────────────────────┐
   │ admin UI             │                       │ patient mobile app     │
   │ /admin/tenants/<id>  │                       │ POST /v1/triage/turn   │
   └────────────┬─────────┘                       └────────────┬───────────┘
                │ x-admin-key (global)                         │ device_id
                ▼                                              ▼
   ┌──────────────────────┐                       ┌────────────────────────┐
   │ FastAPI              │                       │ FastAPI                │
   │ /v1/admin/tenants/*  │                       │ /v1/triage/turn        │
   │ admin_tenants_api.py │                       │ triage.py              │
   └────────────┬─────────┘                       └────────────┬───────────┘
                │                                              │
                │ tenant_id in URL                             │ NO tenant_id
                ▼                                              ▼
   ┌──────────────────────┐                       ┌────────────────────────┐
   │ filesystem:          │                       │ Supabase:              │
   │ data/curated_        │                       │ triage_sessions        │
   │  conditions          │                       │ triage_events          │
   │  .<tenant>.json      │                       │ triage_feedback        │
   └──────────────────────┘                       │   (no tenant_id col)   │
              ▲                                   └────────────┬───────────┘
              │                                                │
   ┌──────────┴───────────┐                       ┌────────────┴───────────┐
   │ runtime.py           │                       │ admin dashboard        │
   │ load_runtime(        │                       │ /admin/sessions        │
   │   tenant_id="default"│  ◀── HARDCODED ────   │ shows ALL sessions     │
   │ )                    │      "default"        │ (no tenant filter)     │
   └──────────────────────┘                       └────────────────────────┘

   ✅ tenant_id flows through the                ❌ tenant_id never reaches
      catalog admin API end-to-end.                 the data plane. Sessions
      Validation regex [a-z0-9_-]{1,32}.            are tenant-blind.
```

**One-line summary:** TriAIge has tenant-scoped CONFIG today
(curated catalogs + audit log of who edited which catalog) and is
fully tenant-blind on the DATA plane (sessions, events, feedback,
admin views). The repo carries the right tenant infrastructure for
the right-most wing of the diagram (dashboard editor + audit table)
but the patient-facing triage path never asks "which tenant is this
session for?"

---

## Findings

### Data plane isolation

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| `triage_sessions` table has no `tenant_id` column | Supabase schema | red | Schema definition has 30+ columns covering envelope, confidence, debug, urgency, device_id — but no `tenant_id`. `Grep "tenant_id"` over `backend/sql/` matches only `tenant_catalog_audit.sql`. | `backend/sql/20260210_supabase_triage_schema.sql:8-35` | Migration: `ALTER TABLE public.triage_sessions ADD COLUMN tenant_id text NOT NULL DEFAULT 'default'`. Backfill existing rows to `'default'`. Add an index. **Pilot blocker.** |
| `session_repo.create_session()` does not accept tenant_id | Backend API | red | Function signature: `create_session(locale, input_text, device_id=None) → UUID`. The row dict it inserts has no `tenant_id` key. `Grep "tenant_id"` over `backend/app/session_repo.py`: zero hits. | `backend/app/session_repo.py:16-44` | Add `tenant_id: str` parameter (default to `"default"` for back-compat). Inject from the request handler. Pair with the schema migration above. |
| `triage.py` does not extract `tenant_id` from the request | Backend API | red | The handler reads `device_id`, `locale`, `lat`, `lon`, `user_message`, `answer` — never a tenant identifier. There is no `x-tenant-id` header read. | `backend/app/api/routes/triage.py:112-253` | Add an `x-tenant-id` header (or `tenant_id` body field) to `TriageTurnRequest`. Default `"default"` if absent. Pass through to `create_session`. The mobile client knows which hospital app it is — that's where the value comes from. |
| Mobile client never sends a tenant identifier | Mobile API | red | `triageClient.ts` builds the request from `req` + `device_id` + `lat`/`lon`. No tenant header. There is no `EXPO_PUBLIC_TENANT_ID` configuration variable surfaced. | `mobile/src/api/triageClient.ts:9-41` | Add `EXPO_PUBLIC_TENANT_ID` to `app.config.ts` extras and read it in `triageClient`. EAS profile per tenant, or runtime detection from a per-tenant deeplink scheme — both work. |
| `runtime.py::load_runtime` is called with `tenant_id="default"` everywhere | Backend startup | red | The signature accepts a `tenant_id` argument (good design), but `triage.py:122` calls `load_runtime()` with no argument, which falls through to the `"default"` default. The runtime is then cached in `_RUNTIME` for the process lifetime — so one runtime serves all tenants regardless of any future tenant header. | `backend/app/runtime.py:189`, `backend/app/api/routes/triage.py:121-124` | Cache runtimes per-tenant: `_RUNTIME_BY_TENANT: Dict[str, Runtime] = {}`. Look up by header on each request. Memory cost is bounded by tenant count; for ten tenants this is trivial. |
| Admin dashboard `/admin/sessions` lists all sessions globally | Dashboard | red | `supabaseAdmin().from("triage_sessions").select(...)` with no `.eq("tenant_id", ...)` filter. An admin authenticated against tenant A would see tenant B sessions if both tenants share a Supabase project. | `dashboard/app/admin/sessions/page.tsx:83-89` | Once `tenant_id` exists on the row, filter by the calling admin's tenant scope. Today every authenticated admin sees the global firehose — this is incompatible with hospital data isolation expectations. |
| Aggregate metrics (Grafana) are global, not per-tenant | Prometheus metrics | yellow | All `Counter`/`Histogram` instances use `envelope_type` / `caps_missing` / `bucket` / `outcome` / `operation` labels. No `tenant_id` label. Per-tenant dashboards are not possible from current metrics. | `backend/app/observability/metrics.py:45-139` | Add `tenant_id` as a label to the high-value counters (`triage_envelope_total`, `confidence_score`, `rate_limit_hits_total`). Cardinality-bound by your tenant count, which is small. Update Grafana dashboard to show per-tenant overlays + a global aggregate. |

### Auth boundary

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Admin auth via static `x-admin-key` header | Backend API | yellow | `require_admin_key` checks one global `ADMIN_API_KEY` env var. Same key for every tenant. No claim of tenant scope on the validated identity. | `backend/app/admin_auth.py:10-18`, `backend/app/admin_tenants_api.py:52-53` | Acceptable for single-tenant pilot; replace with per-tenant keys (`ADMIN_API_KEY_<tenant_id>`) or move to JWT-with-tenant-claim before tenant #2. |
| `admin_users` table has no tenant_id column | Supabase schema | red | Schema: `id, user_id, email, role, created_at`. No tenant association. The RLS policy is "user can read its own row," nothing about tenant scope. | `backend/sql/20260214_admin_users.sql:7-13`, `backend/sql/20260419_admin_users_rls.sql:22-26` | Add `tenant_id` column (NOT NULL, FK to a future `tenants` table). Update the RLS policy and `requireAdmin()` to attach the tenant scope to the returned `{user, role}` object. |
| `requireAdmin()` returns `{user, role}` without tenant context | Dashboard | red | The function reads `admin_users.role` only. Downstream code has no way to know which tenant the admin belongs to. | `dashboard/lib/requireAdmin.ts:24-30` | Once the schema has `tenant_id`, change the select to `select("role, tenant_id")` and return `{user, role, tenantId}`. Every admin page then filters its Supabase query by `.eq("tenant_id", tenantId)`. |
| Cross-tenant leak in admin views | Dashboard | red | Today an admin from tenant A authenticated via Supabase Auth could read tenant B's session_id list — both because `triage_sessions.tenant_id` doesn't exist AND because `requireAdmin()` doesn't tenant-bind. The two gaps stack. | combination of above | Same fix: row-level `tenant_id` + admin-row `tenant_id` + RLS policy that joins them. |
| `super_admin` role | Schema | low | `chk_admin_users_role` allows `'admin'` and `'super_admin'`. The role is checked nowhere in the dashboard — `requireAdmin` only validates the row exists. | `backend/sql/20260214_admin_users.sql:18-26`, `dashboard/lib/requireAdmin.ts:22-30` | When tenant scoping lands, super_admin should be the cross-tenant role (TriAIge ops). Document the boundary in `OPS_ROTATION.md`. |

### Tenant lifecycle

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Tenant creation flow | Admin UI + API | green | `POST /v1/admin/tenants` validates `tenant_id` regex `[a-z0-9_-]{1,32}`, rejects `"default"`, supports `seed_from_default`, writes `curated_conditions.<id>.json` to filesystem, writes audit row. UI form proxies through `/api/admin/tenants` with the admin key kept server-side. | `backend/app/admin_tenants_api.py:316-367`, `dashboard/app/admin/tenants/CreateTenantForm.tsx:7-92`, `dashboard/app/api/admin/tenants/route.ts:9-40` | Solid. The tenant_id validation regex is filesystem-safe; the form uses HTML `pattern` for parallel client-side enforcement. |
| Tenant catalog edit | Admin UI + API | green | `PUT /v1/admin/tenants/{id}/curated` reads old doc → writes new doc → writes audit row with old/new for rollback. Audit is fire-and-forget per `_write_audit_row` (logs but does not block on failure). | `backend/app/admin_tenants_api.py:234-272`, `backend/sql/20260418_tenant_catalog_audit.sql` | Solid. The audit-row design ("pick a known-good row and re-apply new_doc") is the right rollback model. |
| Tenant deletion | Admin API | green | `DELETE /v1/admin/tenants/{id}` snapshots the catalog, unlinks the file, writes a `delete` audit row with `old_doc` set. Refuses to delete `"default"`. | `backend/app/admin_tenants_api.py:275-313` | Solid. Audit captures pre-delete state for forensics. |
| Filesystem-based catalog storage | Backend startup | yellow | Catalogs live in `backend/app/data/curated_conditions.<id>.json`. This means a catalog edit only takes effect for the Fly.io machine that received the PUT — other Fly.io VMs serve a stale catalog until restart. Same applies to multi-region. | `backend/app/admin_tenants_api.py:68-71`, `backend/app/runtime.py:339-360` | Acceptable for a single-region pilot (one Fly machine). Pre-second-tenant: move catalog storage to Supabase (`tenant_catalogs` table keyed by tenant_id, with `JSONB` body). The audit table's `new_doc` column proves this shape works. |
| Tenant scope normalization | Backend API | green | `put_tenant_catalog` overrides `payload_dict["tenant_scope"] = tenant_id` so the file's `tenant_scope` field always matches the URL — closes a class of typo bugs where the file claims to belong to tenant X but the filename says Y. | `backend/app/admin_tenants_api.py:248-249` | None. |
| `demo_hospital` example | Repo | green | `curated_conditions.demo_hospital.json` is a checked-in canary that overrides ONE label (`Panik Bozukluk`) with a `[DEMO TENANT]` prefix. The C1 multi-tenant test suite uses this to assert tenant lookup works. The disclaimer field clearly tags it as test-only. | `backend/app/data/curated_conditions.demo_hospital.json:1-31` | None — this is exactly the right shape for a CI canary. Keep checked in. |

### Configuration scope (per-tenant customizability)

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| `curated_conditions` overrides | Backend runtime | green | Per-tenant catalog overrides specific disease labels; missing labels fall through to default. Partial customization works. | `backend/app/runtime.py:336-360`, `backend/app/admin_tenants_api.py:1-23` (header doc) | Solid design. |
| Other config files (rules, stop_rules, synonyms, specialty_keywords, emergency_rules, risk_rules) | Backend runtime | yellow | All loaded once and shared across tenants. There is no path today to give tenant A a different `emergency_rules.json` or `stop_rules.json`. | `backend/app/runtime.py:206-234,275-327` | Acceptable for pilot — most clinical config should be uniform. If a tenant asks for a different stop threshold, extend the per-tenant pattern (`stop_rules.<tenant>.json`) using the same fallback structure already in place for curated. |
| Per-tenant disclaimer | Backend + UI | green | Each catalog carries a `disclaimer_tr` field; the tenant create form lets the admin set it; default applies if blank. | `backend/app/admin_tenants_api.py:155-159`, `dashboard/app/admin/tenants/CreateTenantForm.tsx:60-69` | Confirm the disclaimer is rendered in the patient-facing mobile app per active tenant. (Could not be confirmed without tracing the mobile RESULT renderer.) |
| Per-tenant branding (logo, colors, name) | Mobile + Dashboard | red (for white-label hospitals) | No per-tenant branding configuration found. The mobile app and admin dashboard are TriAIge-branded everywhere. | repo-wide | Acceptable if pilot tenant accepts TriAIge co-branding. White-label for Acıbadem-class deployments needs a per-tenant theme + logo flow. Defer; do not gold-plate. |
| Per-tenant locales | Backend + Mobile | yellow | Locale is set per-request (`tr-TR` / `en` / `de` / `ru` / `ar`) at the user level, not the tenant level. A tenant cannot disable a locale or restrict to TR-only. | `backend/app/api/routes/triage.py:131,155`, mobile i18n | Defer for pilot. Most hospitals will accept the patient-driven locale model. |
| Per-tenant rate limits | Backend | yellow | One global rate limit per bucket (`triage`, `feedback`, `send-summary`). No per-tenant cap. A noisy tenant could starve a quiet one. | `backend/app/rate_limit.py` (not deeply read in this audit) | Acceptable for one big pilot. Pre-multi-tenant: add tenant_id to the rate-limit bucket key. |

### Database schema isolation

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Foreign keys cascade per session, not per tenant | Schema | n/a | `triage_events.session_id → triage_sessions.id ON DELETE CASCADE`. `triage_feedback.session_id → triage_sessions.id ON DELETE CASCADE`. Once `tenant_id` lands on `triage_sessions`, joining out to `triage_events`/`triage_feedback` via `session_id` inherits the tenant scope transitively. | `backend/sql/20260210_supabase_triage_schema.sql:152-167,222-238` | Once tenant_id is on `triage_sessions`, add a denormalized `tenant_id` column to `triage_events` and `triage_feedback` ALSO — RLS joins on a single table are simpler than transitive tenant lookups. Backfill via trigger on session insert. |
| RLS policies | Schema | red | Only `admin_users` has an RLS policy. `triage_sessions`, `triage_events`, `triage_feedback`, `push_tokens`, `tuning_tasks`, `llm_calls` — RLS state was not introspected; the SQL files don't enable RLS on these. Default Supabase behavior for tables without RLS is "full access for any authenticated user" — fine for a service-role backend, dangerous if an anon client ever gets a foothold. | `backend/sql/*.sql` | Two-step: (a) explicitly `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` on every patient-data table; (b) write tenant-scoped policies tied to the admin's `tenant_id` claim. The dashboard authenticates via Supabase Auth so it can carry the tenant claim through; the backend uses service-role and bypasses RLS by design. |
| Table-level audit log | Schema | yellow | `tenant_catalog_audit` covers catalog writes only. There is no audit log for who viewed which session, who exported which CSV, who triggered the follow-up push flow. | `backend/sql/20260418_tenant_catalog_audit.sql` | Add `triage_session_views` (admin_user_id, session_id, viewed_at) and `triage_csv_exports` (admin_user_id, query_filters, exported_at) for the patient-data audit trail hospitals will demand. |

### Cross-tenant leak surfaces

| Path | Surface | Severity | Current state | Evidence (file:line) | Recommendation |
|---|---|---|---|---|---|
| Session created without tenant_id | Backend | red | Today every session is created without a tenant_id. There is no concept of "tenant A's view" yet — every admin sees every session. Once the column exists, the question becomes: what's the default for legacy rows? | `backend/app/session_repo.py:16-44` | When migrating, either backfill all existing rows to `'default'` (one tenant's data) OR backfill to NULL and refuse to display NULL-tenant rows in the UI (tombstone the legacy data). The second is safer if the existing data set was for "demo / dogfood" use. |
| Push reminder fan-out | Backend | red | Follow-up reminder logic joins `triage_sessions` to `push_tokens` by `device_id`. If two tenants happen to share an emulator device_id (test fixtures, common in QA), tenant A's reminder could land on tenant B's device. Today moot (one tenant) but worth fixing before the second tenant joins. | `backend/sql/20260421_triage_sessions_device_id.sql:1-25`, `backend/app/push.py:78` | Add tenant_id to the join key once the column exists: `ON push_tokens.device_id = sessions.device_id AND push_tokens.tenant_id = sessions.tenant_id`. |
| Webhook fan-out | Backend | red | `notifier.send_alert` uses ONE `WEBHOOK_SLACK_URL` and ONE `WEBHOOK_DISCORD_URL`. Every tenant's emergencies fire at the same TriAIge ops Slack. This may be intentional (TriAIge ops is the on-call), but a hospital-side ops channel is not supported. | `backend/app/notifier.py:117-146`, env: `WEBHOOK_SLACK_URL` / `WEBHOOK_DISCORD_URL` | If hospital-side on-call rotation is part of the pilot offer, support `WEBHOOK_SLACK_URL_<tenant>` env vars or move webhook URLs into the per-tenant catalog file. |
| Curated catalog filename collision | Backend | low | The tenant_id regex `[a-z0-9_-]{1,32}` and the explicit reject of `"default"` plus `"json"` (because `curated_conditions.json` has stem `curated_conditions` which would parse to tenant_id `"json"`) cover the obvious filesystem-traversal attempts. | `backend/app/admin_tenants_api.py:47,189` | None. Defense-in-depth is in place. |

---

## Pilot readiness verdict

### Verdict: **YELLOW** for a single Acıbadem-class pilot, **RED** for any
multi-tenant scenario where two hospitals share the same Supabase project.

### Reasoning

For a **single big tenant** ("Acıbadem Istanbul, only customer for the
first six months"), the current state is workable IF:
- Every session is implicitly tagged "tenant = acibadem_istanbul" (which
  is the case today, because all sessions are tagged with no tenant at
  all and the curated catalog is loaded from
  `curated_conditions.acibadem_istanbul.json` only when a runtime is
  built for that tenant — an architectural assumption that needs
  verifying once a non-default runtime is ever loaded);
- The DPA explicitly states "TriAIge runs a dedicated environment for
  this customer" and "no other tenant data is co-resident";
- TriAIge ops accepts that the global Slack/Discord webhook IS the
  Acıbadem on-call channel.

The pilot CANNOT be sold as "we already do tenant isolation" because:
- The `triage_sessions` table has no `tenant_id` column. Any hospital
  CISO running an audit will flag this in five minutes.
- An admin user gaining access to the dashboard sees every session, full
  stop. There is no read-side scope.
- Cross-tenant data co-residency is the explicit design assumption in
  the catalog flow ("a hospital can override just a few labels while
  inheriting the rest" — `runtime.py:200`) but data-plane reality
  contradicts it.

For a **second tenant**, the current state is RED. The schema doesn't
support it, the dashboard doesn't support it, the push fan-out doesn't
support it. Adding tenant #2 without the pre-pilot checklist below would
result in tenant A's admin seeing tenant B's sessions, which is a
material breach.

---

## Pre-pilot checklist (before first paying customer)

Effort: S = ≤ ½ day, M = ½–2 days, L = > 2 days.

| # | Fix | Effort | Why |
|---|---|---|---|
| 1 | Migration: add `tenant_id text NOT NULL DEFAULT 'default'` to `triage_sessions`, `triage_events`, `triage_feedback`, `push_tokens`. Backfill existing rows. | S | Foundational. Every other fix depends on this column existing. |
| 2 | `session_repo.create_session(...)` accepts `tenant_id`. `triage.py` reads `x-tenant-id` header (with `"default"` fallback). Mobile sends the tenant ID via `EXPO_PUBLIC_TENANT_ID`. | M | Wires the column to the writer. |
| 3 | Per-tenant runtime cache: `_RUNTIME_BY_TENANT: Dict[str, Runtime]`. Look up by header. | S | Today's `_RUNTIME = None` cache treats one tenant as the universe. |
| 4 | `admin_users` table: add `tenant_id` column. RLS policy: scope reads to own tenant. Add a `super_admin` policy carve-out for TriAIge ops. | M | Foundational for dashboard scoping. |
| 5 | `requireAdmin()` returns `{user, role, tenantId}`. Every admin page calls `.eq("tenant_id", tenantId)` on its Supabase query. | M | Closes the dashboard cross-tenant leak. |
| 6 | Add `tenant_id` to Prometheus counter labels for `triage_envelope_total`, `confidence_score`, `rate_limit_hits_total`. Update Grafana dashboard. | S | Per-tenant analytics are a sales talking point. |
| 7 | Audit log table: `triage_session_views`. Wire from the session detail page. | M | Hospital DPA will demand "who looked at this patient's data and when." |
| 8 | Document the tenant model in `PRIVACY_AND_SECURITY.md` and `KVKK_DPA_TEMPLATE.md`. Diagram of the tenant-scope boundary. | S | Sales artifact. The code is necessary but not sufficient — DPA reviewers want a doc. |
| 9 | RLS enable on `triage_sessions`, `triage_events`, `triage_feedback`, `push_tokens`. Service-role backend bypasses; tenant-scoped JWT for the dashboard. | L | Defense-in-depth. The dashboard's service-role admin client is a single-point-of-failure today. |
| 10 | Move catalog storage from filesystem to Supabase (`tenant_catalogs` JSONB table). Migrate the seven existing catalogs. | M | Filesystem storage breaks the moment Fly scales to 2 machines. |

**Total pre-pilot effort:** ≈ 6–8 engineering-days for a focused
sequence. Items 1–6 are the load-bearing minimum; 7–10 depend on the
specific tenant DPA.

---

## Post-pilot scaling — what becomes critical at 10 tenants? 100?

### At 10 tenants

- **Filesystem catalog storage breaks.** Multi-machine Fly deploys serve
  stale catalogs after a PUT. Item #10 above becomes mandatory.
- **Per-tenant Slack/Discord webhooks.** TriAIge-ops can't be the
  on-call for 10 hospitals simultaneously. Either the routing becomes
  hospital-side or TriAIge stands up a per-tenant routing service.
- **Per-tenant rate limits.** A misbehaving mobile build at one tenant
  shouldn't degrade the others. Tenant_id becomes part of the rate-limit
  bucket key.
- **Per-tenant Prometheus dashboards.** The Grafana dashboard becomes a
  template per tenant or a single dashboard with a `tenant_id` variable.
  Cardinality at 10 is fine; the architecture needs to be ready.
- **Per-tenant audit retention.** Different hospitals will have
  different retention requirements (5 years, 10 years, KVKK minimum).
  The retention cron from PII_LEAK_AUDIT recommendation #3 needs a
  per-tenant config table.
- **Per-tenant LLM provider routing.** Some tenants will accept Wiro
  (TR), others will demand on-prem or refuse Google/OpenAI. The
  `LLM_PROVIDER` env var becomes a per-tenant setting.

### At 100 tenants

- **Multi-region Supabase.** Single-region EU likely insufficient for
  EU + TR + GCC + UK customers. Tenant routing by region.
- **Tenant onboarding self-service.** Manual catalog seeding via the
  admin UI doesn't scale. CSV import for bulk catalog edits, or a
  schema-first authoring flow with a JSON-schema validator.
- **Tenant-scoped feature flags.** Some tenants on V4 envelope, others
  on V5; some with red-flag question pack A, others B. The
  `version_gating` middleware is a starting point but isn't tenant-aware.
- **Per-tenant data residency.** Hospitals in regulated markets
  (Switzerland, UK NHS) will demand in-country storage. Multi-region
  Supabase + tenant→region routing.
- **Tenant lifecycle automation.** Provisioning, deprovisioning,
  termination cleanup (delete the tenant_id rows, wipe the catalog).
  Today the delete endpoint covers catalog only — not session data.
- **Cross-tenant analytics for product** (anonymized, opt-in). Useful
  for clinical research; demands its own consent + DPA path.

---

## Honesty section — what could not be audited statically

1. **Live RLS state.** SQL files show migration intent but the actual
   `pg_policies` rows on the running Supabase project were not
   introspected. RLS could be enabled or disabled in ways the migration
   files don't reveal.
2. **The mobile RESULT renderer's per-tenant disclaimer use.** The
   catalog carries a `disclaimer_tr`; whether the mobile app actually
   reads the per-tenant value in the rendered RESULT screen needs a
   trace through `mobile/src/screens/`.
3. **Whether sessions created against `tenant_id="acibadem_istanbul"`
   would actually be served the right curated catalog.** The runtime
   cache (`_RUNTIME` global, populated once) means only the FIRST
   tenant's runtime is ever loaded in the current process. Static
   review confirms this; live confirmation requires hitting the API
   with two different tenant headers and inspecting the served catalog.
4. **`llm_calls` schema.** Migration file exists; not read. Whether it
   carries tenant_id is unknown.
5. **Rate-limit bucket internals.** `app/rate_limit.py` was not deeply
   read. Whether the bucket key is per-IP, per-device, or per-tenant
   needs confirmation for the post-pilot scaling claim above.
6. **Test coverage of the multi-tenant catalog path.**
   `backend/tests/test_multi_tenant_catalog.py` exists per the Grep
   earlier; the test cases were not enumerated. Confirm at least one
   test exercises catalog override for a non-default tenant.
