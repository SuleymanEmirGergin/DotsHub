# Letter of Intent — TriAIge Pilot — TEMPLATE

> **DISCLAIMER**
>
> Bu doküman bir başlangıç şablonudur — hukuki tavsiye değildir. KVKK / GDPR uzmanı bir avukatın imza öncesi review'undan geçirilmelidir. TriAIge bu şablonun yarattığı veya yaratabileceği yükümlülüklerden sorumlu değildir.
>
> *This document is a starting template, not legal advice. It must be reviewed by KVKK / GDPR-qualified counsel before signing. TriAIge accepts no liability for obligations arising from use of this template.*

---

## 1. Parties

**Hospital / Hastane:**
`[HASTANE / HOSPITAL LEGAL NAME]`
`[Adres / Address]`
`[Vergi No / Tax ID]`

**Vendor / Sağlayıcı:**
TriAIge `[Ticari Unvan / Legal Entity to be confirmed]`
`[Adres / Address]`

The Hospital and TriAIge each, a "Party"; together, the "Parties".

---

## 2. Executive sponsors

| Side / Taraf | Name / Ad-Soyad | Title / Unvan | Email |
| ------------ | --------------- | ------------- | ----- |
| Hospital / Hastane | `[ ]` | `[ ]` | `[ ]` |
| TriAIge | Emir Gergin | Founder | `emirgergin21@gmail.com` |

Each executive sponsor is the named escalation point for issues not resolvable at the working level. Substitution requires written notice to the other Party.

---

## 3. Pilot scope / Pilot kapsamı

The Hospital and TriAIge will run a pilot of TriAIge's pre-triage agentic AI service under the following scope:

- **Duration / Süre:** `[3 ay]` (default), starting `[Pilot Start Date]`.
- **Patient volume / Hasta hacmi:** Up to `[100 hasta / 100 patients]` over the pilot period.
- **Clinical scope / Klinik kapsam:** `[1 klinik birim — örn. Acil triyaj öncesi web/mobil yönlendirme / 1 clinical unit]`.
- **Geography / Lokasyon:** `[Pilot site address(es)]`.

**TriAIge feature set in scope:**
- Free-text symptom intake (5 locales: TR / EN / DE / RU / AR with Arabic RTL).
- Deterministic emergency hard-stop rules (rule-driven, not LLM inference).
- Budgeted agentic question loop with bounded turn count.
- `RESULT` envelope with explainability trace (top-specialty rationale, why questioning stopped, risk reasons).
- Per-session event timeline + admin dashboard.
- Optional summary email delivery to the patient on request.
- KVKK-aware logging + Sentry KVKK-safe Session Replay (see DPA §6 and `docs/SENTRY_REPLAY_POLICY.md`).

**Out of scope during pilot:**
- Diagnosis / treatment recommendation.
- HIS / EMR integration (unless contracted as a paid add-on under §6).
- Custom locale beyond the 5 already supported.

---

## 4. Success metrics / Başarı metrikleri

The Parties will jointly select **at least two** of the following metrics, each with an agreed threshold, before pilot start. Metrics are reviewed at every cadence meeting (§7) and re-confirmed at the conversion decision point (§7).

| # | Metric / Metrik | Definition / Tanım | Target / Hedef |
| - | --------------- | ------------------ | -------------- |
| 1 | **Emergency-flag catch rate / Acil işaret yakalama oranı** | Of the cases retroactively confirmed by clinicians as true emergencies, the % correctly routed by TriAIge to an `EMERGENCY` envelope. | `[≥ X%]` |
| 2 | **User satisfaction (NPS) / Kullanıcı memnuniyeti** | NPS score collected via TriAIge's in-app feedback endpoint at the end of each session. | `[≥ Y]` |
| 3 | **Time-to-routing reduction / Yönlendirme süresi azalması** | Median time from patient first contact to a confirmed routing decision, vs. the Hospital's pre-pilot baseline. | `[Reduction ≥ Z%]` |
| 4 | **Inappropriate ER visit reduction / Gereksiz Acil başvuru azalması** | % of pilot-cohort patients who used TriAIge and did NOT subsequently arrive at the ER for a self-resolving condition, vs. the Hospital's pre-pilot baseline. | `[Reduction ≥ W%]` |

Selected metrics: `[Hospital + TriAIge initials in margin]`.
Baseline measurement period for any "vs. baseline" metric: `[Pre-pilot baseline window — e.g. last 6 months]`.

> Targets are set jointly. TriAIge does not guarantee any specific clinical outcome — pilot success is evaluated against the agreed targets, not against absolute claims.

---

## 5. Pricing during pilot / Pilot ücretlendirmesi

**Pilot fee:** `[ücretsiz / no cost]` *(default)* OR `[indirimli aylık X TL / discounted X TL per month]`.

The pilot fee covers:
- Backend hosting and operational SLO described in §8.
- Onboarding sessions for the Hospital's clinical and IT staff.
- Monthly pilot review (§7).

