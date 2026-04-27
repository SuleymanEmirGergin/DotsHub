# 90-Second Demo Script — TriAIge

A tight, narrated walkthrough for hackathon judges. Goal: prove three
things in 90 seconds — emergency hard-stop is rule-driven, the
explanation trace is real, and the system is multilingual and
operationally observable.

For the surrounding pitch, see
[`HACKATHON_LANDING.md`](HACKATHON_LANDING.md).

---

## Setup (pre-demo)

Get these into a known good state before judges sit down. None of them
should be touched live.

- **Mobile app** running on a simulator or device, language preset to
  Turkish, on the intro screen. Have English locale also reachable
  via the language picker if a judge asks.
- **Admin dashboard** open in a separate browser window or second
  display, logged in, on the **Sessions** list view sorted by most
  recent. The session you create live will land at the top.
- **`/health` tab** open in a third tab to demo on demand if asked
  about ops. Should currently be green.
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

Likely judge questions, with tight answers.

**Q: Why not just use GPT-4 for this?**
A: Because you cannot certify a chest-pain hard-stop that depends on
sampling temperature. The emergency layer is deterministic rules
running before any model; the LLM-adjacent pieces (NLU extraction)
are bounded, metered, and have a deterministic fallback.

**Q: How do you handle medical liability / KVKK / patient data?**
A: We do not diagnose — the envelope and disclaimer are explicit. PII
is masked in logs, IDs are hashed, and there is a documented privacy
posture in [`PRIVACY_AND_SECURITY.md`](PRIVACY_AND_SECURITY.md). A
user-initiated `DELETE /v1/me/sessions/{session_id}` endpoint exists.
Final policy text is for legal — we built the plumbing.

**Q: What happens when the model is wrong?**
A: Two layers. First, every result has a deterministic explanation
trace and a feedback button — feedback flows into a tuning task
loop with guardrail checks and automatic rollback if a patch
regresses. Second, the entire system is pre-triage: it routes, it
does not treat. The clinician remains the decision-maker.

**Q: How does this scale beyond a hackathon demo?**
A: The backend already supports multi-instance rate limiting via
Redis, structured JSON logs with request IDs, Prometheus `/metrics`
with native Supabase counters, and a Grafana dashboard with alerts
synced as code. EAS build pipeline ships the mobile app. Fly.io
deploy with always-on suspend-resume is wired. The CI surface
covers regression, lighthouse, a11y, secret scan, and capability
drift.

---

## Closing line

"This system does not diagnose. It determines — and it shows its
work, every turn, in five languages, with a hard stop you can audit."
