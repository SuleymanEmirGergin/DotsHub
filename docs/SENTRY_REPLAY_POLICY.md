# Sentry Session Replay — Configuration Decision Record

**Status:** ACTIVE (Session 6 ship → Session 14 review).
**Owners:** Mobile eng + Privacy/Compliance.
**Next review:** Quarterly, or on any Sentry SDK major version bump,
or if a new PII-carrying surface lands in the mobile app.

This doc is the canonical record of *what Session Replay captures,
what it masks, and why.* It's the artifact we point at during:

- KVKK / HIPAA audits ("how does the app handle patient data?")
- Sentry SDK upgrades (does the new default config preserve our
  masking contract?)
- On-call runbook use (quarterly PII audit — see
  `docs/runbooks/MOBILE_SENTRY_OUTAGE.md#quarterly-pii-audit`)

The *implementation* lives in
`mobile/src/observability/sentry.ts::initSentry` +
`beforeSend`. This doc is the human-readable spec that
implementation must match. A change in either one without a
matching update in the other is a bug.

---

## 1. What Session Replay captures

### 1a. What DOES land in Sentry

| Capture type | Default behavior | Our config |
| ------------ | ---------------- | ---------- |
| Screen frames (video-like) | on | on, with masking (see §2) |
| User gestures (tap position + target type) | on | on |
| Navigation breadcrumbs | on | on (we emit our own via `useNavigationBreadcrumbs`) |
| Network breadcrumbs (URL + status + duration) | on | on, URLs redacted via `redactUrlPath` |
| Console logs | on | on |
| Device metadata (model, OS, app version) | on | on |
| Event / crash context | on | on, scrubbed by `beforeSend` (see `sentry.ts::beforeSend`) |

### 1b. What we deliberately DO NOT send

| Signal | Why excluded |
| ------ | ------------ |
| IP address | KVKK art. 6: IP is a direct identifier. `sendDefaultPii: false` in `Sentry.init`. |
| `x-device-id` header / body field | Stable fingerprint across sessions; aggregated error reports become de-anonymisation vectors. Scrubbed from `request.headers` + `request.data` in `beforeSend`. |
| `authorization` header | Standard auth hygiene. Same scrub list. |
| `user_input_tr` body (free-text patient description) | The highest-value PII surface — the reason this doc exists. Replaced with `"[SCRUBBED]"` in `beforeSend`. |
| `answers`, `doctor_ready_summary_tr`, `why_specialty_tr`, `emergency_reason_tr`, `meta` | Composed from or containing patient input. Same `[SCRUBBED]` treatment. |
| Raw Turkish medical terms in breadcrumb messages | `redactPII` pass over every breadcrumb `message` + `data` value. Patterns: TCKN (11-digit TR ID), phone, email, UUID. |

### 1c. Sampling

| Sample path | Rate | Rationale |
| ----------- | ---- | --------- |
| `replaysSessionSampleRate` (prod) | **0.1** (10% of sessions) | Bounded storage cost; enough diversity to see common flows. |
| `replaysSessionSampleRate` (dev) | 1.0 | Dev team needs every session to debug; no users involved. |
| `replaysOnErrorSampleRate` | **1.0** (always) | Every crash gets the 60s window leading up to it — that's the high-value case. Overrides session rate when an error fires. |
| `tracesSampleRate` (prod) | 0.1 | Performance traces sampled conservatively. |

---

## 2. Masking layers

Layer order (each applies independently):

### Layer A — Replay integration visual masks

`Sentry.mobileReplayIntegration` options as currently configured:

```ts
Sentry.mobileReplayIntegration({
  maskAllText: true,
  maskAllImages: true,
  maskAllVectors: true,
});
```

