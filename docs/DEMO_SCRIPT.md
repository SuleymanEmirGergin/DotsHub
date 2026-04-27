# 90-Second Demo Script — TriAIge

A tight, narrated walkthrough for investor demos and clinical-buyer
walkthroughs. Goal: prove three things in 90 seconds — emergency
hard-stop is rule-driven, the explanation trace is real, and the system
is multilingual and operationally observable.

For the surrounding pitch, see [`PITCH.md`](PITCH.md).

---

## Setup (pre-demo)

Get these into a known good state before the meeting starts. None of
them should be touched live.

- **Mobile app** running on a simulator or device, language preset to
  Turkish, on the intro screen. Have English locale also reachable
  via the language picker if asked.
- **Admin dashboard** open in a separate browser window or second
  display, logged in, on the **Sessions** list view sorted by most
  recent. The session you create live will land at the top.
- **`/health` tab** open in a third tab to demo on demand if anyone
  asks about ops. Should currently be green.
- **Network**: hard-wired or stable WiFi. The mobile offline banner
  is a feature, not what you want to demo unless someone asks.
- **Pre-seeded scenarios** memorized verbatim:
  - Emergency: "göğsümde şiddetli bir sıkışma var, sol koluma vuruyor"
    (chest pressure radiating to left arm).
  - Same-day: "iki gündür sağ alt karın bölgemde keskin bir ağrı var,
    yürümek de zorlaştı" (two days of sharp right-lower abdominal
    pain, walking is hard).
- **Recorded fallback gif/video** of a successful end-to-end flow on a
  USB stick or local file — see fallbacks below.

---

## The 90-second beat sheet

| Time | Action | Narration |
| --- | --- | --- |
| 0:00 – 0:10 | Hold on the mobile intro screen. | "Patients often do not know where to go first. They panic and visit emergency, or delay despite warning signs. This system answers — fast, multilingual, and explainable." |
| 0:10 – 0:25 | Tap into the symptom screen. Type the **emergency** scenario in Turkish. | "Free-text input. Five locales — Turkish, English, German, Russian, Arabic with right-to-left. The same i18n contract test that gates CI also gates this demo." |
| 0:25 – 0:40 | Submit. Show the `EMERGENCY` envelope landing immediately. Switch to the dashboard, open the new session, point at the event timeline. | "This stop is rule-driven, not LLM-driven. The trace shows which emergency rule fired before any scoring or questioning ran. There is no override path." |
| 0:40 – 1:00 | Reset on mobile. Type the **same-day** scenario. Submit. Answer one or two clarifying `QUESTION` turns as they appear. | "When it is not an emergency, the orchestrator runs a budgeted question loop. Bounded turn count, deterministic scoring. It stops when it has enough signal — not when it feels chatty." |
| 1:00 – 1:20 | Land on the `RESULT` screen. Read out: specialty, urgency, risk level. Tap "explanation" or scroll to the trace section. | "Every result is one envelope: specialty, urgency, risk, and the trace — extracted canonicals, why this specialty scored highest, why questioning stopped, why the risk landed where it did. No 'the model said so' answers." |
| 1:20 – 1:30 | Switch to the dashboard. Show the new session's full event timeline and the health overview at the top. | "Every turn is auditable. The dashboard replays the same envelopes, surfaces low-confidence and high-risk trends, and `/health` is a real Supabase check." |

---

## If something breaks

Three pre-decided fallbacks. Pick the first that applies; do not stack
them.

- **Mobile dev server is slow or hangs on first build.** Switch to the
  recorded gif/video on the USB stick. Narrate over it with the same
  beat sheet. Do not apologize — say "here's a captured run from
  earlier today" and continue.
- **Supabase is unreachable.** This is the demo. `GET /health` will
  return a degraded status; admin event timeline will show the failure
  mode. Pivot the narration: "this is what observability looks like —
  the failure is visible at `/health`, in the dashboard, and in
  Sentry. The mobile app surfaces an offline banner. Nothing
  silently swallows the error."
- **Backend rate limit trips during demo.** The mobile app shows
  `429` with a retry hint. Narrate: "rate limits are real, per-IP,
  and shared across instances when Redis is configured." Wait one
  window (60 seconds default) or pivot to the recorded fallback.

---

## Q&A primer

Four questions investors and clinical buyers actually ask, with tight
answers anchored to repo artifacts. Hedge where the honest answer is
"not yet" — do not fabricate.

**Q (investor): What's the regulatory path / FDA-equivalent posture in
your target markets?**
A: No FDA-cleared device today. The system is positioned as
pre-triage, not diagnosis — the envelope and disclaimer are explicit
on that line, and the clinician remains the decision-maker. KVKK and
GDPR posture (PII masking, hashed IDs, user-initiated session
deletion via `DELETE /v1/me/sessions/{session_id}`) is documented in
[`PRIVACY_AND_SECURITY.md`](PRIVACY_AND_SECURITY.md). Formal FDA /
CE-mark conversation is phase-2, after pilot data.

**Q (investor): What's the wedge for a first paying customer? Unit
economics at the n=10 hospital scale?**
A: The wedge is intake — patients self-routing in five locales before
they hit a clinician, with a deterministic emergency hard-stop and a
full audit trail per session. Unit economics are bounded by design:
the agentic loop is turn-budgeted and the LLM-adjacent steps have
deterministic fallbacks, so cost per session has a hard ceiling rather
than long-tail risk. First-customer pricing is a pilot conversation,
not a published rate card.

**Q (customer): How does this integrate with our HIS / EHR? What's
the liability surface for a misroute?**
A: Today the surface is the API (`POST /v1/triage/turn`) plus the
admin event timeline. EHR / HIS integration is bespoke per pilot —
the result envelope (specialty, urgency, risk, full trace) is shaped
to drop into a referral or routing record. On liability: the system
does not diagnose, the disclaimer is explicit on the result screen,
and the deterministic explanation trace gives a defensible audit
artifact for any flagged case. The emergency rules path is rule-driven,
not LLM-driven, which is the question safety committees ask first.

**Q (customer): What does a pilot look like? What success metric would
you commit to?**
A: A scoped pilot is one specialty path or one demographic in one
locale, run alongside existing intake — shadow mode first, then
advisory. Useful success metrics that we can measure today from the
event timeline: agreement rate against clinician routing on the same
session, time-to-decision, and emergency-rule precision. We would
commit to a target on agreement rate and emergency-rule precision in
the pilot agreement; throughput targets depend on volume.

---

## Closing line

"This system does not diagnose. It routes — and it shows its work,
every turn, in five languages, with a hard stop the safety committee
can audit and an event timeline the operator can replay."