Pilot fee does NOT cover:
- HIS / EMR integration work (separately scoped).
- On-site training beyond `[X saat / X hours]` per month.
- Custom branding or white-labelling.

---

## 6. Pricing post-pilot / Pilot sonrası ücret

If the Parties convert the pilot to a production engagement (§7), pricing will be:

- **Annual platform fee / Yıllık platform ücreti:** `[X TL / yıl]`
- **Per-session fee / Oturum başına ücret:** `[Y TL / oturum]` (subject to volume bands `[Z TL/session @ ≥N sessions/month]`)
- **Optional add-ons:** HIS / EMR integration `[fixed quote]`, on-site training day `[fixed quote]`, additional locale `[fixed quote]`.

Final post-pilot pricing is captured in the master service agreement, which the Parties will execute in good faith on or before `[Conversion Decision Date]` (§7).

---

## 7. Term, decision points, and cadence

- **Pilot term / Pilot süresi:** `[3 ay]` from Pilot Start Date.
- **Cadence meetings / Periyodik toplantılar:** every `[2 hafta / 2 weeks]`, alternating between operational review and metric review.
- **Mid-pilot checkpoint / Ara değerlendirme:** end of month `[2]`. Either Party may flag a material concern in writing; failure to resolve within `[14 gün]` is grounds for early exit (§9).
- **Conversion decision point / Dönüşüm karar noktası:** at month `[3]`, the Parties will meet within `[10 iş günü]` of pilot end and choose one of:
  - **Convert / Dönüştür** — proceed to master service agreement at the §6 pricing.
  - **Extend / Uzat** — extend the pilot for an additional `[X ay]` at `[same / renegotiated]` terms.
  - **Exit / Sonlandır** — terminate without conversion, subject to §10 (data return / deletion).

A conversion decision in favour of "Convert" is non-binding under this LOI (see §11) and is formalised by execution of the master service agreement and the KVKK DPA.

---

## 8. Mutual NDA reference

This LOI is executed under a Mutual Non-Disclosure Agreement signed between the Parties on `[NDA Execution Date]`. All information shared during the pilot — including patient cohort design, metric baselines, technical configuration, and pricing — is "Confidential Information" under that NDA.

If no NDA is in place at the time of LOI execution, **the confidentiality clause in §9 is binding stand-alone** until a separate NDA is signed.

---

## 9. Confidentiality and intellectual property

- **Pre-existing IP / Mevcut fikri mülkiyet:** Each Party retains all right, title, and interest in its pre-existing intellectual property. Nothing in this LOI transfers ownership.
- **Pilot data / Pilot verisi:** All patient-related data generated during the pilot remains the property of the Hospital. TriAIge processes such data solely as Data Processor under the KVKK DPA and does not acquire any ownership or independent right of use.
- **Aggregated, anonymised metrics:** TriAIge may use aggregated, anonymised metrics about pilot usage (envelope distribution, latency, locale mix, etc.) for product improvement, **provided no patient or hospital is identifiable** in such use.
- **Confidentiality / Gizlilik:** Each Party will protect the other's Confidential Information with at least the same care it applies to its own confidential information of similar sensitivity, and never less than reasonable care. This obligation survives termination for `[3 yıl]`.

---

## 10. Data return / deletion on termination

On termination of the pilot for any reason:

- TriAIge will return or delete all Hospital-controlled personal data within `[30 gün]`, per the Hospital's written instruction, in line with the KVKK DPA §12.
- TriAIge will provide written confirmation that deletion is complete.
- Aggregated, anonymised metrics retained under §9 are not subject to this return / deletion obligation, provided they remain truly non-identifiable.

---

## 11. Non-binding except / Bağlayıcılık

This LOI is **non-binding** except for the following clauses, which are binding on the Parties from the date of signature:

- §8 (Mutual NDA reference / stand-alone confidentiality).
- §9 (Confidentiality and intellectual property).
- §10 (Data return / deletion on termination).
- §12 (Governing law).

All other clauses — including pilot scope, success metrics, pricing, and conversion intent — represent the Parties' good-faith intent at the time of signature and are not legally binding obligations.

*Bu LOI, §8, §9, §10 ve §12 dışında **bağlayıcı değildir**. Diğer maddeler tarafların imza tarihindeki iyi niyet beyanını yansıtır ve hukuken bağlayıcı yükümlülük doğurmaz.*

---

## 12. Governing law

This LOI is governed by the laws of the Republic of Turkey. The courts and execution offices of `[İSTANBUL]` have exclusive jurisdiction over disputes arising from the binding clauses listed in §11.

---

## 13. Signatures / İmzalar

**For the Hospital / Hastane Adına**
İmza / Signature: __________________________
Ad-Soyad / Name: `[ ]`
Unvan / Title: `[ ]`
Tarih / Date: `[ ]`

**For TriAIge / TriAIge Adına**
İmza / Signature: __________________________
Ad-Soyad / Name: `[ ]`
Unvan / Title: `[ ]`
Tarih / Date: `[ ]`
