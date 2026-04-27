# External rename checklist (Dotshub -> TriAIge)

## Already done (in-repo, session 17)

Session 17 (commit `076f3be`) renamed every in-repo "Dotshub" string to
"TriAIge" across 40 files (85 byte-level replacements). Two earlier
commits had already touched some external surfaces in source:
`bfb454c` (Fly app slug + observability assets) and `7ab4e51` (mobile
bundle IDs + storage keys). The repo is now clean — a `Dotshub`
grep returns only the explicitly-preserved audit-trail comments in
`mobile/utils/deviceId.ts`, `mobile/i18n/storage.ts`, and the
generated `mobile/_bundle_check.js` artefact.

This doc covers what lives **outside** the repo — the SaaS dashboards,
project slugs, channel names, and account namespaces that must be
renamed by hand on each provider's web UI, because no commit can
reach them.

Sequence the work top-down: GitHub repo first (every other doc URL
points back at it), then Fly + Vercel (live URLs), then observability,
then nice-to-haves.

---

## High priority

External systems where stale branding causes user-visible confusion,
broken links, or wrong attribution.

### 1. GitHub repo

- Old: `github.com/SuleymanEmirGergin/DotsHub`
- New: `github.com/SuleymanEmirGergin/TriAIge`
- Confirmed via `git remote -v` — the `origin` remote still points at
  `https://github.com/SuleymanEmirGergin/DotsHub`.
- How: GitHub web UI -> the repo -> **Settings** -> **General** ->
  **Repository name** -> type `TriAIge` -> **Rename**.
