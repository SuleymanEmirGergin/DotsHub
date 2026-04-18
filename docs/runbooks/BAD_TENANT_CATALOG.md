# Runbook: Bad Tenant Catalog Upload

## Symptoms

- A specific hospital's (tenant_id = X) triage sessions go weird
  after a recent admin catalog edit: curated entries missing,
  wrong descriptions, malformed Turkish text, etc.
- Complaints scoped to ONE tenant. Other tenants unaffected.
- **Not** a crash — the runtime loader logs `WARN` and falls back
  to the default catalog, but the tenant-specific prep metadata
  (ICD-10, doctor questions, self-care) simply doesn't appear.
- Admin UI `/admin/tenants/<id>` shows the bad JSON in the editor.

## Severity

- **P2 — scoped to one tenant.** Not safety-critical: the
  orchestrator still routes correctly because the curated-injection
  labels come from `runtime.curated_conditions["conditions"].keys()`,
  and a broken file degrades that lookup but doesn't misroute
  patients. Still, the hospital's admin may be confused why their
  edits "vanished".

## Immediate diagnosis (< 5 min)

1. Read the admin API directly to see what the runtime sees:

```bash
curl -H "x-admin-key: $ADMIN_API_KEY" \
     "$BACKEND/v1/admin/tenants/<tenant_id>/curated" | jq .
```

2. If that returns a 500 → JSON parse error on disk. The tenant
   file is syntactically broken. Proceed to rollback.
3. If it returns JSON but the `conditions` object is empty or
   wrong → the content is broken. Proceed to rollback.

## Rollback (the reason audit log exists)

The audit log captured the previous state. Query Supabase:

```sql
SELECT id, actor, created_at, new_doc
FROM tenant_catalog_audit
WHERE tenant_id = '<tenant_id>'
ORDER BY created_at DESC
LIMIT 5;
```

Pick the most recent row where `new_doc` is known-good. PUT it
back:

```bash
curl -X PUT \
     -H "x-admin-key: $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d @last_good.json \
     "$BACKEND/v1/admin/tenants/<tenant_id>/curated"
```

`last_good.json` is the `new_doc` jsonb you selected. The PUT
overwrites the tenant file on disk and (as a side effect) appends
another audit row — so the rollback itself is traceable.

## If audit log is also broken

`tenant_catalog_audit` insert is fire-and-forget and best-effort
(`admin_tenants_api._write_audit_row` logs + continues on failure).
In practice this means:

- If the insert failed silently during the bad write, the audit
  table may not have a row for the broken version. But the PREVIOUS
  version's row should still be there.
- If Supabase itself is down, audit writes were dropped across
  the board. Fall back to:
  - `git log` on the repo if tenant files are tracked (they are
    NOT by default — production filesystem is authoritative).
  - File backups from the backend container host — this requires
    an out-of-band backup policy that the team must own.

## Prevention

1. **Schema validation on the PUT endpoint.** The Pydantic
   `CatalogPayload` model should reject missing `conditions` or
   malformed `ConditionPayload` shapes before writing. Tracked as
   a follow-up — the current validator is permissive.
2. **Backup policy.** Mount `/srv/pretriage/config` as a volume
   that has a scheduled snapshot (hourly, 7-day retention). This
   is an infra concern, not an app concern — document in
   `docs/DEPLOY_AND_ENV.md`.
3. **Dry-run / preview mode in the admin UI.** Instead of PUT
   overwriting immediately, preview the rendered RESULT for a
   representative scenario with the new catalog. Admin clicks
   "confirm" after visual check. Follow-up feature.

## Recovery verification

1. `GET /v1/admin/tenants/<tenant_id>/curated` — check `conditions`
   count matches the pre-incident baseline.
2. Single test triage for that tenant (manual in mobile app) —
   verify the expected curated labels re-appear in `top_conditions`
   with prep metadata.
3. Update the tenant's admin with rollback note + timestamp for
   their own records.
