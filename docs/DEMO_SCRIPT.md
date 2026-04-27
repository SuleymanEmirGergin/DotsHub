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
- **Pre-seeded scenarios** memorized verbatim. These exact strings are
  the ones the deterministic safety / scoring rules are tested against
  in `backend/app/data/demo_scenarios/`. Paraphrasing them on stage can
  cause a non-emergency phrasing of the chest scenario to slip past
  the keyword path, so type them as written:
  - Emergency: "Göğsümde baskı var, sol koluma vuruyor ve terliyorum.
    Nefes darlığı da var." (chest pressure + radiating arm pain +
    sweating + dyspnea — fires `chest_pressure_sweating` in
    `backend/app/data/rules.json` and `chest_pain_sob` in
    `config/emergency_rules.json`).
  - Same-day-ish: "Dün akşamdan beri karnımın sağ alt tarafında ağrı
    var, ateşim 38.2 derece." (right-lower abdominal pain plus fever —
    routes to General Surgery via the specialty scorer; the
    multi-turn flow probes for nausea / palpation pain before
    settling).
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
| 1:00 – 1:20 | Land on the `RESULT` screen. Read out: specialty, urgency, risk level. Scroll to the rationale (`why_specialty_tr`) section on the result card. | "Every result is one envelope: specialty, urgency, risk, and the per-specialty rationale on screen. The full trace — extracted canonicals, stop reason, scoring debug — is on the matching admin session row, ready to replay. No 'the model said so' answers." |
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

---

## Pre-flight checklist

Run in order, ~5 min before the meeting starts. Each step has an
exit signal — do not move on until you see it.

- [ ] Backend: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` — wait for `Uvicorn running on http://0.0.0.0:8000`. Visit http://localhost:8000/health, expect `{"status":"ok","service":"triaige-api","version":"4.0.0",...}` and (if Supabase is configured) `"supabase":"ok"`.
- [ ] Dashboard: `cd dashboard && npm run dev` — wait for `Ready in ...` from Next.js. Visit http://localhost:3000/admin/sessions; expect the sessions list, sorted by `created_at` desc by default.
- [ ] Mobile: `cd mobile && npm start` — wait for the Expo dev server QR / menu. Press `i` (iOS sim), `a` (Android emulator), or scan the QR with Expo Go. Verify the intro screen renders in Turkish.
- [ ] Run the pre-seeded **emergency** scenario verbatim once on the mobile app to warm caches and confirm the `EMERGENCY` envelope fires before any LLM hop. Tear the session down on the mobile side; leave the dashboard tab pointed at `/admin/sessions` so the live demo session lands at the top.
- [ ] Open `/health` in a third browser tab so it can be revealed on demand without switching contexts.
- [ ] Have the recorded fallback gif/video on a USB stick or local file, ready to play.
- [ ] Phone on silent, OS notifications off, screen brightness up, dock visible. Resize the dashboard window so the sessions table is fully visible.
- [ ] Confirm network: hard-wired or stable WiFi. The mobile offline banner is a feature, not what you want to demo unscripted.