- Side effects:
  - GitHub keeps a 301 redirect from the old name to the new one
    indefinitely (per GitHub docs: "we'll redirect any web requests
    for the old location to the new one"). Existing clones using the
    old URL keep working but should be updated.
  - Webhooks pointing at the repo URL (CI integrations, Vercel,
    EAS, Sentry release auto-link) auto-follow because they use the
    repo's stable numeric ID, not the slug.
  - Open PRs and issues are preserved.
  - Doc URL in `docs/MOBILE_EAS.md:72` references
    `github.com/SuleymanEmirGergin/TriAIge/actions/...` — already
    written to the new URL, so it will resolve correctly only AFTER
    the rename. This is a one-line latent breakage right now.
- After rename, in every local clone / worktree:
  ```bash
  git remote set-url origin https://github.com/SuleymanEmirGergin/TriAIge.git
  ```
- Verify: `git remote -v` shows the new URL, `gh repo view` returns
  `SuleymanEmirGergin/TriAIge`.

### 2. Fly.io app

- The `fly.toml` at repo root reads `app = "triaige-backend"`, so the
  Fly app slug was renamed in commit `bfb454c`.
- Verify the actual Fly app exists under the new name:
  ```bash
  flyctl status --app triaige-backend
  flyctl apps list | grep -E "dotshub|triaige"
  ```
- If `flyctl apps list` still shows `dotshub-backend`, you have two
  options:
  1. **Recommended — destroy + recreate** under the new slug, since
     Fly does NOT support in-place app rename. Run `flyctl apps create
     triaige-backend`, re-set every secret with `flyctl secrets set`
     (see `docs/DEPLOY_FLY.md` Section 3 for the full list — at minimum
     `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `WIRO_API_KEY`,
     `WIRO_API_SECRET`, `ADMIN_API_KEY`, `CORS_ORIGINS`, and the
     Grafana/Sentry secrets), then `flyctl deploy`.
  2. Keep the old slug live and update `fly.toml` back to the old
     name. Not recommended — slug shows up in the public Fly URL
     (`triaige-backend.fly.dev` is referenced from
     `docs/DEPLOY_FLY.md`, `docs/RUNBOOK.md`, `mobile/eas.json`,
     `.github/workflows/fly-deploy.yml`).
- Side effects of recreate:
  - Public URL changes from `dotshub-backend.fly.dev` to
    `triaige-backend.fly.dev` (the latter is what every client config
    in the repo already expects).
  - Upstash Redis attached to the old app needs `flyctl redis attach`
    to the new app, OR a fresh `flyctl redis create --name
    triaige-redis --plan free` (drops in-memory rate-limit windows
    once on switchover — acceptable).
  - DNS pointing at the old `.fly.dev` host needs updating; if no
    custom domain is in front, no DNS work needed.
- Verify:
  - `curl -sS https://triaige-backend.fly.dev/health | jq` returns
    `{"status":"ok",...}`.
  - `flyctl status --app triaige-backend` shows machine `started`,
    health `passing`.
  - `.github/workflows/fly-deploy.yml` next deploy succeeds.

### 3. Vercel project (dashboard)

- The dashboard is hosted on Vercel; `docs/DEPLOY_FLY.md:142` and
  `docs/OPS_STAGING_SETUP.md:51` reference
  `https://triaige.vercel.app` and
  `https://triaige-staging.vercel.app` as the expected hostnames.
- Vercel project name controls the default `<project>.vercel.app`
  hostname.
- How: Vercel dashboard -> the project -> **Settings** -> **General**
  -> **Project Name** -> change from `dotshub` (or whatever the
  current name is) to `triaige` -> **Save**. Repeat for the staging
  project (`triaige-staging`) if it exists separately.
- Side effects:
  - Default vercel.app hostname changes immediately. Vercel keeps
    the old hostname as an alias for a grace period; verify under
    Settings -> Domains.
  - Build logs, deployment history, env vars all carry over.
  - GitHub integration (the Vercel app on the repo) auto-follows
    because it tracks repo ID, not name. Confirm under Vercel ->
    Settings -> Git after the GitHub rename.
- Verify:
  - `https://triaige.vercel.app` returns the dashboard.
  - The CORS origin set on Fly (`CORS_ORIGINS` secret) includes the
    new URL — see `docs/DEPLOY_FLY.md` Section 5 for how to update.
  - Dashboard -> backend round-trip works (admin login, session list).

### 4. Sentry projects (backend + mobile)

- Two Sentry projects in scope:
  - **Backend** Python project — DSN consumed by
    `backend/app/observability/sentry_init.py` via `SENTRY_DSN`. No
    project slug is hard-coded in code, but the events page URL
    will still show the old slug.
  - **Mobile** React Native project — `mobile/app.config.ts` sets
    `organization: process.env.SENTRY_ORG ?? "triaige"` and
    `project: process.env.SENTRY_PROJECT ?? "triaige-mobile-rn"` for
    the source-map upload step. `docs/OBSERVABILITY.md` (line ~360,
    "Mobile Sentry") documents the same `triaige-mobile-rn` slug.
    Source-map upload will fail until the actual Sentry project
    matches one of those names.
- How:
  - Sentry web UI -> **Settings** -> **Organization Settings** ->
    **Slug** -> rename org from `dotshub` to `triaige`.
  - For each project: **Settings** -> **Project Settings** -> **Name**
    + **Slug** -> rename to `triaige-backend` and `triaige-mobile-rn`.
- Side effects:
  - Sentry keeps the DSN itself (the random 32-char hash) stable
    across rename. Backend `SENTRY_DSN` does NOT need to be rotated.
    Verified per Sentry docs: "Renaming a project does not invalidate
    its DSN."
  - The DSN's host portion may include the org slug
    (`https://<hash>@<org>.ingest.sentry.io/...`); Sentry continues
    to accept events on the old host alongside the new one. No
    immediate action needed, but quarterly audit (per
    `docs/SENTRY_REPLAY_POLICY.md`) is a good time to refresh DSNs
    to the new host string.
  - Alert rules, inbound filters, and PII scrubbing settings travel
    with the project.
  - Release tags created against the old slug stay accessible.
- Verify:
  - Backend: trigger a synthetic exception, confirm it lands in
    `triaige-backend` project. The weekly smoke
    (`.github/workflows/sentry-smoke.yml`) is the natural canary.
  - Mobile: the next EAS build's source-map upload step succeeds
    (build log mentions `sentry-cli sourcemaps upload`).
  - GitHub Actions secrets `SENTRY_ORG` and `SENTRY_PROJECT` (used in
    `.github/workflows/mobile-eas-build.yml` lines 119-120) match the
    new slugs.

### 5. Slack workspace and channels

- `docs/OPS_ROTATION.md:30` references `#triaige-ops` as the rotation
  announcement channel. The channel name must exist as written.
- `docs/OBSERVABILITY.md` and `config/grafana/alerts/backend-health.yaml`
  both refer generically to "Slack #alerts" — the actual channel
  name lives in the Slack incoming webhook URL stored in
  `WEBHOOK_SLACK_URL` (Fly secret) and `SLACK_WEBHOOK_URL` (GitHub
  Actions secret on `health-alert.yml`).
- How:
  - Slack -> the channel `#dotshub-ops` (or equivalent) -> name
    pencil -> rename to `#triaige-ops`.
  - Slack -> **Settings & administration** -> **Workspace settings**
    -> **Name** -> rename if the workspace is also `Dotshub`.
  - Webhook URL itself (`https://hooks.slack.com/services/T../B../...`)
    stays valid across channel rename — Slack keeps the channel ID
    stable.
- Side effects:
  - Slack auto-posts a "channel was renamed" message and inserts a
    redirect from the old name (anyone typing `#dotshub-ops` lands on
    `#triaige-ops`).
  - Webhook URL keeps working. No need to rotate
    `WEBHOOK_SLACK_URL` purely for the rename.
- Verify:
  - Trigger a test alert from the backend admin endpoint
    (`docs/OPS_ROTATION.md:88`-style canary) and confirm it lands in
    the renamed channel.
  - Slack search for `#dotshub` returns no live channel.

### 6. Discord server / channels (if used)

- `WEBHOOK_DISCORD_URL` is a parallel webhook surface to Slack. If
  the Discord server itself is named `Dotshub`, rename it via Server
  Settings -> Overview. If only specific channels are named after
  the brand (`#dotshub-alerts`), rename via channel settings.
- How: Discord client -> right-click server icon -> **Server Settings**
  -> **Overview** -> **Server Name** -> save.
- Side effects: webhook URLs survive the rename (webhook is bound
  to the channel ID). Same as Slack.
- Verify: trigger a test alert; confirm it lands in the renamed
  server.

### 7. Apple App Store Connect record

- `docs/MOBILE_EAS.md:45` says "create the Triaige record" and the
  Bundle ID `com.triaige.app` is already wired in
  `mobile/app.config.ts`.
- If the App Store Connect app record was created BEFORE the rename
  with display name "Dotshub", users see "Dotshub" in TestFlight /
  App Store search until the listing is updated.
- How:
  - App Store Connect -> **My Apps** -> the app -> **App Information**
    -> change **Name** + **Subtitle** -> save.
  - Bundle ID is immutable in App Store Connect — but
    `mobile/app.config.ts` already targets `com.triaige.app`, so the
    bundle ID either:
    1. Already matches (rename was display-only), OR
    2. Doesn't match (the existing record is `com.dotshub.app`),
       which means the next production build will be REJECTED with
       "Bundle ID mismatch" by EAS submit. Resolution: create a NEW
       App Store Connect app with bundle ID `com.triaige.app`,
       re-link in `eas.json::submit.production.ios.ascAppId` (which
       is currently `TBD_APP_STORE_CONNECT_APP_ID`).
- Side effects: store reviewers will re-evaluate the metadata change
  on the next submission (~24h).
- Verify: TestFlight build's listing shows "Triaige".

### 8. Google Play Console record

- Same shape as Apple. `docs/MOBILE_EAS.md:52` says "Create the
  Triaige app record. Package name = `com.triaige.app`."
- Package name is immutable on Play Console once published — same
  rename caveat as Apple. If the package name on the live record is
  `com.dotshub.app`, you cannot rename it; you must publish a NEW
  app and migrate users.
- How: Play Console -> **All apps** -> the app -> **App information**
  -> rename app name + short description -> save.
- Verify: Play Console internal-track listing shows "Triaige".

### 9. EAS / Expo account + project

- `docs/MOBILE_EAS.md:36` says "Create an organization named
  `triaige`". `mobile/app.config.ts` has `slug: "triaige"`.
- `.github/workflows/mobile-eas-build.yml:140` constructs the dashboard
  URL `https://expo.dev/accounts/triaige/projects/triaige/builds`.
- If the Expo account / org is still `dotshub`, that workflow's
  Summary step will print a 404 link, and `eas build` will fail with
  "expo project slug `triaige` does not match the project on EAS".
- How: Expo dashboard -> account avatar -> **Account settings** ->
  **Username** -> rename, OR for an org -> **Organization settings**
  -> **Slug** -> rename.
- Side effects:
  - `EXPO_TOKEN` GitHub Actions secret keeps working (token is
    user-scoped, not slug-scoped).
  - In-flight builds finish under the new slug. Build history is
    preserved.
  - OTA update channels (`development`, `preview`, `production` per
    `mobile/eas.json`) carry over.
- Verify: `eas whoami` shows the new account name; manual workflow
  dispatch on `mobile-eas-build.yml` succeeds and the EAS dashboard
  link in the summary resolves.

---

## Medium priority

Observability surfaces visible to the ops team but not to end users.

### 10. Grafana Cloud stack + dashboards

- `docs/OBSERVABILITY.md:156` references stack URL
  `https://triaige.grafana.net`. The stack URL is set by the org slug
  on Grafana Cloud.
- The dashboard JSON at `config/grafana/dashboard-triaige.json` has:
  - `"uid": "triaige-pretriage"` (line 279)
  - `"title": "Triaige - Pretriage Backend"` (line 278)
  - `"tags": ["triaige", "pretriage", "fastapi"]` (line 273)
  - `"description": "TriAIge pre-triage backend - ..."` (line 29)
  - `"description": "Prometheus / Grafana Cloud scraping the Triaige
    /metrics endpoint."` (line 6, in `__inputs[0]`)
- Alert rule names in `config/grafana/alerts/backend-health.yaml` and
  `triage-envelope.yaml` are brand-neutral (`BackendHighErrorRate`,
  `EmergencyEnvelopeSpike`, etc.) — no rename needed.
- The alert namespace, however, is documented as `triaige-backend`
  in `docs/OBSERVABILITY.md:208`. If the live Grafana Cloud Managed
  Alertmanager has the rules under namespace `dotshub-backend`, the
  next `observability-sync.yml` push will create a SECOND namespace
  alongside the old one. Resolution: rename or delete the old
  namespace via the Grafana UI / `mimirtool rules delete-namespace`.
- How:
  - Grafana Cloud account -> **Switch organization** -> the
    `Dotshub` org -> **Org settings** -> rename to `Triaige`. Same
    effect on the stack URL.
  - Dashboards: the JSON above will overwrite the dashboard on the
    next `observability-sync.yml` run because `uid` and `title`
    drive idempotency. The OLD dashboard (under the old uid like
    `dotshub-pretriage`) stays orphaned in the UI — delete it
    manually.
- Side effects:
  - Stack URL change breaks bookmarks; Grafana Cloud does NOT
    302-redirect the old slug. Update
    `GRAFANA_CLOUD_STACK_URL` GitHub secret AND any local bookmarks.
  - `GRAFANA_CLOUD_API_TOKEN`, `GRAFANA_CLOUD_PROM_URL`,
    `GRAFANA_CLOUD_PROM_USER`, `GRAFANA_CLOUD_PROM_TOKEN` GitHub
    secrets stay valid (token is account-scoped, prom_url is
    region-scoped).
  - Datasources, contact points (Slack route bound to `severity`
    label), notification policies all carry over.
- Verify:
  - `https://triaige.grafana.net/dashboards` lists "TriAIge -
    Pretriage Backend" with uid `triaige-pretriage`.
  - `Alerting -> Alert rules -> triaige-backend` shows the synced
    rules.
  - `https://triaige.grafana.net/explore` query
    `up{service="backend"}` returns 1 (the Fly agent's scrape
    landing).
  - `RUNBOOK.md:445` link `https://<slug>.grafana.net/dashboards`
    becomes `https://triaige.grafana.net/dashboards`.

### 11. Prometheus / metric labels

- `config/grafana/prometheus.yml:22` job name is `triaige-backend`,
  which matches the Grafana Cloud-side scrape label and dashboard
  queries.
- `config/grafana-agent/config.river:25` declares
  `prometheus.scrape "triaige_backend"` — also already aligned.
- No external metric label currently carries `dotshub`. Skip unless
  Grafana Cloud's recording rules / silences were created against
  the old label namespace; check via Grafana UI ->
  **Alerting -> Silences** -> look for any silence label-matcher
  containing `dotshub`.
- Verify: `up{job="triaige-backend"}` returns 1 in Grafana Cloud
  Explore.

### 12. Grafana provisioner name (local dev only)

- `config/grafana/dashboards.yml:12` has `name: triaige`. This is
  the local-only Grafana container's provisioner — never reaches
  Grafana Cloud, no external action needed. Listed for
  completeness only.

---

## Low priority / cosmetic

Internal-only naming where rename is hygiene, not user-facing.

### 13. GitHub Actions bot email addresses

- `.github/workflows/guardrail.yml:105` uses commit author email
  `guardrail-bot@triaige.com`.
- `.github/workflows/tuning.yml:76` uses `tuning-bot@triaige.com`.
- These are commit-trailer identities, NOT mailboxes that need to
  exist. They show up in `git log --author` output as the bot
  author. No external action required UNLESS someone owns the
  `triaige.com` domain and wants the bot mail to deliver — in which
  case set up MX records + a forwarder. Most likely this is purely
  cosmetic and the address should remain a non-deliverable identity.
- Verify: `git log --author=triaige.com` shows future automated
  commits if those workflows have run since the rename. No mailbox
  lookup needed.

### 14. Env var KEY names (not values)

- Searched the entire tree for env var KEYS containing `DOTSHUB_`
  (e.g. `DOTSHUB_API_KEY`). Zero matches. The session 17 rewrite
  was thorough on this front.
- Skip.

### 15. Placeholder domains in docs

The following `.example` / placeholder domains appear in the repo
and are NOT live owned domains. They are illustrative and act as
templates for the operator to substitute their real domain when
running the relevant playbook. Listed here so you can decide whether
to acquire `triaige.com` / `triaige.co` and replace them with a real
owned domain in a future commit:

- `docs/RUNBOOK.md:45` — `status.triaige.com` (planned status page,
  not yet acquired)
- `docs/DEPLOY_FLY.md:165` — `dashboard.triaige.com` (custom domain
  for the dashboard, optional)
- `docs/OPS_ROTATION.md:42, 88` — `https://api.triaige.example/...`
  (placeholder API host in canary-curl examples)
- `docs/OPS_STAGING_SETUP.md:37` — `e2e-admin@triaige.example`
  (placeholder email for E2E admin user — this one IS used as the
  literal `STAGING_TEST_ADMIN_EMAIL` GitHub secret default; verify
  the secret you actually configured uses `.example` not `.com`)
- `docs/runbooks/SECURITY_INCIDENT.md:38-41` — `ops@triaige.example`,
  `eng-lead@triaige.example`, `security@triaige.example`,
  `legal@triaige.example` (placeholder rota mailboxes)
- `SECURITY.md:11` — `security@triaige.example` (vulnerability
  reporting address — should be a real mailbox before public launch)
- `mobile/__tests__/observability/sentry.test.ts:78-79` —
  `https://api.triaige.test/...` (test fixture; explicitly the
  reserved `.test` TLD — no action needed)

The `.example` and `.test` TLDs are reserved by IANA (RFC 2606) for
exactly this purpose; they will never resolve. The `.com` mentions
ARE potentially live and need DNS / domain ownership work if you
actually plan to use them.

Action: decide which of `triaige.com`, `triaige.co`, `triaige.app`
you intend to own, then replace each placeholder with the real
domain in a follow-up commit. This is documentation-quality, not a
runtime blocker.

---

## Sequencing notes

Ordering matters in two places:

1. **GitHub repo rename FIRST** (item 1). Every other doc URL,
   workflow link, and webhook backref points at the repo. Renaming
   it last would mean every other rename's "verify" step fails with
   404. After step 1, in every clone /
   worktree run `git remote set-url origin
   https://github.com/SuleymanEmirGergin/TriAIge.git`.

2. **Fly recreate BEFORE Vercel CORS update**. If you destroy +
   recreate the Fly app (item 2), the public URL stays
   `triaige-backend.fly.dev` (already the canonical name in repo),
   so Vercel's `NEXT_PUBLIC_API_BASE` env var doesn't change. But
   the new Fly app's `CORS_ORIGINS` secret must include the Vercel
   URL BEFORE the dashboard tries to call it, otherwise the
   dashboard hits a CORS wall on first load. Order: create Fly app
   -> set `CORS_ORIGINS` secret with current Vercel URL -> deploy
   Fly -> rename Vercel project -> update `CORS_ORIGINS` again with
   the new Vercel URL if it changed.

3. **Sentry org rename BEFORE the next mobile EAS build**. Source
   map upload reads `SENTRY_ORG` + `SENTRY_PROJECT` GitHub secrets
   (`mobile-eas-build.yml:119-120`). If the secrets still say
   `triaige` but the actual Sentry org is `dotshub`, the upload step
   fails. Either rename the Sentry org first, OR temporarily set
   the secrets to the old slug until you do.

4. **Slack/Discord channel renames are independent** — webhook URLs
   stay valid across channel rename, so do these last.

---

## In-repo bugs found during this audit (out of scope to fix here)

None. Session 17's rewrite was complete: every grep for `dotshub` /
`Dotshub` / `DOTSHUB` returned only the three explicitly-preserved
locations (audit-trail comments in `mobile/utils/deviceId.ts` and
`mobile/i18n/storage.ts`, plus the generated
`mobile/_bundle_check.js` artefact). No additional rename work
required inside the repo.
