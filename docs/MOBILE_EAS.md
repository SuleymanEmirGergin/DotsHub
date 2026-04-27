# Mobile — EAS Build + Store Submit

End-to-end recipe for getting the Triaige Expo app through EAS into TestFlight (iOS) and Google Play Internal (Android), and from there to the public stores.

**Audience:** the repo owner on first submission. Subsequent releases skip most of the setup.

---

## 0. Architecture at a glance

```
 Developer (you)
      │
      ▼  git tag v1.0.0 → push
 GitHub Actions (.github/workflows/mobile-eas-build.yml)
      │  eas build --profile production --platform all
      ▼
 EAS Build cloud (runs Apple Xcode toolchain + Android SDK)
      │  artefact: .ipa / .aab
      ▼
 EAS dashboard (https://expo.dev/…)
      │  eas submit --profile production      ← manual, you trigger
      ▼
 App Store Connect (TestFlight) / Google Play Console (Internal track)
      │  promote to production                ← manual review / rollout
      ▼
 Public App Store / Play Store
```

## 1. Prerequisites (one-time)

### Expo / EAS account

1. https://expo.dev/signup — free tier is fine to start (covers 30 builds/month for free).
2. Create an organization named `triaige` (or match the slug in `app.config.ts`).
3. Settings → **Access tokens** → "Create" → scope: **Read and write**. Copy the token once shown.
4. GitHub → Settings → Secrets and variables → Actions → new secret:
   - `EXPO_TOKEN` = the access token

### Apple Developer Program (iOS only)

1. https://developer.apple.com/programs/ — **$99/year**. Enrolment takes 24-48h.
2. After approval, https://appstoreconnect.apple.com:
   - **Users and Access → Keys** → create an "App Store Connect API" key with role `Admin`. Download the `.p8` file once — store it in EAS: `eas credentials` CLI or via the dashboard.
   - **My Apps → +** → create the `Triaige` record. Bundle ID = `com.triaige.app` (matches `app.config.ts`).
   - Note the numeric **Apple App Store Connect App ID** from the app record URL.
   - Note the **Apple Team ID** from "Membership".

### Google Play Developer (Android only)

1. https://play.google.com/console — **$25 one-time** registration.
2. Create the `Triaige` app record. Package name = `com.triaige.app`.
3. **Setup → API access** → link a Google Cloud project → create a service account with role `Service Account User`. Download the JSON.
4. Upload the JSON to EAS: `eas credentials` → Android → "Google Service Account Key".

## 2. Build profiles in `eas.json`

Already configured in the repo. You pick a profile per build:

| Profile | Distribution | Backend target | Use when |
|---------|--------------|----------------|----------|
| `development` | Internal (dev-client build) | `.env` fallback | Debugging native modules, testing a dep upgrade |
| `preview` | Internal (signed .ipa / .apk) | `triaige-backend.fly.dev` | Share with beta testers before store submission |
| `production` | Store-bound (.ipa / .aab) | `triaige-backend.fly.dev` | Submit to App Store / Play Store |

Auto-increment: `production` profile bumps `ios.buildNumber` + `android.versionCode` automatically each build, so you never re-submit the same binary.

## 3. First build (manual)

### Via GitHub Actions (recommended)

1. https://github.com/SuleymanEmirGergin/TriAIge/actions/workflows/mobile-eas-build.yml
2. **Run workflow** button → pick:
   - Branch: `main`
   - Profile: `preview` (start here)
   - Platform: `all`
   - Message: "First preview build"
3. Run. The job queues the build on EAS in ~30s then exits. The actual binary takes 15-30 minutes.
4. Follow progress: https://expo.dev/accounts/triaige/projects/triaige/builds

### Via CLI (alternative)

```bash
cd mobile
npm install -g eas-cli
eas login            # one-time
eas build --profile preview --platform all --message "First preview"
```

### Tag-triggered production build

```bash
# Bump version in app.config.ts (e.g. 1.0.0 → 1.0.1)
git commit -am "chore: bump version to 1.0.1"
git tag v1.0.1
git push origin main --tags
# GitHub Actions auto-starts production build for both platforms.
```

## 4. Submit to stores (manual, after first build finishes)

### iOS — TestFlight

```bash
cd mobile
eas submit --profile production --platform ios --latest
```

- EAS uploads the `.ipa` to App Store Connect.
- Apple processes it for ~5-15 minutes (you get an email).
- It appears under **TestFlight → Internal Testing**. Add yourself + trusted testers to the internal group.
- From TestFlight, promote to external testing (100-10000 users, needs Apple review ~24h) or submit for App Store release (review ~24-48h).

### Android — Internal Track

```bash
eas submit --profile production --platform android --latest
```

- Default `track: internal` in `eas.json` → uploads as a Play Console "Internal testing" release.
- Immediately shareable via opt-in URL to up to 100 testers.
- Promote to `closed` → `open` → `production` tracks via Play Console UI as testing progresses.

## 5. Over-the-Air (OTA) updates

For JavaScript-only changes (no native module updates) you can push an update without a new build:

```bash
cd mobile
eas update --branch production --message "Fix typo in result screen"
```

- Users get the update on next app launch (Expo Updates runtime picks it up).
- Bypasses store review (allowed by both Apple + Google for JS updates).
- `channel` in `eas.json` matches `branch` here, so binaries from `profile=production` receive updates from `--branch production`.

## 6. Assets & metadata checklist

