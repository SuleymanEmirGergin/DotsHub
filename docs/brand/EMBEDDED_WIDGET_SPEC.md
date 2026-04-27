# Embedded Widget Spec — TriAIge Pre-Triage Widget

> **Audience.** Hospital web team plus TriAIge engineering. Read by both: the hospital web lead drops the embed snippet on a landing page; the TriAIge engineer reads this to know what to build and what not to build.

> **Status.** Specification, not yet implemented. This document is the build target for v1 of the embed surface. Sequenced after the production website scaffold ([`WEBSITE_SCAFFOLD.md`](WEBSITE_SCAFFOLD.md)).

---

## 1. Why this product surface exists

The friction in hospital adoption is not the product — it is the integration. Asking a hospital web team to wire a custom REST integration into their CMS, get an internal security review, and ship a hospital-branded triage flow is a six-month conversation. Asking them to add one line of HTML is a one-week conversation.

The widget is the lowest-friction surface area for hospital adoption. Patients triage on the hospital's own domain (better trust, better hospital-side analytics attribution, lower bounce). The hospital web team owns the placement (their CMS, their navigation, their branding context). TriAIge owns the runtime (we ship updates, we fix bugs, we maintain compliance).

Three properties to preserve:

1. **One-line embed.** Anything more than one line and we have lost the hospital web team.
2. **Compliance posture unchanged.** The widget must inherit the same KVKK / GDPR / Sentry posture as the standalone app. PII does not leak into the parent page — even one accidental leak undoes the privacy story.
3. **Hospital-attributable analytics.** The hospital must be able to count widget sessions on their own analytics stack (without us shipping their analytics ID server-side).

---

## 2. Two technical options

### Option A — `<iframe>`-based widget

TriAIge hosts the widget at `widget.triaige.com/embed?...`. Hospital embeds via a one-line `<iframe>`. The widget runs in a separate browsing context.

**Pros:**

- Strong sandbox isolation. JS conflicts impossible; CSS conflicts impossible.
- Faster to ship — the widget is almost the existing dashboard with a stripped chrome.
- CSP for hospital page is unaffected by widget-internal CSP.
- Analytics inside the iframe stays inside the iframe; hospital page does not need to allow our analytics origin.

**Cons:**

- Styling customization is constrained to whatever query-string parameters or theme files we accept.
- Iframes can be blocked by aggressive content blockers; non-iframe-friendly browser extensions break the widget for ~1–3% of users.
- Analytics attribution is fuzzy — if the hospital wants to track "user reached emergency hard-stop in widget", they need to listen for `postMessage` events.
- Mobile responsiveness inside an iframe is harder; the iframe must declare its own height or we must auto-resize via `postMessage`.

### Option B — JS SDK widget

TriAIge ships a `<script>` tag. Hospital adds it to their `<head>` and a `<div id="triaige-widget">` where they want it to render. The widget mounts as a React tree directly into their DOM.

**Pros:**

- Full styling control. Hospital can fully integrate visual identity.
- Better analytics integration — page-level `dataLayer` events visible.
- Better mobile responsiveness; widget shares the parent's layout context.
- No iframe-blocking issue.

**Cons:**

