# HIS / EHR Integration — TriAIge

Last updated: 2026-04-27. Audience: hospital CIO + technical
architect. Use this memo as the technical leave-behind after the first
discovery call.

## Why this doc exists

Every hospital partner conversation reaches the same question within
the first 30 minutes: **"How do you integrate with our HBYS?"** Until
TriAIge has a written answer, the conversation stalls and the patient
flow stays hypothetical. This memo gives the CIO, the integration
architect, and the medical-tech vendor (often a third party) a single
document to align on scope, effort, and risk before pilot signing.

The TR-specific reality on the ground:

- Most TR HBYS (Hastane Bilgi Yönetim Sistemi) deployments are **not
  yet FHIR-native.** The dominant stack is HL7 v3 messaging into
  Sağlık-Net / e-Nabız, plus vendor-proprietary REST or SOAP for
  bilateral integrations. (Confirmed by the 2025 State of FHIR Survey:
  Turkey shows no major mandate or grant program for FHIR adoption as
  of early 2026.)
- Therefore, TriAIge's integration roadmap **must not assume FHIR**.
  FHIR is the future option; the present is webhook + proprietary REST.
- The first wave of pilots (Acıbadem, Memorial, Eczacıbaşı eVital
  channel) will most likely run as **Tier 0 or Tier 1**, not Tier 2.

---

## Current TriAIge surface area

The integration surface as of this writing is documented in
`docs/openapi_orchestrator.yaml`. Verified routes (under `backend/app/api/routes/`):

- `POST /v1/triage/turn` — main turn-based contract returning a typed
  envelope (`QUESTION` / `RESULT` / `EMERGENCY` / `ERROR`).
- `POST /v1/triage/stream` — SSE variant for spinner UX.
- `POST /v1/triage/feedback` — user up/down feedback on a result.
- `GET /v1/triage/history` — recent sessions for a device.
- `POST /v1/triage/send-summary` — email a session summary (currently
  via Resend).
- `POST /v1/triage/export-summary` — plain-text export.
- `GET /v1/facilities` — specialty-aware facility lookup (today: limited
  TR seed data).
- `GET /v1/config/features` — feature-flag + version-gate snapshot.
- `DELETE /v1/me/sessions/{session_id}` — KVKK / GDPR user-initiated
  deletion (CHANGELOG 4.6.0).
- `POST /v1/triage/push-token` (and `DELETE`) — Expo push registration.

What we **don't yet have** but that hospital integration will require:

- Outbound webhook / push to a hospital-side endpoint on every
  `RESULT` envelope. **To be built; ~3 engineering days for v1
  (signed JSON POST, retry queue, dead-letter, ops dashboard).**
- FHIR R4 resource emitter (`Encounter` / `Observation` /
  `ServiceRequest` / `Composition`). **To be built; ~2 engineering
  weeks for a covered subset.**
- HL7 v2 ADT/ORU bridge. **Almost certainly to be built per-hospital
  as integration glue, not as core product. ~1 week per HBYS vendor.**
- mTLS / VPN tunnel for hospital-network deployments.
  **Operationally to be set up per-pilot; no product code change.**

---

## Integration tiers

### Tier 0 — Standalone web/mobile, no HIS integration

The patient runs TriAIge before they reach the hospital — at home, in
the waiting room, or via a QR code on the appointment confirmation.
The output is a printable summary (PDF or email) the patient hands to
intake or to the clinician.

- **Effort:** day-1 deployable. Already shipping.
- **Risk:** lowest. No hospital-network integration, no PHI flowing
  into TriAIge from the HIS.
- **When to use:** first pilot wave; medical-tourism patients; any
  scenario where the hospital is risk-averse on integration before
  proving clinical value.
- **Recommended for the Acıbadem pilot.**

### Tier 1 — Outbound webhook to hospital intake endpoint

TriAIge POSTs the `RESULT` envelope (with optional patient identifiers
provided at session start: phone number, MRN, e-Nabız ID) to a
hospital-side webhook receiver. The hospital maps the envelope to a
patient record and surfaces it in the intake clinician's view.

- **TriAIge changes required:** add an outbound webhook config + signed
  POST + retry queue + dead-letter. ~3 engineering days for v1.
- **Hospital changes required:** expose an internal webhook receiver
  that authenticates TriAIge (mTLS or HMAC), validates the JSON, and
  writes into the patient record.
- **Effort end-to-end:** ~2 weeks elapsed including hospital-side
  procurement and security review.
- **Risk:** medium. PHI now flows hospital-side. Signed-payload +
  TR-residency posture matter.
- **When to use:** second pilot wave; any hospital that already has a
  modern integration team.

### Tier 2 — FHIR R4 native

TriAIge emits a FHIR `Bundle` containing `Encounter` + `Observation` +
`ServiceRequest` + `Composition` resources. The hospital's HBYS
ingests it via a FHIR endpoint. International-standard, future-proof,
but **almost no TR HBYS is FHIR-native today** — so this tier is
realistic only with HBYS vendors who have a FHIR adapter (typically
the multinationals or HBYS systems sold in Europe).