Store submission requires these before you can actually publish:

### App icon

Currently a placeholder in `mobile/assets/icon.png` (solid-blue "T" mark). **Before production submit:**

1. Get the final 1024×1024 PNG (no alpha, no rounded corners — Apple adds those).
2. Replace `mobile/assets/icon.png`.
3. Also update:
   - `mobile/assets/adaptive-icon.png` (Android foreground, 1024×1024, transparent background)
   - `mobile/assets/splash-icon.png` (splash screen artwork, ~2048×2048 centred on brand blue)
   - `mobile/assets/favicon.png` (web favicon, 48×48)
4. Commit. EAS picks up the new assets on the next build.

### Screenshots

Required sizes (minimum one per size; up to 10):

| Device | iOS required | Android required | Resolution |
|--------|--------------|------------------|------------|
| iPhone 6.7" | ✅ yes | — | 1290×2796 |
| iPhone 6.5" | optional | — | 1242×2688 |
| iPad Pro 12.9" | optional | — | 2048×2732 |
| Android phone | — | ✅ yes | 1080×1920 or similar |
| Android tablet | — | optional | 1200×1920 |

Capture from the real device or simulator:

```bash
# iOS simulator
xcrun simctl io booted screenshot ~/Desktop/ss-1.png

# Android emulator
adb exec-out screencap -p > ~/Desktop/ss-1.png
```

### Metadata (per locale)

| Field | iOS max | Android max | Notes |
|-------|---------|-------------|-------|
| App name | 30 chars | 30 chars | "Triaige" |
| Subtitle (iOS only) | 30 chars | — | e.g. "Ön triaj, doğru branş" |
| Short description | — | 80 chars | |
| Full description | 4000 chars | 4000 chars | Include medical disclaimer |
| Keywords (iOS) | 100 chars | — | comma-separated, e.g. `triaj,sağlık,doktor,acil,hasta,belirti` |
| Privacy URL | ✅ required | ✅ required | `https://triaige.vercel.app/privacy` |
| Support URL | ✅ required | ✅ required | `mailto:emirgergin21@gmail.com` for now |

### App Store privacy questionnaire (Apple only)

App Store Connect asks a long form: "what data do you collect, for what purpose, is it linked to identity?" — answer according to `docs/privacy/` + the privacy policy page. Rough shape:

- **Contact info → Email**: only if user opts into summary email. Used for functionality, NOT linked to identity, NOT for tracking.
- **Health & fitness → Health**: symptom descriptions the user types. Used for app functionality, NOT linked to identity.
- **Usage data → Product interaction**: anonymous session counts. Used for analytics, NOT linked to identity.
- **Diagnostics → Crash data / Performance**: if Sentry DSN set. Used for app functionality, NOT linked to identity.

"Tracking" (ATT prompt) = none.

## 7. Release checklist (per version)

```
[ ] Version bumped in mobile/app.config.ts (expo.version)
[ ] CHANGELOG.md updated with user-facing changes
[ ] Staging build tested end-to-end on a real device (preview profile)
[ ] Backend deployed + /health green
[ ] Privacy + terms pages live + match submission version
[ ] App icon matches intended release design (not the placeholder)
[ ] Screenshots regenerated if UI changed
[ ] git tag v<version> created + pushed (kicks off production build)
[ ] EAS build succeeded on both platforms
[ ] eas submit for iOS + Android
[ ] TestFlight / Play Internal tested by at least 2 people
[ ] Store release notes ready (per locale)
[ ] Submitted for review
[ ] Release monitored for 24h after live (crash rate, error rate, support inbox)
```

## 8. Troubleshooting

### "EAS CLI version mismatch"

`eas.json::cli.version` pins the minimum. Local CLI: `npm install -g eas-cli@latest`. CI automatically installs the latest.

### "Unable to access resource: apple"

Apple credentials expired. `eas credentials` → iOS → "Manage credentials" → generate fresh.

### "Version/buildNumber conflict"

App Store Connect rejects duplicate `buildNumber` for a given `version`. Cause: two production builds produced from the same commit without bumping. Fix: `eas.json::production.autoIncrement: true` is already set, so this is usually a stale cache — bump `version` in `app.config.ts` manually and rebuild.

### "Sentry source maps upload failed"

`SENTRY_AUTH_TOKEN` secret missing or expired in GitHub Actions. Builds still succeed; the mobile bundle just has no source map attribution on Sentry. Regenerate at Sentry Settings → Auth Tokens.

## 9. Where to go next

- [`docs/DEPLOY_AND_ENV.md`](DEPLOY_AND_ENV.md) — all env vars across backend / dashboard / mobile
- [`docs/RUNBOOK.md`](RUNBOOK.md) — incident response when production misbehaves
- [`docs/DEPLOY_FLY.md`](DEPLOY_FLY.md) — backend side (Fly.io)
- [`docs/OBSERVABILITY.md`](OBSERVABILITY.md) — mobile Sentry + backend Prometheus / Grafana Cloud

---

**TL;DR first-time flow:**

1. Apple Developer Program ($99) + Google Play Console ($25) — accounts.
2. `EXPO_TOKEN` GitHub secret → you can run the workflow.
3. GitHub Actions → **Mobile EAS Build** → profile `preview` → wait 20min → TestFlight / Play Internal app installed.
4. Test on real device. If OK, tag `v1.0.0` → production build → `eas submit`.
5. App Store / Play review (~24-48h). Live.