- Surface area for bugs is large. JS conflicts (e.g., the hospital's existing jQuery patching `Object.prototype`) become our debugging problem.
- CSP changes required on hospital side: `script-src widget.triaige.com`, `connect-src api.triaige.com`, etc. This is the same six-month conversation we were trying to avoid.
- PII isolation is harder — a single bug where we accidentally read from `window.parent` or leak a state value into a global is a privacy incident.
- React-version conflicts. Hospital already runs React 17, our widget compiles against React 19 → must ship as a fully self-contained bundle.
- Bundle size matters more (must lazy-load).

### Recommendation

**Start with Option A (iframe) for v1.** Ship the Acıbadem pilot fast. Migrate to Option B (SDK) only if iframe limitations bite — estimated 6–9 months in, after we have real partner feedback.

The migration path is clean: Option B's API surface becomes a superset of Option A's `postMessage` contract. A hospital embedded via Option A who later wants Option B keeps the same event names.

---

## 3. Functional spec for v1 (iframe)

### URL

```
https://widget.triaige.com/embed
  ?tenant=<slug>
  &locale=<tr|en|de|ru|ar>
  &theme=<light|dark|hospital-custom>
  &entry=<intro|chat>
```

### Parameters

| Parameter | Required | Default | Notes |
| --------- | -------- | ------- | ----- |
| `tenant` | Yes | — | Tenant slug. Resolves to tenant-specific curated conditions, theme overrides, allowed parent origins. Example: `tenant=acibadem`. |
| `locale` | No | `tr` | One of `tr`, `en`, `de`, `ru`, `ar`. If unspecified, fall back to `Accept-Language`, then `tr`. Matches the mobile + dashboard locale set. |
| `theme` | No | `light` | `light`, `dark`, or `hospital-custom`. The last reads the tenant's theme JSON (see §3a). |
| `entry` | No | `intro` | `intro` shows the TriAIge intro screen; `chat` skips the intro for hospitals that have their own landing page explaining the tool. |

### Tenant resolution

`tenant=acibadem` → backend reads tenant config:

- Curated condition list — generalize the existing `backend/app/data/curated_conditions.demo_hospital.json` per tenant. Spec: rename the file to `curated_conditions.<tenant_slug>.json` and load by slug at request time.
- Theme overrides JSON (if `theme=hospital-custom`).
- Allow-list of parent origins (frame-ancestors).
- Optional analytics webhook target (see §6).

If the tenant slug does not resolve, the widget renders an error state ("This embed is not configured. Contact your administrator.") rather than falling back to a generic experience. Avoids accidental brand confusion.

### Locale auto-detect

If `locale` is not in the URL:

1. Read `navigator.language` from inside the iframe.
2. If it matches one of the five supported locales, use it.
3. Otherwise fall back to `tr`.

Browser-level `Accept-Language` is forwarded by the iframe's HTTP request and respected at the SSR layer for the initial render — preventing flash-of-wrong-locale.

### Theme

`theme=light` and `theme=dark` use the existing dashboard tokens (see [`docs/DASHBOARD_THEME.md`](../DASHBOARD_THEME.md)).

`theme=hospital-custom` reads a per-tenant theme JSON of shape:

```json
{
  "primary": "oklch(0.6231 0.1880 259.8145)",
  "primary_foreground": "#ffffff",
  "accent": "oklch(0.9514 0.0250 236.8242)",
  "background": "#ffffff",
  "foreground": "#0f172a",
  "border": "#e2e8f0",
  "logo_url": "https://hospital.example.com/logo.svg",
  "logo_alt_tr": "Hastane Adı",
  "logo_alt_en": "Hospital Name"
}
```

Tokens map 1:1 to the same tokens the dashboard uses. Hospital web team supplies the JSON during onboarding; TriAIge admin team validates and stores.

### Entry point

- `entry=intro` (default) — full TriAIge intro screen with the tagline and a "Start" CTA.
- `entry=chat` — skips the intro. Used by hospitals that have their own page explaining the widget (recommended for partners with mature content). The widget opens directly to the symptom input.

### Embed snippet

The recommended embed snippet, with all attributes documented:

```html
<iframe
  src="https://widget.triaige.com/embed?tenant=acibadem&locale=tr&theme=hospital-custom&entry=intro"
  width="100%"
  height="600"
  style="border: 0; max-width: 720px; display: block; margin: 0 auto;"
  allow="microphone *"
  referrerpolicy="strict-origin-when-cross-origin"
  loading="lazy"
  title="TriAIge — Ön Triyaj Asistanı"
></iframe>
```

Attribute notes (each is load-bearing):

- `allow="microphone *"` reserves space for a future voice-input feature without requiring re-embed. Today the widget does not request microphone access. Documented now to avoid a hospital security review re-opening when the feature lands.
- `referrerpolicy="strict-origin-when-cross-origin"` minimizes URL leakage to TriAIge's edge. We need the parent origin (for tenant validation) but not the full path.
- `loading="lazy"` defers iframe load until scrolled near. Improves the hospital's Lighthouse score.
- `title=""` is required for accessibility; provide a localized version per page.

### Cross-origin messaging

The widget posts events to the parent via `window.parent.postMessage`. Parent listens via:

```js
window.addEventListener('message', (e) => {
  if (e.origin !== 'https://widget.triaige.com') return;
  // handle e.data
});
```

Origin check is mandatory; documented in the public embed-integration guide.

#### Events posted by widget → parent

| Event name | Payload shape | When it fires |
| ---------- | ------------- | ------------- |
| `triaige:ready` | `{ version, tenant, locale }` | Widget mounted and ready to receive user input. Use to remove a parent-side loading skeleton. |
| `triaige:emergency_detected` | `{ rule_id, urgency }` | The deterministic emergency layer hard-stopped the flow. Hospital can scroll the widget into view, fire their own analytics event, or display a parent-side prompt. **Never includes the patient's input text.** |
| `triaige:result_shown` | `{ specialty, urgency, risk_level }` | A `RESULT` envelope was rendered. Hospital can fire analytics. **Never includes the patient's input text or the explainability trace.** |
| `triaige:exit` | `{ reason }` | User explicitly closed the widget or hit "Start over". Use for analytics. |
| `triaige:height_changed` | `{ height }` | Widget content height changed. Parent should resize the iframe to avoid scrollbars-within-scrollbars. Optional; iframe with fixed height also works. |

#### Events accepted by widget ← parent (v1: none)

The widget does not accept inbound events from the parent in v1. Adding a parent-to-widget channel introduces a class of injection attacks that we do not need yet. Reserved for v2.

### Result handoff

A hospital that wants to save the result into the patient's electronic record can opt into a result-handoff payload. This is a **separate explicit consent** from the in-widget consent.

When the user finishes triage and grants consent, the widget posts:

```
triaige:result_handoff
{
  session_id: string,           // TriAIge session id, hashed
  specialty: string,            // canonical specialty slug
  urgency: 'EMERGENCY' | 'SAME_DAY' | 'ROUTINE',
  risk_level: 'low' | 'medium' | 'high',
  summary_url: string           // signed URL to fetch the PDF summary, expires in 1 hour
}
```

The hospital's page fetches `summary_url` server-side (not client-side — the URL is a bearer token) and stores the PDF in the patient record.

**What is NOT in this payload:**

- The patient's free-text symptom description.
- The full conversation transcript.
- Any of the explainability trace.

The hospital can request the full session via the standard TriAIge API with the session id, after they have completed their KVKK DPA with the patient. The widget does not bundle that data into the cross-origin message.

---

## 4. Security

### Frame ancestors

Each tenant registers their allowed parent origins during onboarding:

```
acibadem:
  - https://www.acibadem.com.tr
  - https://international.acibadem.com.tr
```

The widget app sets:

```
Content-Security-Policy: frame-ancestors https://www.acibadem.com.tr https://international.acibadem.com.tr;
```

Plus the legacy `X-Frame-Options: ALLOW-FROM <origin>` header (single-origin browsers; deprecated but still respected by some enterprise browsers).

Effect: a competitor cannot embed `widget.triaige.com/embed?tenant=acibadem` on their own site to harvest sessions or impersonate. The browser refuses to render the iframe if the parent origin is not on the list.

### Tenant origin registration

Hospital onboarding flow:

1. Hospital web team submits their parent origin(s) via TriAIge admin.
2. TriAIge engineering validates the origins resolve to the hospital's actual property (DNS check + manual confirmation with the hospital's named contact).
3. The origin allow-list is committed to the tenant config, deployed, then the hospital is notified.

