# Mobile version-gate rollout playbook

The backend exposes a version-gate policy via
`GET /v1/config/features → client_version`. Mobile app reads it on
launch and, depending on `mode`, silently passes / shows an update
banner / blocks the app. This doc is the flip-by-flip rollout flow
for ops when a new minimum client version goes live.

## Config knobs

Set in backend env (see `backend/.env.example`):

| Env var | Purpose |
|---|---|
| `MIN_CLIENT_VERSION` | Apps below this version are "out of date" |
| `LATEST_CLIENT_VERSION` | Informational — newest published build |
| `CLIENT_VERSION_ENFORCEMENT` | `off` / `warn` / `block` |
| `CLIENT_VERSION_UPDATE_URL_IOS` | App Store deep link |
| `CLIENT_VERSION_UPDATE_URL_ANDROID` | Play Store deep link |

Modes:
- **`off`** — gate is inactive. Client ignores version mismatch.
  Safe default — mobile audit logs show `state=ok` regardless.
- **`warn`** — amber banner above the stack. Tappable Update button
  opens the store link; Dismiss clears banner for that session only
  (reappears next launch).
- **`block`** — full-screen wall. No dismiss. User must install the
  new version or uninstall.

## Standard rollout flow

When a new mobile version ships with a bugfix old clients shouldn't
keep hitting:

### Phase 0 — Prep (before push to stores)

1. Mobile: bump `app.json` → `expo.version` (e.g. `1.2.0` → `1.3.0`).
2. Ship the new build to TestFlight / Play internal-testing.
3. **Do not** touch backend env yet.

### Phase 1 — Warn (bake period, 3–7 days)

Once the new build is in stores and a meaningful % of users have
auto-updated:

1. Backend env:
   ```
   MIN_CLIENT_VERSION=1.3.0
   LATEST_CLIENT_VERSION=1.3.0
   CLIENT_VERSION_ENFORCEMENT=warn
   CLIENT_VERSION_UPDATE_URL_IOS=itms-apps://…
   CLIENT_VERSION_UPDATE_URL_ANDROID=market://…
   ```
2. Restart backend (or reload config — depends on deployment).
3. Verify `GET /v1/config/features` returns the new policy.
4. Watch mobile telemetry (Sentry + any custom events):
   - % of sessions receiving warn (= users still on old)
   - tap-through rate on the Update button
   - uninstall rate (should not spike)

Bake for **at least 3 days**. If tap-through is low (<30% daily),
extend another 3 days and consider nudging via push.

### Phase 2 — Block (hard cutoff)

Flip only when:
- Warn has been live ≥ 3 days,
- The old version has a known-bad medical-logic bug (wrong
  EMERGENCY routing, specialty misassignment, PII leak) — NOT just
  a feature gap,
- You've prepared support comms for users still stuck on old
  devices that can't receive the update.

1. Backend env:
   ```
   CLIENT_VERSION_ENFORCEMENT=block
   ```
2. Restart / reload.
3. Verify the block screen renders on an old client (hold a
   pre-1.3.0 build for this).
4. Announce in #dotshub-ops Slack channel + update the public status
   page if you have one.

### Phase 3 — Tidy up

Once the old version's share drops to <1% and tickets stabilise:

1. Bump `MIN_CLIENT_VERSION` to the next known-safe version (don't
   leave it lagging the new ship-target).
2. Consider dropping `CLIENT_VERSION_ENFORCEMENT=warn` or `off`
   again if the safety-critical bug no longer exists.

## Emergency rollback

If `block` is misconfigured (wrong version in env, store link broken,
users crash-looping on the block screen):

1. Backend env: `CLIENT_VERSION_ENFORCEMENT=off`.
2. Restart **immediately** — users refetch `/v1/config/features` on
   every launch, so off-mode propagates in seconds.
3. Run `GET /v1/config/features` from an anon client to confirm the
   policy is off.
4. Backfill a post-mortem once stable.

`off` → `block` path is one env var, so rollback is cheap. **Don't
hesitate to flip back if anything looks off** — a locked-out user
can't be triaged.

## Testing the policy locally

```bash
# Simulate a warn policy
export MIN_CLIENT_VERSION=99.0.0
export CLIENT_VERSION_ENFORCEMENT=warn
uvicorn app.main:app --reload

curl -s http://localhost:8000/v1/config/features | jq
# Expect: client_version.mode == "warn", client_version.min == "99.0.0"
```

Mobile: set `Constants.expoConfig.version` in `app.json` below
`MIN_CLIENT_VERSION` and launch the app. You should see the warn
banner (or, if mode=block, the full-screen wall).

## Known limitations

- Semver compare ignores pre-release suffix (`1.3.0-beta` == `1.3.0`).
  Intentional — devs on beta builds shouldn't be blocked by their
  own release number.
- Policy is per-backend-instance. Multi-tenant deployments must set
  env per tenant; today there's no per-tenant override mechanism.
- The block screen has no "emergency bypass" — by design. If you
  need one, add a hidden diagnostic route and keep it undocumented.

## Related

- Component source: `mobile/src/hooks/useVersionGate.ts`,
  `mobile/src/components/VersionUpdateBanner.tsx`,
  `mobile/src/components/VersionBlockScreen.tsx`
- Backend endpoint: `backend/app/api/routes/features.py`
- Config: `backend/app/core/config.py` (`MIN_CLIENT_VERSION` etc.)
- `SECURITY.md` §Deploy-time checklist