- **TriAIge changes required:** FHIR resource emitter + a Bundle
  builder. ~2 engineering weeks for the covered subset.
- **Hospital changes required:** a working FHIR R4 ingestion endpoint;
  may require HBYS vendor work.
- **Effort end-to-end:** ~4 weeks if the HBYS vendor is already
  FHIR-ready; ~2-3 months if the vendor has to build the receiver.
- **Risk:** medium-low once delivered (standards-based), high during
  build (vendor coordination).
- **When to use:** third+ pilot wave; partnerships with HBYS vendors;
  any export-market customer (UAE, KSA, EU).

### Tier 3 — Embedded inside the HBYS UI

TriAIge runs as an iframe or Web Component inside the HBYS
patient-registration flow. Triggered by the registration clerk or by
self-check-in kiosks. The session is born inside the HBYS context, and
the result is consumed in the same UI session — no separate user
authentication.

- **TriAIge changes required:** embeddable bundle (iframe + postMessage
  contract OR Web Component), embed-mode auth (HBYS session token
  exchange), CSP/iframe-ancestors hardening, embed-tenant theming
  hooks.
- **Hospital changes required:** HBYS vendor cooperation to add the
  embed point in the registration screen.
- **Effort end-to-end:** ~6-8 weeks with HBYS vendor cooperation;
  ~3-4 months without (we end up doing vendor education).
- **Risk:** highest. Deepest integration, biggest change-management
  surface, but highest patient-throughput payoff.
- **When to use:** post-pilot expansion; signed multi-hospital
  agreements; HBYS-vendor partnerships (Sisoft / AKGUN / Probel).

---

## TR-specific HIS systems

Numbers below are estimates; install bases in the TR private-chain
market are not publicly published. Treat as "[verify with vendor]"
before quoting in a sales doc.

### Sisoft (Sisoft Sağlık Bilgi Sistemleri)

- **Vendor:** Sisoft, Ankara.
- **Position:** HIMSS Europe research has named Sisoft a market-share
  leader among TR HIS vendors [verify with HIMSS source].
- **Install base:** widely deployed across TR public hospitals and
  university hospitals [verify with vendor].
- **FHIR maturity:** HL7 v2/v3 messaging confirmed; FHIR adapter not
  publicly advertised [verify with vendor].
- **Recommended tier:** Tier 1 (webhook) for first pilot; Tier 3
  (embed) if a multi-hospital partnership emerges.

### AKGUN Yazılım

- **Vendor:** AKGUN, Ankara.
- **Position:** long-established public-sector HIS vendor.
- **Install base:** large public-hospital footprint [verify with vendor].
- **FHIR maturity:** product page advertises HL7 international
  standards (ICD-10, ATC, LOINC, CPT, HL7 messaging). FHIR not
  explicitly advertised [verify with vendor].
- **Recommended tier:** Tier 1 (webhook) initial; Tier 2 if AKGUN ships
  a FHIR adapter.

### Probel Yazılım

- **Vendor:** Probel, İzmir.
- **Position:** "Paperless Hospital" positioning; education / training
  / state / university hospital footprint.
- **Install base:** material in TR public hospitals + universities
  [verify with vendor].
- **FHIR maturity:** offers integrated HBYS + LIS + RIS + clinical
  decision support, but FHIR not explicitly named on the product page
  [verify with vendor].
- **Recommended tier:** Tier 1 (webhook).

### ENLIL

- **Vendor:** ENLIL, Ankara.
- **Position:** mid-market HBYS, mobile + PACS modules.
- **Install base:** smaller than Sisoft / AKGUN / Probel
  [verify with vendor].
- **FHIR maturity:** unclear from public docs [verify with vendor].
- **Recommended tier:** Tier 1 (webhook).

### Acıbadem in-house (Cerebral Plus / Astore / Lab Assistant / Acıbadem Online)

- **Vendor:** Acıbadem Technology (in-house, since 2015).
- **Install base:** Acıbadem hospitals only; not licensed externally as
  far as we can find publicly.
