# Runbook: Mobile Sentry Down / Flooding / Quota-Exhausted

## Quick checklist (incident → green)

- [ ] Confirm scope: Sentry-org issue vs. just the mobile project
- [ ] Check Sentry status page (https://status.sentry.io)
- [ ] If flooding: identify the runaway error signature + add an
      inbound filter or rate-limit rule in Sentry UI
- [ ] If quota-exhausted: bump sample rate down OR upgrade plan OR
      wait for quota reset
- [ ] Confirm the app itself is NOT impacted — Sentry SDK failures
      are swallowed by design (blank DSN = no-op contract)
- [ ] If SDK is tripping client-visible errors: flip the kill switch
      (clear `EXPO_PUBLIC_SENTRY_DSN` on next EAS build)
- [ ] Post-incident ticket (see bottom)

## Symptoms

- **Sentry UI** shows no events for the last N minutes (normal rate
  is ~`traces_sample_rate * traffic`).
- **Release adoption** on the `triaige-mobile-rn` project doesn't
  tick up after a new EAS build.
- **Free-tier quota exhaustion** alert from Sentry (email / webhook).
- **User complaint**: app crashes on startup in the field. (Separate
  from Sentry itself being down — verify with a direct crash repro.)

## Severity

- **P3 — visibility degraded, serving unaffected.** Sentry failures
  are silent by design:
  - Blank DSN: `initSentry()` short-circuits, no `@sentry/react-native`
    import attempted.
  - DSN set but transport fails: Sentry SDK buffers + retries; app
    threads are never blocked on a network call.
  - `beforeSend` throws: Sentry wraps it in try/except, drops the
    event, keeps running.
- **P2** if the SDK itself starts crashing the app. This would be a
  client-side regression (not a Sentry outage per se) — roll back to
  the previous EAS build.
- **P1** never — Sentry is telemetry, not serving.

## Immediate mitigation

### Case A: We're flooding Sentry (quota approaching or exhausted)

1. **Identify the runaway** — Sentry UI → Issues → sort by `Events`
   descending for the last 24h. Top issue is almost always a single
   exception fired on every render (e.g. an undefined prop on a
   production screen).
2. **Quick kill in Sentry** — Settings → Inbound Filters → add a
   Custom Filter matching the issue's error message or stack frame.
   Events still arrive but get dropped before counting. Takes effect
   immediately; no deploy.
3. **Real fix** — patch the mobile bug, ship an EAS OTA update
   (`eas update --channel production`) or a full binary release. The
   inbound filter can be removed once the issue disappears from the
   top-issues list.

### Case B: Sentry provider outage

1. **Verify** — https://status.sentry.io. SDK failures in the client
   logs (`Sentry transport error: 502`) are a hint; a "we failed to
   send event" burst in the admin console confirms.
2. **No action needed.** The SDK buffers events and retries with
   backoff. Events from the outage window either land on recovery or
   get dropped. The app itself keeps running.
3. If the outage is prolonged and you can't tolerate backlog when
   Sentry recovers: lower `EXPO_PUBLIC_SENTRY_TRACES_SAMPLE_RATE`
   to 0 on the next build so only errors (not traces) are captured.

### Case C: Sentry SDK is crashing the app (regression from an SDK upgrade)

This is the scenario that warrants P2 severity.

1. **Roll back the EAS build** to the previous production release.
   `eas build:list --platform ios --profile production` → find the
   prior build ID → `eas build:resign --id <id>` or re-submit the
   known-good binary.
2. **If a store-level rollback isn't possible fast enough** — ship
   an OTA update (`eas update --channel production`) with
   `EXPO_PUBLIC_SENTRY_DSN=""` in the env. The client will init
   Sentry as disabled on next launch, bypassing the crashing SDK.
3. Investigate the SDK upgrade that caused the regression
   (`@sentry/react-native` + the Expo plugin). Pin to the known-good
   version in `package.json`.

## Data integrity

- **Events lost during the outage**: unrecoverable. Sentry is
  best-effort telemetry. For the postmortem, cross-check backend
  `/health` + `triage_sessions` volume for the same window — if the
  backend was healthy but mobile Sentry missed events, we lost
  crashes; if both were degraded, there's a product incident on top.
- **Source maps**: the `@sentry/react-native/expo` plugin uploads
  source maps at build time, NOT at event time. An upload failure
  during build is captured in the EAS build log, not here; verify
  the last successful source map upload in Sentry UI → Releases →
  the specific release → Source Maps.

## Recovery verification

1. Sentry UI → Issues → a new event arrived for the current release
   in the last 5 min.
2. Release Health → `triaige-mobile-rn@<release>` shows a non-zero
   `Session Count` for the last hour.
3. A synthetic test: hit the "Intentional Error" dev menu button on
   a TestFlight/internal build, confirm the event lands in Sentry
   within ~30 seconds.

## PII regression check (post-incident)

If the outage was caused by a flood of a SINGLE issue — before
closing the ticket, sample 10 events from that issue and confirm:

- [ ] No raw Turkish patient text (`hasta`, `ağrı`, `nefes` markers)
      in exception messages, breadcrumbs, or `request.data`.
- [ ] No TCKN, phone, email in any field.
- [ ] Session-scoped URLs aggregated as `/v1/session/[id]/…`.

If any of the above is violated, the `beforeSend` scrubber has a
regression — open a P1 security bug; the next EAS build MUST ship a
fix. This is load-bearing for KVKK compliance.

## Quarterly PII audit

Independent of any specific incident — a standing quarterly audit
runs the same checks, expanded, over a sample of recent production
events and replays. See `docs/SENTRY_REPLAY_POLICY.md` §6 for the
full procedure. Condensed operator flow:

1. Sample **5 distinct issues** from Sentry → Issues, filter to
   `environment:production`, time range: last 30 days. For each,
   open the most recent replay and confirm the four masking
   invariants (text blocks, input blocks, URL collapse, no
   identifying context) listed in SENTRY_REPLAY_POLICY.md §6.
2. For the same 5 issues, pull the latest event JSON and run it
   through the local helper:

   ```bash
   # Copy the event JSON from Sentry UI → the three-dots menu →
   # "View as JSON" → raw. Then:
   python scripts/sentry_event_pii_scan.py < event.json
   ```

   A PASS means no flagged patterns. A FAIL means one or more of:
   TCKN (11-digit), phone, email, UUID (session id leak), or
   Turkish medical free-text keywords that the `beforeSend`
   scrubber should have stripped. Any FAIL is a P1.
3. Alternative (if you prefer CLI-first): use the Sentry REST API
   to pull the last 5 events of an issue as JSON:

   ```bash
   ORG=triaige
   PROJECT=triaige-mobile-rn
   ISSUE_ID=<copy-from-sentry-ui>
   curl -s -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
     "https://sentry.io/api/0/projects/$ORG/$PROJECT/issues/$ISSUE_ID/events/?limit=5" \
     > /tmp/events.json
   # Then iterate through events and pipe each into the scanner:
   jq -c '.[]' /tmp/events.json | while read -r evt; do
     echo "$evt" | python scripts/sentry_event_pii_scan.py
   done
   ```
4. Record the audit + any findings in
   `docs/incidents/` using `TEMPLATE.md` — a passed audit is a
   zero-finding "incident" for archival purposes (see
   SENTRY_REPLAY_POLICY.md §6).

## Escalation

- Sentry quota burned within <24h repeatedly: evaluate paid tier
  upgrade. Alternative is aggressive sample-rate cut (<5%) which
  loses signal on rare crashes.
- Crash rate increase across MULTIPLE unrelated issues: probably a
  product regression, not a telemetry issue. Escalate to on-call eng
  and start a real incident.

## Prevention

- **Release-gate the sample rate** — `EXPO_PUBLIC_SENTRY_TRACES_SAMPLE_RATE`
  is per-build, so staging and prod can differ. Keep prod at 0.1,
  staging at 0.5, dev at 1.0.
- **Pin SDK version** — don't `^7.x` in `package.json`. Use `~7.1.x`
  so patch bumps land but minor/breaking changes require a
  conscious review + new EAS build.
- **Check the inbound filter list quarterly** — dead filters that
  don't match any live signature mean we've forgotten to remove them.
  Dead filters also mean ops can forget they exist and be surprised
  by silently-missing events on a real incident.

## Post-incident checklist

- [ ] **Timeline**: detected (Sentry admin alert / user report),
      mitigated (filter applied / kill switch flipped), green (events
      flowing again)
- [ ] **Root cause**: flooding issue / provider outage / SDK
      regression / quota exhausted
- [ ] **Impact**: number of events dropped, release adoption gap,
      visible crashes during the blind window
- [ ] **PII check**: sample passed (see above)
- [ ] **What went well** / **what didn't**: 3 bullets each
- [ ] **Action items**: inbound-filter hygiene, sample-rate audit,
      SDK pinning
- [ ] Close the incident + archive Sentry-side filter config