And `maskAllInputs: true` is the SDK default (we don't override).

| Option | Covers | Effect |
| ------ | ------ | ------ |
| `maskAllText: true` | Every `<Text>` component | Renders as a filled opaque rectangle in the replay. Ops sees text POSITION + SIZE but not content. |
| `maskAllInputs: true` *(SDK default)* | Every `<TextInput>` | Same treatment for input values. |
| `maskAllImages: true` | Every `<Image>` | Covers avatar URIs, emergency banners, etc. We don't ship user-uploaded images today; this is defence-in-depth for future features. |
| `maskAllVectors: true` | Every SVG + react-native-svg primitive | Icons + charts → blanked. Charts on the Analytics dashboard are dashboard-side only; this guards future mobile charts. |

**What this DOES mean:** every pixel in a replay that could be patient-visible text or image is redacted to a solid block.

**What this DOES NOT mean:** gesture tracks (where the user tapped), screen transitions, and breadcrumb metadata are all retained. A replay is still useful for "user tapped button X, then tapped Y, then the crash happened" — just not for "what did the user type?" because we don't ship that.

### Layer B — Event body scrubbing (`beforeSend`)

Runs on every event before transport. Code:
`mobile/src/observability/sentry.ts::beforeSend`.

Scrubs:

1. **Known body keys** (case-insensitive) replaced with
   `"[SCRUBBED]"`:
   `user_input_tr`, `input_text`, `user_message`, `answers`,
   `doctor_ready_summary_tr`, `why_specialty_tr`,
   `emergency_reason_tr`, `meta`, `device_id`, `x-device-id`.

2. **Known auth headers** (case-insensitive):
   `authorization`, `cookie`, `x-admin-key`, `x-supabase-auth`,
   `x-device-id`.

3. **Free-text redaction** via `redactPII` over every breadcrumb
   `message` + every string value in `extra` / `contexts`:
   - TCKN (11-digit TR ID, first digit 1–9)
   - Phone (international + TR local shapes)
   - Email
   - UUID

4. **URL path collapse** — `/v1/session/{uuid}/...` →
   `/v1/session/[id]/...` in `event.transaction` + `event.request.url`
   + breadcrumb URLs. Prevents session UUIDs from becoming
   cardinality landmines in the Sentry UI AND removes them as a
   potential cross-session de-anonymisation vector.

5. **Drop test/CI events** — `environment=test|ci` → return `null`
   (event discarded). Prevents Jest runs that accidentally carry
   a DSN from phoning home.

### Layer C — Backend-side defence (not strictly Sentry, but part
of the same contract)

The backend also maintains its own PII scrubber
(`backend/app/observability/sentry_init.py::before_send`) for
exceptions that originate server-side. The mobile `beforeSend`
and backend `before_send` share the same key list and patterns,
intentionally — so PII policy is defined once and enforced twice.

---

## 3. KVKK + HIPAA alignment

### 3a. KVKK (Kişisel Verilerin Korunması Kanunu, Türkiye)

| Principle | How Sentry Replay config aligns |
| --------- | ------------------------------- |
| Data minimization (art. 4) | Free-text patient descriptions never leave device; screen frames masked. What Sentry receives is "shape of the app's UI + which buttons the user pressed" — the minimum needed to debug crashes. |
| Explicit purpose limitation | Sentry used solely for crash + performance observability, not analytics / marketing. Documented in `docs/runbooks/MOBILE_SENTRY_OUTAGE.md` §Severity. |
| Lawful basis (art. 5) | Legitimate interest (service-operation safety). NOT consent-based — we don't prompt the user. This is defensible BECAUSE replay contains no identifiable data under our masking config. If we ever relax masking, the lawful basis must shift to explicit consent. |
| Data subject rights | A replay without identifiable content cannot be mapped back to a specific user → GDPR/KVKK "right to access" and "right to erasure" don't create a backlog. Deleting the Sentry project deletes all replays uniformly. |

### 3b. HIPAA (relevant only if we enter the US market)

HIPAA treats health information + identifiers as a combined
trigger. Our config is strictly safer than HIPAA's minimum:

- **PHI identifiers** — we don't capture any of the 18 categories
  (name, geographic subdivisions smaller than state, dates, phone,
  email, SSN, etc.) because `beforeSend` scrubs them all.
- **De-identification standard** — our masked replay plus scrubbed
  event payload does not permit re-identification. Equivalent to
  HIPAA's "Safe Harbor" method post-masking.

If we go US-live, this doc + the implementation should pass a
Business Associate Agreement review with Sentry (Sentry has a
standard BAA available for Enterprise tier). If we don't pay for
Enterprise, we cannot legally process PHI through Sentry — but
that's fine because we don't send PHI in the first place.

---

## 4. Renegotiation knobs

This section lists what we *could* change and what it would cost.
Use this when discussing thresholds with product/privacy, not as
an action list.

### 4a. Would loosen (risk → low/medium)

| Knob | Current | Loosen to | Risk added |
| ---- | ------- | --------- | ---------- |
| `replaysSessionSampleRate` (prod) | 0.1 | 0.3 | Storage cost 3× + more scrape volume. Zero PII risk change — same masking applies. |
| `replaysOnErrorSampleRate` | 1.0 | 0.5 | Lose half the crash-proximate replays. Minor debugging loss; big privacy no-change. |

### 4b. Would tighten (risk → never loosen without privacy eng sign-off)

