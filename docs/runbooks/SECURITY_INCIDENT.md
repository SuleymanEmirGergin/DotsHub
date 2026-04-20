# Runbook: Security Incident Response

Use when a suspected breach, leaked credential, malicious-input
attack, unauthorised data access, or PII exposure is reported or
observed. Escalates above the normal operational runbooks — legal
and KVKK notification timelines may apply.

## Quick checklist (first 30 minutes)

- [ ] Do NOT panic-delete logs or rotate keys yet — preserve
      evidence. Investigation first, rotation second.
- [ ] Identify what's suspected: leaked secret, RCE, XSS, data
      exfiltration, DoS, social engineering, supply-chain.
- [ ] Notify incident commander (see escalation matrix below).
- [ ] Declare severity (P0/P1/P2) and create a private #sec-incident
      Slack channel.
- [ ] Stop the bleeding (block abusive IP, disable compromised
      account, revoke leaked key — in that order of priority).
- [ ] Preserve evidence: screenshot dashboards, export logs to a
      secure bucket, save Sentry event IDs.
- [ ] Start the timeline log (who did what when, in UTC).

## Severity guide

| Severity | Signals |
|---|---|
| **P0** | Confirmed patient-PII breach, RCE on backend, exfiltration active |
| **P1** | Credential leak (service_role, admin key), unauthorised admin access |
| **P2** | Suspected abuse with no confirmed data access, stale token reuse |
| **P3** | Vulnerability report with no exploitation, supply-chain advisory |

Anything touching patient input = minimum P1 by default.

## Escalation matrix

| Role | Contact | When |
|---|---|---|
| Incident Commander | ops@dotshub.example | Always, first call |
| Engineering Lead | eng-lead@dotshub.example | P0/P1 within 15 min |
| Security Lead | security@dotshub.example | P0/P1 within 30 min |
| Legal / KVKK DPO | legal@dotshub.example | P0/P1 within 1 hour |
| External counsel | (on-file) | Only Legal escalates |

Don't page outside these channels until the incident commander
confirms; multi-channel comms spreads bad info.

## Common scenarios

### Leaked secret in a public commit

1. **Revoke** the credential at the provider (Supabase, Wiro,
   admin-key env) — value is now dead regardless of where it lives.
2. **Rotate** and update the env everywhere it's set (Vercel,
   backend host, GitHub secrets).
3. **Audit** recent activity on the leaked credential:
   - Supabase service-role: `SELECT * FROM auth.audit_log_entries`
   - Wiro: provider dashboard → API logs
   - Admin key: `tenant_catalog_audit` + `llm_calls` rows for the
     window
4. **Rewrite history?** Only if the leak is brand new and nothing
   has mirrored/cloned the commit yet. Otherwise the secret is
   already considered compromised globally — revoke and move on.
5. **Document** the scanner hit (gitleaks, Trufflehog) that caught
   it so detection gaps can be closed.

### Credential-stuffing / brute-force on admin magic-link

1. Supabase dashboard → Authentication → Rate limits — temporarily
   tighten the email-signin rate.
2. Flip `CLIENT_VERSION_ENFORCEMENT=block` if the attack is
   targeting an old-client endpoint.
3. Audit `admin_users` rows for unexpected additions.
4. Revoke sessions via Supabase auth admin API if any look
   suspicious.

### PII in logs

1. Immediately pull the affected log files (Loki / Supabase logs)
   to a private bucket.
2. Identify the code path that failed to redact — usually a new
   endpoint that bypassed `app.pii.redact_pii`.
3. Patch + deploy. Do NOT just clear logs — audit trail matters.
4. Notify affected users if the PII reached an external system
   (LLM provider, analytics, external webhook).

### Malicious input triggering unsafe routing

1. Pull the session from `triage_sessions` and `triage_events`.
2. Check if the output went to a patient (was a RESULT or EMERGENCY
   envelope returned with wrong specialty/urgency?)
3. If yes: treat as P0 clinical-safety incident, not just security.
   Engage clinical lead + Legal.
4. Update the golden-flow regression with the malicious input as
   a fixture so the fix is pinned.

## KVKK obligations (Turkish data protection)

Under Article 12, KVKK requires notification to the Personal Data
Protection Authority within **72 hours** of a data breach that:
- compromises the confidentiality of personal data, OR
- affects patient-health records.

For any P0/P1 involving patient input:

- [ ] Within 72 hours: notify affected data subjects (email)
- [ ] Within 72 hours: notify KVK (official form,
      https://www.kvkk.gov.tr/)
- [ ] Preserve a copy of all logs and correspondence for 5 years

Legal owns the notification flow — engineering provides evidence
pack. Do not send any external notification without Legal signoff.

## Post-incident review (within 7 days)

- [ ] **Full timeline** (detected → contained → mitigated → green)
- [ ] **Root cause** with evidence (code line, config, external
      event)
- [ ] **Blast radius** measured (rows affected, users affected,
      credentials leaked, systems touched)
- [ ] **What went well / didn't** (bluntly — blameless postmortem
      culture)
- [ ] **Action items** with owners:
  - detection gap closure
  - tooling improvements
  - runbook updates
  - security-training gaps exposed
- [ ] **Lessons learned** doc linked from this runbook
- [ ] For KVKK cases: archive the breach evidence pack + external
      correspondence
- [ ] Close the incident in ops tracker, update the CHANGELOG with
      a redacted note

## Prevention cadence

- Quarterly: credential rotation (see `docs/OPS_ROTATION.md`)
- Quarterly: dependency audit summary reviewed by security lead
- Annually: tabletop exercise (simulated breach scenario)
- Continuously: `gitleaks` in CI on every PR
