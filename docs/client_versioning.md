# Client capability protocol

## The problem

We need to ship new response fields (`top_conditions[].icd10` and friends, EMERGENCY-path `recommended_specialty`) without breaking clients that don't know about them yet. Traditional API versioning (`/v2/...`) is too coarse: we'd double-maintain every endpoint. Semver headers would work in principle, but `mobile/app.config.ts` has been at `1.0.0` through many feature commits — version numbers aren't a reliable discriminator here.

## The mechanism

Clients declare what they can parse via an additive, capability-based header:

```
X-Client-Version: 1.3.0
X-Client-Capabilities: curated_meta,emergency_specialty
```

The server strips any field whose capability token the client did not advertise. Missing header → empty capability set → minimal payload — the oldest imaginable client always sees something it can handle.

## Wire format

| Header | Required | Value | Notes |
|---|---|---|---|
| `X-Client-Version` | optional | free-form | logged only; does **not** gate payload |
| `X-Client-Capabilities` | optional | comma-separated tokens | parsing: whitespace-trimmed, lower-cased, unknown tokens dropped |

Tokens are ASCII `[a-z_]+`. Do not pack structure into the value — each capability is a boolean.

## Registry

Defined in [`backend/app/version_gating.py`](../backend/app/version_gating.py):

| Token | What it unlocks |
|---|---|
| `curated_meta` | `Envelope.payload.top_conditions[*]` curated fields: `disease_description`, `disease_description_tr`, `icd10`, `source_type`, `disclaimer_tr`, `doktora_sorulacak_sorular_tr`, `izlenecek_belirtiler_tr`, `ne_zaman_tekrar_basvur_tr`, `self_care_tr`, `aciliyet_notu_tr` |
| `emergency_specialty` | `Envelope.payload.recommended_specialty` **only when `envelope.type == "EMERGENCY"`** |

Routing info (`recommended_specialty_tr`, `urgency`) is **never** gated — every client sees it.

## Adding a new capability