Step 3 takes 24 hours by design. Adding origins to a partner is not a self-service operation. If a hospital is adding a new microsite weekly, they buy the Enterprise tier which surfaces this as a self-service admin form (with a 1-hour propagation delay rather than 24).

### PII handling inside the iframe

Same posture as the standalone app. The widget runs:

- The same backend with the same Sentry scrub layer ([`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md)).
- The same `redactPII` mobile-pattern utilities, ported to the dashboard codebase.
- The same Supabase tables, with a `tenant_id` column added to scope rows per tenant.

Crucially: **nothing the user types appears in any cross-origin message.** Only structured envelope metadata leaves the iframe. The patient input text never crosses the iframe boundary.

### Microphone permission

`allow="microphone *"` is documented in the embed snippet for forward compatibility. The widget does NOT prompt for microphone access in v1 and does NOT use the microphone. When voice-input ships, this attribute already in place avoids re-embed.

---

## 5. Branding

### Default

A small TriAIge wordmark in the widget footer with a `Powered by TriAIge` link to `triaige.com`. Sufficient brand presence without dominating the hospital's experience.

### Hospital branding

`theme=hospital-custom` allows the hospital to:

- Use their primary / accent / background colors (token-mapped, see §3).
- Place their logo in the widget header.
- Customize a single line of intro copy (hospital name and a one-liner welcome).

What the hospital cannot customize via the theme:

- The deterministic emergency hard-stop UI. Safety-critical screen, owned by TriAIge.
- The audit trail disclosure. Compliance-critical, owned by TriAIge.
- The "Powered by TriAIge" footer (unless on Enterprise tier — see white-label).

### White-label option

Enterprise tier: the "Powered by TriAIge" footer is removed, and TriAIge does not appear in the widget UI at all. Available only to enterprise customers under contract; not available in pilot tier.

The trade-off is honest: white-label hides our brand but does not hide our legal responsibility. The widget URL is still on `widget.triaige.com`; the network requests still go to `api.triaige.com`. Anyone inspecting will know. The white-label is a marketing-surface choice, not a technical disguise.

---

## 6. Analytics

### TriAIge-side (always-on)

Per-tenant aggregate counters land in the existing observability stack:

- `widget_session_started_total{tenant="acibadem"}` (Prometheus counter)
- `widget_emergency_detected_total{tenant="acibadem"}` (Prometheus counter)
- `widget_result_shown_total{tenant="acibadem", urgency="..."}` (Prometheus counter, low-cardinality only)

Surfaces to the existing Grafana Cloud dashboard. No PII; no per-session detail at the metrics layer.

### Hospital-side (opt-in)

Hospitals on Growth and above tiers can opt into a webhook:

- They register a webhook URL in TriAIge admin.
- TriAIge posts a signed JSON payload per session:

```json
{
  "tenant": "acibadem",
  "session_id_hashed": "abc123...",
  "started_at": "2026-04-27T10:00:00Z",
  "completed_at": "2026-04-27T10:05:23Z",
  "urgency": "SAME_DAY",
  "result_specialty": "cardiology",
  "result_risk_level": "medium"
}
```

- Webhook signed with HMAC-SHA256 using a per-tenant secret.
- Retry-with-backoff on failure (exponential, 5 attempts over 1 hour).

**What is NOT in the webhook payload:**

- The patient's input text.
- The full conversation.
- The explainability trace.

The hospital uses this for operational analytics only ("how many widget sessions led to a cardiology routing"). Anything richer requires the patient-consented full-session API, which is gated by the DPA, not the embed.

### Hospital-side (client-side)

A hospital that wants to count "widget viewed" without server-side webhook setup can listen to the `triaige:ready` and `triaige:result_shown` events and fire their own analytics. The widget itself does not load any third-party analytics on the hospital's behalf — they must wire their own.

---

## 7. Implementation effort estimate

### v1 (iframe widget) — 2 to 3 weeks

Breakdown:

- Tenant slug resolution + per-tenant config loading: 2–3 days. Extends the existing curated-condition file pattern in `backend/app/data/`.
- Embed page route at `widget.triaige.com/embed`: 2 days. Stripped layout from the existing dashboard chat surface.
- `postMessage` protocol implementation: 2 days.
- CSP `frame-ancestors` per-tenant: 1 day.
- Theme JSON loading + per-tenant overrides: 2 days.
- Hospital admin onboarding flow (basic — register origin, upload theme JSON): 2 days.
- Webhook delivery (HMAC, retries): 2 days.
- End-to-end test: a demo embedding page hosted on `widget.triaige.com/_demo` that the team uses to verify each tenant onboarding: 2 days.

Total: 15 working days, with realistic slip to 18–20 working days. Three calendar weeks for one engineer.

### v2 (JS SDK widget) — 4 to 6 weeks

Sequenced for ~9 months out, after iframe limitations bite. Out of scope for this v1 spec. Will be tracked as `EMBEDDED_WIDGET_SPEC.v2.md` when it lands.

---

## 8. Pilot deployment with Acıbadem

Recommended sequence (after the spec ships and the v1 widget is built):

1. **Pick the embedding page.** Acıbadem International landing page is the candidate — it has international traffic, a multilingual audience, and a single web team owning it.
2. **Onboarding.** TriAIge team registers Acıbadem's origin(s), provides the theme JSON template, gets it filled in, validates it.
3. **Staging embed.** Acıbadem embeds on a staging copy of the page; we and they verify together.
4. **Production embed.** Push to production. Monitor:
   - First 100 sessions in detail (every emergency hard-stop reviewed by clinical advisor + Acıbadem's named clinical contact).
   - Webhook delivery success rate.
   - Hospital-page Lighthouse score impact (should be < 100ms LCP regression with `loading="lazy"`).
5. **Iterate weekly.** Theme adjustments, intro copy adjustments, entry point experiments (`intro` vs `chat`), based on real session funnel.
6. **Expand placement.** After ~30 days of stable operation, Acıbadem decides whether to expand to additional branch sites.

This sequence is documented in the LOI ([`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md)) when the pilot is signed.

