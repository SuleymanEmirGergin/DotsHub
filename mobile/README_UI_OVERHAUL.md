# Expo RN Triage UI Overhaul

## Scope
This change is a UI-only refactor for the Expo React Native triage flow.

Touched files:
- `mobile/src/ui/designTokens.ts` (new)
- `mobile/src/ui/primitives.tsx` (new)
- `mobile/src/screens/IntroScreen.tsx`
- `mobile/src/screens/ChatScreen.tsx`
- `mobile/src/screens/QuestionScreen.tsx`
- `mobile/src/screens/ResultScreen.tsx`
- `mobile/src/screens/EmergencyScreen.tsx`
- `mobile/src/screens/ErrorScreen.tsx`
- `mobile/src/ui/ConfidenceBar.tsx`
- `mobile/app/index.tsx`
- `mobile/README_UI_OVERHAUL.md` (new)

## Non-goals
- No business logic change.
- No API contract change.
- No Zustand state shape change.
- No dependency changes.
- No edits in out-of-scope legacy paths (`mobile/screens/*`, `mobile/components/*`).

## Behavior Parity Guarantees
The following behavior is intentionally preserved:
- Intro gate still requires acceptance and calls `setAcceptIntro(true)`.
- Chat send flow remains: user message -> loading state -> assistant loading bubble -> `triageTurn` -> `applyEnvelope`.
- Question flow still supports all `answer_type` branches and sends identical payload structure.
- Result flow keeps confidence fallback logic (`backendConf ?? computeConfidence(result)`).
- Feedback still uses one-submit guard and same payload fields.
- Emergency actions still call `tel:112` and SMS URL logic.
- Error screen still resets session the same way.
- Envelope-driven routing order in `mobile/app/index.tsx` is unchanged.

## UTF-8 Cleanup
Scoped UI strings were normalized to Turkish UTF-8 text.
No English demo copy was introduced in scoped files.

## Validation
### Type check
Run in `mobile`:

```bash
npx tsc --noEmit
```

### Manual QA Checklist
- Intro gate blocks progression until checkbox is selected.
- Chat send triggers backend turn and navigates by envelope type.
- All answer types work (`yes_no`, `free_text`, `number`, `multi_choice`).
- Result feedback can only be sent once per result screen state.
- Emergency screen actions trigger call and SMS handlers.
- Error reset starts a fresh flow.
- No clipping in input bars/buttons on Android emulator and Expo web.

## Notes
This workspace does not expose a git repository root, so delivery is file-level with validation output.