- **FHIR maturity:** unknown [verify with vendor].
- **Recommended tier:** Tier 0 for the first pilot (de-risks the deal);
  Tier 1 (webhook into Acıbadem Online's patient portal) for v2; Tier 3
  (embed in Acıbadem Online) for v3.
- **Note:** Acıbadem owning their HIS is good news for partnership
  velocity once trust is established — they decide their own roadmap,
  no third-party vendor blocking.

### Memorial / Liv / Medical Park / Medicana / Anadolu / Florence Nightingale

We do not have public confirmation of which HBYS each major TR private
chain runs. Likely a mix of in-house (Memorial in particular) +
Sisoft / Probel / AKGUN. Discovery question for the first call:
**"Which HBYS do you run, and is the vendor on the call?"**

### Sağlık Bakanlığı Sağlık-Net / e-Nabız

The national substrate. Not an HIS we integrate **into**, but a data
source we may eventually integrate **with**. Uses HL7 v3 messaging.
Coverage: 28,608 facilities, 39 public institutions, ~82% of the TR
population enrolled. Future TriAIge integration target only after a
hospital pilot is signed and the privacy/legal posture is reviewed.

---

## FHIR mapping cheat-sheet

When we ship Tier 2, the TriAIge `RESULT` envelope maps to the
following FHIR R4 resources:

| TriAIge field                  | FHIR resource                     | Notes                                          |
|--------------------------------|-----------------------------------|------------------------------------------------|
| `session_id`                   | `Encounter.id`                    | UUID re-used.                                  |
| Session start / end timestamps | `Encounter.period.start/.end`     |                                                |
| `recommended_specialty`        | `ServiceRequest.code`             | Map specialty key to SNOMED-CT or local code.  |
| `urgency` (`EMERGENCY` / `SAME_DAY` / `ROUTINE`) | `ServiceRequest.priority` | `stat` / `urgent` / `routine`.                 |
| Extracted canonicals (symptoms)| `Observation.valueCodeableConcept`| One `Observation` per canonical, linked to the `Encounter`. |
| Top conditions + scores        | `Observation` with `category=survey` and an extension carrying `score_0_1` | Confidence is non-standard; carry as extension. |
| `doctor_ready_summary_tr`      | `Composition.section[].text`      | Markdown blob.                                 |
| `safety_notes_tr`              | `Composition.section[].text`      | Separate section.                              |
| Explainability trace           | `Composition.section[].text`      | "Why this specialty / why questioning stopped / risk reasons" — Markdown. |
| Patient identifier (if given)  | `Encounter.subject` -> `Patient`  | TR national ID / phone / MRN; whichever the hospital uses. |

The whole thing is wrapped in a `Bundle` (`type=transaction` for
ingest). We do not author `Patient` resources — the hospital owns
patient identity; TriAIge references the existing `Patient` by
identifier.

---

## KVKK / data residency

This is the single most asked question after "how do you integrate".
The current state of the answer:

- TriAIge is KVKK-aware by design: PII masking in logs, hashed device
  IDs, user-initiated deletion endpoint, documented privacy posture
  (`docs/PRIVACY_AND_SECURITY.md`).
- The current production stack runs on Fly.io (compute) + Supabase
  (database). Region selection drives the residency answer.
  **Open item:** confirm the Supabase region of record and decide
  whether TR-resident customers require a TR-region deployment or are
  satisfied with EU-region. This needs to be resolved in
  `docs/PRIVACY_AND_SECURITY.md` before any signed pilot.
- For SGK-billable patients: the safe default assumption is that
  patient data must remain in TR. We should not promise this is
  satisfied today without a region check — flag as a **pre-pilot
  blocker for Acıbadem**.
- For medical-tourism / private-pay patients: EU-residency is
  generally acceptable, but verify per partner.
- LLM call telemetry (when LLM features are enabled): currently goes to
  the model provider's endpoint. PII-masking and prompt-redaction are
  in place; for KVKK-strict deployments, the long-term answer is a
  TR-resident inference path or a fully-deterministic-only deployment
  profile (the "deterministic-only" mode is already a configurable
  flag — `llm_nlu_enabled` / `llm_explain_enabled` in
  `GET /v1/config/features`).

---

## Suggested first-meeting deliverable

After the discovery call with a CIO, leave behind a 1-page tailored
"integration estimate" with five lines:

1. **Recommended tier** (0 / 1 / 2 / 3) and one-line reason.
2. **Effort estimate** in elapsed weeks, broken into TriAIge-side and
   hospital-side.
3. **Top three open questions** (HBYS vendor, residency, identifier
   strategy).
4. **Top three risks** (vendor cooperation, KVKK posture, clinical
   validation).
5. **Suggested next step** — usually "30-min call with HBYS vendor
   present" or "share API spec under NDA, then a 60-min architecture
   review".

A markdown template for this is in `docs/sales/templates/` — to be
created in the next iteration; until then, copy the structure above.

---

## Sources

- [Probel — Hospital Information Management System](https://en.probel.com.tr/hospital-information-management-system/)
- [Sisoft Healthcare Information Systems](https://www.sisoft.com.tr/en/)
- [AKGUN HIMS](https://www.akgunyazilim.com.tr/en/urunler/akgun-hastane-bilgi-yonetim-sistemleri-hbys)
- [ENLIL HBYS](http://enlil.com.tr/hbys.html)
- [Acıbadem Technology — about](https://www.acibademtechnology.com/about-us/)
- [Tiga Health — From Sağlık.NET to e-Nabız](https://www.tigahealth.com/from-saglik-net-to-e-nabiz-the-digital-journey-of-personal-health-records-in-turkiye/)
- [HL7 Chile — 2025 State of FHIR Survey (Turkey)](https://hl7chile.cl/wp-content/uploads/2025/06/2025-State-of-FHIR-Survey-Report.pdf)
- [HL7 FHIR overview](https://www.hl7.org/fhir/overview.html)