1. Add a `CAP_*` constant in `backend/app/version_gating.py` and register it in `KNOWN_CAPABILITIES`.
2. If the new field lives inside `top_conditions`, also add its key to `CURATED_TOP_CONDITION_FIELDS` (or extend the filter if the shape differs).
3. Write one unit test (with-cap / without-cap) in `backend/tests/test_version_gating.py`.
4. Update the registry table in this doc.
5. Bump the mobile capability list once the client ships support — see `mobile/src/config/runtime.ts` (TBD, see [Client Capabilities — TBD](#client-capabilities--tbd)).

The backend change is safe to merge before the client change: clients without the new capability keep getting filtered payloads, so the rollout is strictly additive.

## Where gating happens

Single middleware — `CapabilityGateMiddleware` — mounted in `backend/app/main.py`. It:

1. Intercepts responses on `/v1/*` with `Content-Type: application/json`.
2. Parses `X-Client-Capabilities` once.
3. Fast-paths if the client advertises every known capability (most production traffic once clients are current).
4. Otherwise decodes the JSON body, runs `filter_envelope(data, caps)`, re-serialises, and rewrites `Content-Length`.

Invalid JSON is passed through untouched — the server stays correct even when the response isn't a triage envelope.

## What's explicitly not gated

- **Routing semantics**: `recommended_specialty_tr` on RESULT, `urgency`, `stop_reason`.
- **Meta envelope**: `disclaimer_tr`, `timestamp`, `model_info`, `debug`, `facility_discovery`. Treat `facility_discovery` as optional (clients always may skip it) but not as a capability gate — it was in the contract before this protocol existed.
- **Admin-only responses**: `/v1/admin/*` rows written from the database. Gating in the browser-dashboard response would desync the dashboard from the database; dashboard gets full payloads.

## Testing

- `backend/tests/test_version_gating.py` → 100% branch coverage on parser, filter, and middleware.
- Safety-critical gate in `backend-regression.yml` enforces `--cov-fail-under=100` on `app.version_gating` alongside `emergency_router`, `safety_guard`, and `top_conditions_filter`.

## Related: runtime feature flags (`useVersionGate`)

This protocol is **not** the same as the runtime feature-flag layer the mobile app also uses. They operate on different axes:

| Layer | Where it lives | Direction | Question answered |
|---|---|---|---|
| Capability gating (this doc) | `backend/app/version_gating.py` + `mobile/src/config/capabilities.ts` | Client → Server, every request | "Which response FIELDS can I parse?" |
| Feature-flag gating | `backend/app/api/routes/features.py` + `mobile/src/hooks/useVersionGate.ts` + `mobile/src/api/featuresClient.ts` + `mobile/src/utils/semver.ts` | Server → Client, at startup | "Which FEATURES should I enable, and is my build still supported?" |

The two layers are **complementary**, not redundant:

- Capability gating lets the backend ship new response fields (curated metadata, an EMERGENCY specialty hint) without waiting for every installed build to understand them. The response is shape-correct for whatever version of the client is asking.
- `useVersionGate` lets the backend tell a client "LLM explanations are on this week", "you're 2 minor versions behind, show a banner", or "your build is too old, block new sessions". None of that is about payload shape.

When adding a new user-visible feature, you'll usually touch both: gate the new payload field with a capability, AND (if the feature has runtime UX state — rollout toggle, banner, block) surface it in the `/v1/config/features` response that `useVersionGate` reads.

If a capability is advertised but the corresponding feature flag is off, the backend still emits the gated field (it has no reason to strip a field the client claims to understand); the client just chooses not to render it because the feature flag is off. Neither layer has to know about the other.

## Mobile side

The mirror registry lives in [`mobile/src/config/capabilities.ts`](../mobile/src/config/capabilities.ts). It exposes:

- `CAP_CURATED_META`, `CAP_EMERGENCY_SPECIALTY` — token constants typed as string literals (`as const`), so accidental typos fail `tsc`.
- `CLIENT_CAPABILITIES` — readonly ordered array (canonical serialisation order).
- `getCapabilitiesHeader()` — returns the comma-joined header value.
- `__testing.setCapabilities(set | null)` / `__testing.reset()` — test-only hooks for simulating older clients.

**Why a dedicated module** (over `app.config.ts extra` or stuffing into `runtime.ts`):

- Capability tokens change at release cuts, not at deploy time — compile-time constants match the cadence. `extra`-block indirection buys nothing and adds a rebuild step to change a string.
- Token names are a finite union — tests, handlers, and assertions benefit from `CapabilityToken` type-safety. `extra` is untyped strings.
- One dedicated file keeps the "add a capability" checklist in one place; the module's top-of-file comment links back to this doc and the backend registry.
- Test override uses a module-level setter — no Jest `moduleNameMapper` gymnastics, no monkey-patching `Constants`.

### Injection points

The header is attached at the two low-level fetch wrappers, so every API caller in the app picks it up automatically:

- [`mobile/src/api/fetchWithTimeout.ts`](../mobile/src/api/fetchWithTimeout.ts) — used by `pushClient`, `feedbackClient`, `summaryClient`, `triageClient`, `HistoryScreen`.
- [`mobile/services/api.ts`](../mobile/services/api.ts) — `ApiClient.request()` (session start/message/result/summary).

Individual callers never need to know the protocol exists.

### Drift protection

Backend `KNOWN_CAPABILITIES` and mobile `CLIENT_CAPABILITIES` MUST agree. Enforced by:

- [`scripts/check_capability_drift.cjs`](../scripts/check_capability_drift.cjs) — parses both registries and exits non-zero on mismatch.
- [`.github/workflows/capability-drift.yml`](../.github/workflows/capability-drift.yml) — runs the script on any PR touching either file.

Local check: `node scripts/check_capability_drift.cjs`.

## Rollback

If the middleware misbehaves in production, comment out the `app.add_middleware(CapabilityGateMiddleware)` line in `backend/app/main.py`. All other behaviour is unaffected — endpoints still emit the full payload; only the trailing filter layer is skipped.