| Knob | Current | Tighten to | Cost |
| ---- | ------- | ---------- | ---- |
| `maskAllText` | true | `false` + per-component `mask` attribute | HUGE — one component without `mask` leaks patient text. Only justifiable if we start building non-clinical screens (marketing-only pages) where text is safe to display. Even then, the default should stay `true`. |
| `maskAllInputs` | true (SDK default) | false | NEVER without explicit consent + a BAA (if US). TextInput is the single highest-value PII surface in the app. |
| `maskAllImages` | true | false | Low-risk today (no user uploads) but becomes high-risk the moment we ship anything image-related. Keep default-on. |
| `maskAllVectors` | true | false | Low-impact, low-risk. SVG content on mobile is mostly icons; revealing them makes replays prettier without leaking data. Defensible to loosen post-release if ops want better visual debugging. |

### 4c. Decisions recorded from review sessions

| Date | Decision | Rationale |
| ---- | -------- | --------- |
| Session 6 (initial) | Ship with aggressive mask (all four `maskAll*` true, sample 0.1 prod / 1.0 on-error) | Medical app, not taking chances on release. |
| Session 14 (this review) | No config changes. Rationale doc published. Quarterly audit established. | Masking behavior is working; no ops pain has been reported. Changing anything without operational data is premature. |
| *(future — add rows as decisions happen)* | | |

---

## 5. Consent UI — open question

**Today:** the app does NOT surface a "we capture replays"
disclosure to the user. The legal basis is legitimate interest
(§3a), which is tenable precisely because our masking removes
the identifiable content.

**Risk:** if we ever materially loosen masking (see §4b), we must
flip the legal basis to explicit consent and ship a consent UI.
The Settings screen already has a "Legal" section linking to
Privacy Policy — that's where the consent toggle would live.

**Action:** *no action today.* This is called out here so the
first person who proposes loosening masking sees the coupled
obligation.

---

## 6. Quarterly audit

Run the audit every 3 months (or triggered by any release that
touches `mobile/src/observability/*` or `mobile/src/api/*`):

1. Sample **at least 5 recent production replay events** (Sentry
   UI → Issues → pick 5 distinct issues → open replay).
2. For each replay, confirm:
   - [ ] No readable text in any frame (all text-shaped regions
         are solid blocks).
   - [ ] No readable inputs (text fields render as blocks).
   - [ ] Breadcrumb trail shows `/v1/session/[id]/…`, never a
         literal UUID.
   - [ ] Exception messages (if any) contain no TCKN / phone /
         email / free-text patient description.
   - [ ] Tags / contexts don't carry `device_id` verbatim.
3. Sample **3 recent production events** (Sentry UI → Issues →
   open the event detail JSON). Check the `request`, `extra`,
   `contexts`, and `breadcrumbs` sections for the same patterns.
   The local helper script `scripts/sentry_event_pii_scan.py`
   will flag obvious leaks when you paste the JSON into stdin —
   see `docs/runbooks/MOBILE_SENTRY_OUTAGE.md#quarterly-pii-audit`.
4. Record the audit date + findings in
   `docs/incidents/` (use the standard TEMPLATE.md; treat a passed
   audit as a zero-finding "incident" for archival purposes).
5. Any failed check is a P1 privacy bug — open a ticket, ship an
   EAS build with a fix, re-audit after deploy.

The audit exists because:
- Sentry SDK upgrades occasionally change default masking behavior
  (past example: Sentry React Native 5 → 6 moved `maskAllText` from
  the Replay integration to the base SDK — our config kept it set
  correctly, but a less-attentive upgrade could silently open a
  leak).
- New screens / new breadcrumb categories may accidentally expose
  data the current `beforeSend` doesn't know to scrub.

---

## 7. Related files

| Path | Role |
| ---- | ---- |
| `mobile/src/observability/sentry.ts` | Implementation — `initSentry` + `beforeSend` |
| `mobile/src/observability/redact.ts` | Pure redaction utilities (TCKN, phone, email, UUID, URL) |
| `mobile/src/observability/breadcrumb.ts` | Breadcrumb helpers; every category passes through `redactUrlPath` |
| `mobile/__tests__/observability/sentry.test.ts` | Unit tests for `beforeSend` scrubber contract |
| `backend/app/observability/sentry_init.py` | Backend-side mirror — same key list + patterns |
| `docs/runbooks/MOBILE_SENTRY_OUTAGE.md` | Runbook; references this doc for masking invariants |
| `docs/OBSERVABILITY.md` | General observability overview; links here |
| `scripts/sentry_smoke.sh` | Weekly DSN smoke (Session 7); pairs with this audit doc |
| `scripts/sentry_event_pii_scan.py` | Local PII scanner — paste Sentry event JSON, get report |