---

## 9. Out of scope for v1

- Native mobile-app SDK (iOS/Android). Hospitals with their own apps want our flow inside their app, not a web view. Tracked as a separate effort; not coupled to this widget.
- Multi-step embed (a "wizard" with hospital-controlled steps wrapping the widget). Adds substantial protocol complexity. Defer until requested.
- Server-side rendering of the widget into hospital pages. Conflicts with the runtime-update model; the iframe model is structurally more honest about who owns the runtime.

---

## Related documents

- [`docs/brand/WEBSITE_SCAFFOLD.md`](WEBSITE_SCAFFOLD.md) — sibling; the marketing site links to the widget surface from `/integrations`.
- [`docs/brand/REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) — sibling; the widget appears in the architecture diagram as an additional client surface.
- [`docs/PRIVACY_AND_SECURITY.md`](../PRIVACY_AND_SECURITY.md) — the widget inherits this posture.
- [`docs/SENTRY_REPLAY_POLICY.md`](../SENTRY_REPLAY_POLICY.md) — same scrub contract applies inside the widget.
- [`docs/DASHBOARD_THEME.md`](../DASHBOARD_THEME.md) — token source for the widget's theme system.
- [`docs/templates/LOI_TEMPLATE.md`](../templates/LOI_TEMPLATE.md) — pilot agreement that will reference this document.
- `docs/HIS_EHR_INTEGRATION.md` — sibling, being created in parallel; widget is integration tier 1.
- `backend/app/data/curated_conditions.demo_hospital.json` — file pattern to generalize per tenant.
